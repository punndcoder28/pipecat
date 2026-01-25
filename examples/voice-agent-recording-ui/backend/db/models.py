"""SQLAlchemy ORM models for the voice agent recording system.

This module defines the database schema for tracking:
- Conversation sessions with their audio recordings
- Transcripts of user and assistant messages
- Turn latency measurements for performance monitoring
- Freeze events for detecting audio/video issues
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class SessionStatus(str, enum.Enum):
    """Enumeration of possible session states.

    Attributes:
        ACTIVE: Session is currently in progress.
        COMPLETED: Session ended normally.
        ERROR: Session ended due to an error.
    """

    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Returns:
        datetime: Current UTC timestamp with timezone info.
    """
    return datetime.now(timezone.utc)


class Session(Base):
    """ORM model representing a voice conversation session.

    A session captures a complete conversation between a user and the voice
    agent, including metadata about timing, recording location, and status.

    Attributes:
        id: Unique identifier for the session.
        created_at: When the session started.
        ended_at: When the session ended (None if still active).
        audio_file_path: Path to the recorded audio file.
        status: Current state of the session.
        deleted_at: When the session was soft-deleted (None if not deleted).
        transcripts: Related transcript entries.
        turn_latencies: Related latency measurements.
        freeze_events: Related freeze detection events.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    audio_file_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status", native_enum=False),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    turn_latencies: Mapped[list["TurnLatency"]] = relationship(
        "TurnLatency",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    freeze_events: Mapped[list["FreezeEvent"]] = relationship(
        "FreezeEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return a string representation of the session."""
        return f"<Session(id={self.id}, status={self.status}, created_at={self.created_at})>"


class Transcript(Base):
    """ORM model representing a single message in a conversation.

    Each transcript entry captures one turn of dialogue, either from
    the user or the assistant, along with timing information.

    Attributes:
        id: Unique identifier for the transcript entry.
        session_id: Reference to the parent session.
        role: Who sent the message ('user' or 'assistant').
        content: The text content of the message.
        timestamp: When the message was recorded.
        turn_number: Sequential number of this turn in the conversation.
        session: Reference to the parent Session object.
    """

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="transcripts",
    )

    def __repr__(self) -> str:
        """Return a string representation of the transcript entry."""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Transcript(id={self.id}, role={self.role}, turn={self.turn_number}, content='{content_preview}')>"


class TurnLatency(Base):
    """ORM model for tracking response latency per conversation turn.

    Measures the time between when the user finishes speaking and when
    the bot starts responding, which is a key metric for conversation quality.

    Attributes:
        id: Unique identifier for the latency measurement.
        session_id: Reference to the parent session.
        turn_number: Which conversation turn this measurement is for.
        latency_ms: Latency in milliseconds.
        was_interrupted: Whether the user interrupted the bot's response.
        created_at: When this measurement was recorded.
        session: Reference to the parent Session object.
    """

    __tablename__ = "turn_latencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    was_interrupted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="turn_latencies",
    )

    def __repr__(self) -> str:
        """Return a string representation of the latency measurement."""
        return f"<TurnLatency(id={self.id}, turn={self.turn_number}, latency_ms={self.latency_ms}, interrupted={self.was_interrupted})>"


class FreezeEvent(Base):
    """ORM model for tracking detected freeze events during a session.

    Freeze events occur when the audio or video stream appears to stall,
    which can indicate network issues or processing bottlenecks.

    Attributes:
        id: Unique identifier for the freeze event.
        session_id: Reference to the parent session.
        start_time_ms: When the freeze started (offset from session start).
        duration_ms: How long the freeze lasted.
        detected_at: When this freeze was detected/recorded.
        session: Reference to the parent Session object.
    """

    __tablename__ = "freeze_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="freeze_events",
    )

    def __repr__(self) -> str:
        """Return a string representation of the freeze event."""
        return f"<FreezeEvent(id={self.id}, start_ms={self.start_time_ms}, duration_ms={self.duration_ms})>"
