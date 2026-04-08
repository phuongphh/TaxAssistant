"""
Tax regulation update scheduler.

Runs the tax regulation scraper on a configurable schedule to automatically
detect and ingest new/updated tax laws from Vietnamese government websites.

Architecture:
    FastAPI startup → scheduler.start() → background asyncio task
                                           ↓ (every SCRAPE_INTERVAL_HOURS)
                                      scraper.scrape_all()
                                           ↓
                                      ingest_scraped_documents()
                                           ↓
                                      PostgreSQL + ChromaDB updated

Usage:
    # Integrated into FastAPI (automatic):
    # - Starts when the tax-engine service starts
    # - Runs scraper every 24h (configurable via TAX_SCRAPE_INTERVAL_HOURS)
    # - First run is delayed by TAX_SCRAPE_INITIAL_DELAY_MINUTES after startup

    # Standalone (manual):
    python -m data.scheduler          # Run one scrape cycle now
    python -m data.scheduler --loop   # Run continuously with configured interval
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("tax_scheduler")

# Configuration via environment variables
SCRAPE_INTERVAL_HOURS = int(os.environ.get("TAX_SCRAPE_INTERVAL_HOURS", "24"))
INITIAL_DELAY_MINUTES = int(os.environ.get("TAX_SCRAPE_INITIAL_DELAY_MINUTES", "5"))
SCRAPE_ENABLED = os.environ.get("TAX_SCRAPE_ENABLED", "true").lower() == "true"


class TaxUpdateScheduler:
    """Schedules periodic tax regulation scraping and ingestion."""

    def __init__(
        self,
        interval_hours: int = SCRAPE_INTERVAL_HOURS,
        initial_delay_minutes: int = INITIAL_DELAY_MINUTES,
    ) -> None:
        self.interval_hours = interval_hours
        self.initial_delay_minutes = initial_delay_minutes
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Start the scheduler as a background asyncio task.

        Call this from FastAPI's startup/lifespan event.
        Safe to call multiple times (idempotent).
        """
        if not SCRAPE_ENABLED:
            logger.info("Tax scraper is disabled (TAX_SCRAPE_ENABLED=false)")
            return

        if self._task and not self._task.done():
            logger.warning("Scheduler already running, skipping start")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Tax update scheduler started (interval=%dh, initial_delay=%dm)",
            self.interval_hours,
            self.initial_delay_minutes,
        )

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Tax update scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        # Initial delay to let the service fully start
        logger.info(
            "Waiting %d minutes before first scrape...",
            self.initial_delay_minutes,
        )
        await asyncio.sleep(self.initial_delay_minutes * 60)

        while self._running:
            await self._run_one_cycle()

            # Wait for next cycle
            next_run = datetime.now(timezone.utc).strftime("%H:%M UTC")
            logger.info(
                "Next scrape in %d hours (last run: %s)",
                self.interval_hours,
                next_run,
            )
            await asyncio.sleep(self.interval_hours * 3600)

    async def _run_one_cycle(self) -> None:
        """Execute one scrape + ingest cycle."""
        logger.info("Starting tax regulation scrape cycle...")
        try:
            from data.scraper import TaxRegulationScraper, ingest_scraped_documents

            scraper = TaxRegulationScraper()
            documents = await scraper.scrape_all()

            if documents:
                logger.info("Found %d new/updated regulations", len(documents))
                counts = await ingest_scraped_documents(documents)
                logger.info(
                    "Ingestion complete: %d to DB, %d to vector store",
                    counts["database"],
                    counts["vector_store"],
                )
            else:
                logger.info("No new regulations found")

        except Exception:
            logger.exception("Tax scrape cycle failed")

    async def run_once(self) -> None:
        """Run a single scrape cycle immediately (for manual/CLI use)."""
        await self._run_one_cycle()


# Singleton instance for use in FastAPI startup
tax_scheduler = TaxUpdateScheduler()


async def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Tax regulation update scheduler")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scheduler = TaxUpdateScheduler(initial_delay_minutes=0)

    if args.loop:
        scheduler.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            await scheduler.stop()
    else:
        await scheduler.run_once()


if __name__ == "__main__":
    asyncio.run(main())
