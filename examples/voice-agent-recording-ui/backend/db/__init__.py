"""Database module for SQLAlchemy models and session management.

This module provides the database infrastructure for the voice agent
recording UI backend, including async SQLAlchemy setup and ORM models.

Exports:
    - Base: Declarative base class for ORM models
    - get_db: FastAPI dependency for database sessions
    - init_db: Function to initialize database tables
    - close_db: Function to close database connections
    - async_session_maker: Session factory for creating database sessions
    - engine: Async SQLAlchemy engine instance
    - Session: ORM model for conversation sessions
    - SessionStatus: Enum for session states
    - Transcript: ORM model for conversation messages
    - TurnLatency: ORM model for latency measurements
    - FreezeEvent: ORM model for freeze detection events
"""

from backend.db.database import (
    Base,
    async_session_maker,
    close_db,
    engine,
    get_db,
    init_db,
)
from backend.db.models import (
    FreezeEvent,
    Session,
    SessionStatus,
    Transcript,
    TurnLatency,
)


__all__ = [
    # Database infrastructure
    "Base",
    "get_db",
    "init_db",
    "close_db",
    "async_session_maker",
    "engine",
    # ORM models
    "Session",
    "SessionStatus",
    "Transcript",
    "TurnLatency",
    "FreezeEvent",
]
