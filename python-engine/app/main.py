"""
Main entry point for the Python Tax Engine service.
Runs both FastAPI (REST) and gRPC servers concurrently.
"""

import asyncio
import logging
import signal

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.routes import health, tax, portal
from app.grpc_server import serve_grpc

PORTAL_DIR = Path(__file__).resolve().parent / "portal"

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Tax Assistant Engine",
        description="AI-powered Vietnamese Tax Consultation Engine",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health.router)
    app.include_router(tax.router)
    app.include_router(portal.router)

    # Serve portal static files (CSS, JS)
    app.mount(
        "/portal/static",
        StaticFiles(directory=str(PORTAL_DIR / "static")),
        name="portal-static",
    )

    return app


app = create_app()


async def main() -> None:
    """Run both REST and gRPC servers."""
    logger.info(
        "Starting Tax Engine (env=%s, rest=%s:%d, grpc=%s:%d)",
        settings.environment,
        settings.rest_host,
        settings.rest_port,
        settings.grpc_host,
        settings.grpc_port,
    )

    # Start gRPC server
    grpc_server = await serve_grpc()

    # Start tax regulation update scheduler (background task)
    try:
        from data.scheduler import tax_scheduler
        tax_scheduler.start()
    except Exception:
        logger.warning("Tax update scheduler failed to start", exc_info=True)

    # Setup shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    # Start REST server
    config = uvicorn.Config(
        app,
        host=settings.rest_host,
        port=settings.rest_port,
        log_level="info" if not settings.debug else "debug",
    )
    rest_server = uvicorn.Server(config)

    # Run both servers
    async def run_rest():
        await rest_server.serve()

    async def wait_shutdown():
        await shutdown_event.wait()
        logger.info("Shutting down servers...")

        # Stop tax scheduler
        try:
            from data.scheduler import tax_scheduler
            await tax_scheduler.stop()
        except Exception:
            pass

        await grpc_server.stop(grace=5)
        rest_server.should_exit = True

    await asyncio.gather(run_rest(), wait_shutdown())
    logger.info("Tax Engine stopped.")


if __name__ == "__main__":
    asyncio.run(main())
