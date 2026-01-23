"""Main entry point for the Voice Agent Recording UI backend.

This module initializes and runs the FastAPI application with WebRTC
support for real-time voice agent interactions with recording capabilities.
"""

import argparse
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from loguru import logger
from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

from backend.config import get_settings
from backend.db import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events.

    Handles startup and shutdown operations for the FastAPI application,
    including database initialization and cleanup.

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control returns to the application after startup.
    """
    # Startup
    logger.info("Starting Voice Agent Recording UI backend...")

    # Validate API keys
    settings = get_settings()
    missing_keys = settings.validate_required_keys()
    if missing_keys:
        logger.warning(
            f"Missing API keys: {', '.join(missing_keys)}. "
            "Some features may not work correctly."
        )

    # Initialize database
    await init_db()
    logger.info("Database initialized successfully")

    logger.info("Voice Agent Recording UI backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Voice Agent Recording UI backend...")
    await close_db()
    logger.info("Database connections closed")
    logger.info("Voice Agent Recording UI backend shutdown complete")


# Create FastAPI application with lifespan management
app = FastAPI(
    title="Voice Agent Recording UI",
    description="Backend API for voice agent interactions with recording capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS middleware for development
# In production, restrict origins to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Mount the SmallWebRTC prebuilt UI at /client
app.mount("/client", SmallWebRTCPrebuiltUI())


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect root path to the client UI.

    Returns:
        RedirectResponse: Redirect to /client/ path.
    """
    return RedirectResponse(url="/client/")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring and load balancers.

    Returns:
        dict: Health status of the application.
    """
    return {"status": "healthy"}


def main() -> None:
    """Main entry point for running the application.

    Parses command-line arguments for host and port configuration,
    falling back to settings from configuration file.
    """
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Voice Agent Recording UI Backend Server"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.host,
        help=f"Host address to bind to (default: {settings.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help=f"Port number to listen on (default: {settings.port})",
    )

    args = parser.parse_args()

    logger.info(f"Starting server on {args.host}:{args.port}")

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
