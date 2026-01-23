"""Main entry point for the Voice Agent Recording UI backend.

This module initializes and runs the FastAPI application with WebRTC
support for real-time voice agent interactions with recording capabilities.
"""

import argparse
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from loguru import logger
from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection

from backend.api import router as api_router
from backend.bot.pipeline import run_bot
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

    # Close all WebRTC connections
    if pcs_map:
        logger.info(f"Closing {len(pcs_map)} WebRTC connection(s)...")
        coros = [pc.disconnect() for pc in pcs_map.values()]
        await asyncio.gather(*coros)
        pcs_map.clear()
        logger.info("All WebRTC connections closed")

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

# Store WebRTC connections by pc_id
pcs_map: Dict[str, SmallWebRTCConnection] = {}

# ICE servers for WebRTC
ice_servers = [
    IceServer(urls="stun:stun.l.google.com:19302"),
]

# Configure CORS middleware for development
# In production, restrict origins to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Include the API router for session endpoints
app.include_router(api_router)

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


@app.post("/api/offer")
async def offer(request: dict, background_tasks: BackgroundTasks):
    """WebRTC signaling endpoint for establishing peer connections.

    Handles SDP offer/answer exchange for WebRTC connections. Supports
    both new connections and renegotiation of existing connections.

    Args:
        request: Dictionary containing 'sdp', 'type', and optionally
            'pc_id' and 'restart_pc' fields.
        background_tasks: FastAPI background tasks for running the bot.

    Returns:
        dict: SDP answer with pc_id for the WebRTC connection.
    """
    pc_id = request.get("pc_id")

    if pc_id and pc_id in pcs_map:
        pipecat_connection = pcs_map[pc_id]
        logger.info(f"Reusing existing connection for pc_id: {pc_id}")
        await pipecat_connection.renegotiate(
            sdp=request["sdp"],
            type=request["type"],
            restart_pc=request.get("restart_pc", False),
        )
    else:
        pipecat_connection = SmallWebRTCConnection(ice_servers)
        await pipecat_connection.initialize(sdp=request["sdp"], type=request["type"])

        @pipecat_connection.event_handler("closed")
        async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
            logger.info(f"Discarding peer connection for pc_id: {webrtc_connection.pc_id}")
            pcs_map.pop(webrtc_connection.pc_id, None)

        # Run the bot with the WebRTC connection
        background_tasks.add_task(run_bot, pipecat_connection)

    answer = pipecat_connection.get_answer()
    # Update the peer connection inside the map
    pcs_map[answer["pc_id"]] = pipecat_connection

    return answer


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
