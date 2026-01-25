"""Main entry point for the Voice Agent Recording UI backend.

This module initializes and runs the FastAPI application with WebRTC
support for real-time voice agent interactions with recording capabilities.
"""

import argparse
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request
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


# OpenAPI tags for endpoint organization
OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Health check endpoints for monitoring and load balancers.",
    },
    {
        "name": "sessions",
        "description": "Session management endpoints for listing and retrieving recorded sessions.",
    },
    {
        "name": "webrtc",
        "description": "WebRTC signaling endpoints for establishing voice connections.",
    },
]

# Create FastAPI application with lifespan management
app = FastAPI(
    title="Voice Agent Recording UI",
    description="""
## Overview

Backend API for voice agent interactions with recording capabilities. This service provides:

- **Real-time voice conversations** via WebRTC with a Pipecat-powered voice agent
- **Session recording** with audio capture and transcript storage
- **Turn latency tracking** for performance monitoring
- **Freeze event detection** for identifying bot response issues

## Architecture

The voice pipeline uses:
- **Deepgram** for speech-to-text (STT)
- **Google Gemini** for language model processing (LLM)
- **Cartesia** for text-to-speech (TTS) with low latency
- **Silero VAD** with smart turn detection for natural conversation flow

## Getting Started

1. Start a voice session via the WebRTC client at `/client/`
2. Retrieve recorded sessions via the `/api/sessions` endpoints
3. Stream audio recordings via `/api/sessions/{id}/audio`
    """,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    contact={
        "name": "Voice Agent Recording UI",
    },
    license_info={
        "name": "BSD 2-Clause License",
    },
)

# Store WebRTC connections by pc_id
pcs_map: Dict[str, SmallWebRTCConnection] = {}

# Store active sessions for the prebuilt UI
active_sessions: Dict[str, Dict[str, Any]] = {}

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


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect root path to the client UI.

    Returns:
        RedirectResponse: Redirect to /client/ path.
    """
    return RedirectResponse(url="/client/")


@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    response_description="Returns healthy status if service is running",
)
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring and load balancers.

    Returns a simple status object indicating the service is operational.
    Use this endpoint for:
    - Kubernetes liveness/readiness probes
    - Load balancer health checks
    - Monitoring systems
    """
    return {"status": "healthy"}


@app.post(
    "/api/offer",
    tags=["webrtc"],
    summary="WebRTC SDP offer/answer exchange",
    response_description="SDP answer with peer connection ID",
)
async def offer(request: dict, background_tasks: BackgroundTasks):
    """WebRTC signaling endpoint for establishing peer connections.

    Handles SDP offer/answer exchange for WebRTC connections. Supports
    both new connections and renegotiation of existing connections.

    **Request body:**
    - `sdp` (str): The SDP offer from the client
    - `type` (str): The SDP type (typically "offer")
    - `pc_id` (str, optional): Existing peer connection ID for renegotiation
    - `restart_pc` (bool, optional): Whether to restart the peer connection

    **Response:**
    - `sdp` (str): The SDP answer from the server
    - `type` (str): The SDP type ("answer")
    - `pc_id` (str): The peer connection ID for subsequent requests
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


@app.post(
    "/start",
    tags=["webrtc"],
    summary="Initialize a new WebRTC session",
    response_description="Session ID and optional ICE configuration",
)
async def start_session(request: Request):
    """Initialize a new WebRTC session for the prebuilt UI.

    This endpoint creates a new session and returns configuration needed
    to establish a WebRTC connection. It mimics Pipecat Cloud's /start
    endpoint for compatibility with the SmallWebRTCPrebuiltUI component.

    **Request body (optional):**
    - `enableDefaultIceServers` (bool): If true, includes default STUN servers

    **Response:**
    - `sessionId` (str): Unique identifier for the session
    - `iceConfig` (object, optional): ICE server configuration if requested
    """
    try:
        request_data = await request.json()
        logger.debug(f"Received start request: {request_data}")
    except Exception:
        request_data = {}

    # Generate a new session ID
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = request_data

    result = {"sessionId": session_id}

    # Include ICE servers if requested
    if request_data.get("enableDefaultIceServers"):
        result["iceConfig"] = {
            "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
        }

    logger.info(f"Started new session: {session_id}")
    return result


@app.api_route(
    "/sessions/{session_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["webrtc"],
    summary="Session-scoped request proxy",
    include_in_schema=False,  # Hide from docs as it's an internal endpoint
)
async def proxy_session_request(
    session_id: str,
    path: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Proxy requests to session-specific endpoints.

    This internal endpoint handles the prebuilt UI's session-based WebRTC
    signaling by proxying requests to the appropriate handlers.
    """
    if session_id not in active_sessions:
        return {"error": "Invalid or expired session_id"}, 404

    if path.endswith("api/offer"):
        try:
            request_data = await request.json()
            return await offer(request_data, background_tasks)
        except Exception as e:
            logger.error(f"Failed to handle session offer: {e}")
            return {"error": "Invalid WebRTC request"}, 400

    logger.debug(f"Unhandled session path: {path}")
    return {"status": "ok"}


# Mount the SmallWebRTC prebuilt UI at /client (must be after route definitions)
app.mount("/client", SmallWebRTCPrebuiltUI)


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
