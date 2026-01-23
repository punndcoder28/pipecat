"""API module for FastAPI routes and endpoints.

This module exports the main API router which includes all session-related
endpoints for the voice agent recording UI backend.

Exports:
    - router: FastAPI APIRouter with session endpoints
"""

from backend.api.routes import router

__all__ = ["router"]
