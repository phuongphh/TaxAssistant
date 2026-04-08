"""
Tax regulation scraper for Vietnamese tax law updates.

Scrapes thuvienphapluat.vn and other official sources to detect
new/updated tax regulations and ingest them into the system.

Usage:
    python -m data.scraper                    # Check for updates and ingest
    python -m data.scraper --dry-run          # Preview without writing
    python -m data.scraper --category pit     # Only check PIT regulations
    python -m data.scraper --since 2025-01-01 # Only docs after this date
"""

import asyncio
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tax_scraper")

SEED_DIR = Path(__file__).resolve().parent / "seed"

# Sources to scrape for tax regulation updates
TAX_SOURCES = [
    {
        "name": "Thư viện Pháp luật - Thuế TNCN",
        "url": "https://thuvienphapluat.vn/page/tim-van-ban.aspx?keyword=thu%E1%BA%BF+thu+nh%E1%BA%ADp+c%C3%A1+nh%C3%A2n&area=2&type=0&match=True&eff_date=&pub_date=&org=0",
        "category": "pit",
    },
    {
        "name": "Thư viện Pháp luật - Thuế GTGT",
        "url": "https://thuvienphapluat.vn/page/tim-van-ban.aspx?keyword=thu%E1%BA%BF+gi%C3%A1+tr%E1%BB%8B+gia+t%C4%83ng&area=2&type=0&match=True&eff_date=&pub_date=&org=0",
        "category": "vat",
    },
    {
        "name": "Thư viện Pháp luật - Thuế TNDN",
        "url": "https://thuvienphapluat.vn/page/tim-van-ban.aspx?keyword=thu%E1%BA%BF+thu+nh%E1%BA%ADp+doanh+nghi%E1%BB%87p&area=2&type=0&match=True&eff_date=&pub_date=&org=0",
        "category": "cit",
    },
    {
        "name": "Tổng cục Thuế - Chính sách mới",
        "url": "https://www.gdt.gov.vn/wps/portal/home/cs-moi",
        "category": "general",
    },
]

# Known document patterns for Vietnamese legal documents
DOC_NUMBER_PATTERN = re.compile(
    r"(\d+/\d{4}/(?:QH\d+|NĐ-CP|TT-BTC|UBTVQH\d+|QĐ-BTC|NQ-CP))"
)

# User agent for polite scraping
HEADERS = {
    "User-Agent": "TaxAssistant/1.0 (tax-regulation-updater; +https://github.com/TaxAssistant)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


class TaxRegulationScraper:
    """Scrapes Vietnamese tax regulation websites for new/updated documents."""

    def __init__(self, rate_limit_seconds: float = 2.0) -> None:
        self.rate_limit = rate_limit_seconds
        self._seen_hashes: set[str] = set()
        self._load_existing_hashes()

    def _load_existing_hashes(self) -> None:
        """Load content hashes of existing seed documents to detect changes."""
        for json_file in SEED_DIR.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    docs = json.load(f)
                for doc in docs:
                    content_hash = hashlib.sha256(
                        doc.get("content", "").encode()
                    ).hexdigest()
                    self._seen_hashes.add(content_hash)
            except (json.JSONDecodeError, KeyError):
                continue

    async def scrape_all(
        self,
        category_filter: str | None = None,
        since_date: str | None = None,
    ) -> list[dict]:
        """Scrape all configured sources for new tax regulations.

        Args:
            category_filter: Only scrape sources for this category (pit, vat, cit).
            since_date: Only return documents with effective_date after this (YYYY-MM-DD).

        Returns:
            List of new regulation documents found.
        """
        new_docs: list[dict] = []

        sources = TAX_SOURCES
        if category_filter:
            sources = [s for s in sources if s["category"] == category_filter]

        async with httpx.AsyncClient(
            headers=HEADERS, timeout=30.0, follow_redirects=True
        ) as client:
            for source in sources:
                logger.info("Scraping: %s", source["name"])
                try:
                    docs = await self._scrape_source(client, source)
                    if since_date:
                        docs = [
                            d for d in docs
                            if d.get("effective_date", "") >= since_date
                        ]
                    new_docs.extend(docs)
                except Exception as e:
                    logger.error("Failed to scrape %s: %s", source["name"], e)

                # Rate limit between sources
                await asyncio.sleep(self.rate_limit)

        # Deduplicate by document_number
        seen_numbers: set[str] = set()
        unique_docs = []
        for doc in new_docs:
            if doc["document_number"] not in seen_numbers:
                seen_numbers.add(doc["document_number"])
                unique_docs.append(doc)

        logger.info("Found %d new/updated regulations total", len(unique_docs))
        return unique_docs

    async def _scrape_source(
        self, client: httpx.AsyncClient, source: dict
    ) -> list[dict]:
        """Scrape a single source URL for regulation documents."""
        docs: list[dict] = []

        try:
            response = await client.get(source["url"])
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("HTTP error fetching %s: %s", source["url"], e)
            return docs

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for document links - common patterns on thuvienphapluat.vn
        doc_links = self._extract_document_links(soup, source["url"])
        logger.info("Found %d document links from %s", len(doc_links), source["name"])

        for link_info in doc_links[:10]:  # Limit to 10 most recent per source
            try:
                doc = await self._fetch_document(client, link_info, source["category"])
                if doc and self._is_new_document(doc):
                    docs.append(doc)
                    logger.info(
                        "New document: %s - %s", doc["document_number"], doc["title"][:60]
                    )
            except Exception as e:
                logger.warning("Failed to fetch document %s: %s", link_info.get("url"), e)

            await asyncio.sleep(self.rate_limit)

        return docs

    def _extract_document_links(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict[str, str]]:
        """Extract document links from a search results page."""
        links: list[dict[str, str]] = []

        # Pattern 1: thuvienphapluat.vn search results
        for item in soup.select(".nq-item a, .content-area a, .search-result a"):
            href = item.get("href", "")
            title = item.get_text(strip=True)
            if href and title and len(title) > 10:
                full_url = urljoin(base_url, href)
                if "thuvienphapluat.vn/van-ban" in full_url:
                    links.append({"url": full_url, "title": title})

        # Pattern 2: Generic document list pages
        if not links:
            for item in soup.select("a[href*='van-ban'], a[href*='phap-luat']"):
                href = item.get("href", "")
                title = item.get_text(strip=True)
                if href and title and len(title) > 10:
                    full_url = urljoin(base_url, href)
                    links.append({"url": full_url, "title": title})

        return links

    async def _fetch_document(
        self, client: httpx.AsyncClient, link_info: dict, category: str
    ) -> dict | None:
        """Fetch and parse a single regulation document page."""
        try:
            response = await client.get(link_info["url"])
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract document number from content
        page_text = soup.get_text()
        doc_number_match = DOC_NUMBER_PATTERN.search(page_text)
        if not doc_number_match:
            doc_number_match = DOC_NUMBER_PATTERN.search(link_info.get("title", ""))
        if not doc_number_match:
            return None

        doc_number = doc_number_match.group(1)

        # Extract title
        title_tag = soup.select_one("h1, .doc-title, .title")
        title = title_tag.get_text(strip=True) if title_tag else link_info["title"]

        # Extract main content
        content_area = soup.select_one(
            ".doc-content, .content-area, .van-ban-content, article"
        )
        content = content_area.get_text(strip=True) if content_area else ""

        if len(content) < 100:
            return None

        # Try to extract effective date
        effective_date = self._extract_effective_date(page_text)

        return {
            "document_number": doc_number,
            "title": title[:200],
            "category": category,
            "effective_date": effective_date,
            "source_url": link_info["url"],
            "content": content[:5000],  # Limit content length
        }

    def _extract_effective_date(self, text: str) -> str:
        """Try to extract effective date from document text."""
        patterns = [
            r"có hiệu lực (?:thi hành )?(?:kể )?từ (?:ngày )?(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
            r"hiệu lực.*?(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
            r"áp dụng từ.*?(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                day, month, year = match.groups()
                try:
                    return f"{year}-{int(month):02d}-{int(day):02d}"
                except (ValueError, IndexError):
                    continue
        return ""

    def _is_new_document(self, doc: dict) -> bool:
        """Check if this document is new (not already in seed data)."""
        content_hash = hashlib.sha256(doc["content"].encode()).hexdigest()
        if content_hash in self._seen_hashes:
            return False
        self._seen_hashes.add(content_hash)
        return True


async def ingest_scraped_documents(documents: list[dict]) -> dict[str, int]:
    """Ingest scraped documents into PostgreSQL and ChromaDB.

    Returns dict with counts: {"database": N, "vector_store": M}.
    """
    from data.seed_loader import seed_database, seed_vector_store

    counts = {"database": 0, "vector_store": 0}

    if not documents:
        logger.info("No documents to ingest.")
        return counts

    # Save to seed files for persistence
    _append_to_seed_files(documents)

    # Ingest into database
    try:
        counts["database"] = await seed_database(documents)
        logger.info("Ingested %d documents into PostgreSQL", counts["database"])
    except Exception as e:
        logger.error("Failed to ingest into PostgreSQL: %s", e)

    # Ingest into vector store
    try:
        counts["vector_store"] = await seed_vector_store(documents)
        logger.info("Indexed %d documents into ChromaDB", counts["vector_store"])
    except Exception as e:
        logger.error("Failed to index into ChromaDB: %s", e)

    return counts


def _append_to_seed_files(documents: list[dict]) -> None:
    """Append new documents to the appropriate seed JSON files."""
    category_file_map = {
        "pit": "pit_regulations.json",
        "vat": "vat_regulations.json",
        "cit": "cit_regulations.json",
        "license": "license_tax_regulations.json",
        "procedure": "procedure_regulations.json",
    }

    by_category: dict[str, list[dict]] = {}
    for doc in documents:
        cat = doc.get("category", "general")
        by_category.setdefault(cat, []).append(doc)

    for category, docs in by_category.items():
        filename = category_file_map.get(category)
        if not filename:
            filename = f"{category}_regulations.json"

        filepath = SEED_DIR / filename
        existing: list[dict] = []
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                existing = json.load(f)

        # Merge: update existing by document_number, append new
        existing_numbers = {d["document_number"] for d in existing}
        for doc in docs:
            if doc["document_number"] in existing_numbers:
                # Update existing
                for i, e in enumerate(existing):
                    if e["document_number"] == doc["document_number"]:
                        existing[i] = doc
                        break
            else:
                existing.append(doc)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        logger.info("Updated seed file %s (%d documents)", filename, len(existing))


async def main() -> None:
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args

    # Parse optional filters
    category_filter = None
    since_date = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--category" and i < len(sys.argv) - 1:
            category_filter = sys.argv[i + 1]
        if arg == "--since" and i < len(sys.argv) - 1:
            since_date = sys.argv[i + 1]

    scraper = TaxRegulationScraper()
    documents = await scraper.scrape_all(
        category_filter=category_filter,
        since_date=since_date,
    )

    if not documents:
        logger.info("No new regulations found.")
        return

    print(f"\nFound {len(documents)} new/updated regulations:")
    for doc in documents:
        print(f"  [{doc['category'].upper()}] {doc['document_number']}: {doc['title'][:60]}")
        if doc.get("effective_date"):
            print(f"    Effective: {doc['effective_date']}")

    if dry_run:
        logger.info("Dry run mode - no data written.")
        return

    counts = await ingest_scraped_documents(documents)
    logger.info(
        "Ingestion complete: %d to DB, %d to vector store",
        counts["database"],
        counts["vector_store"],
    )


if __name__ == "__main__":
    asyncio.run(main())
