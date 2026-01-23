"""Pydantic schemas for API request and response models.

This module defines the data transfer objects (DTOs) used by the REST API
endpoints for serializing session data, transcripts, latency measurements,
and freeze events.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


class TranscriptResponse(BaseModel):
    """Response model for a single transcript entry.

    Attributes:
        id: Unique identifier for the transcript.
        role: Who sent the message ('user' or 'assistant').
        content: The text content of the message.
        timestamp: When the message was recorded.
        turn_number: Sequential number of this turn in the conversation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    timestamp: datetime
    turn_number: int


class TurnLatencyResponse(BaseModel):
    """Response model for a turn latency measurement.

    Attributes:
        id: Unique identifier for the latency measurement.
        turn_number: Which conversation turn this measurement is for.
        latency_ms: Latency in milliseconds.
        was_interrupted: Whether the user interrupted the bot's response.
        created_at: When this measurement was recorded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    turn_number: int
    latency_ms: float
    was_interrupted: bool
    created_at: datetime


class FreezeEventResponse(BaseModel):
    """Response model for a freeze detection event.

    Attributes:
        id: Unique identifier for the freeze event.
        start_time_ms: When the freeze started (offset from session start).
        duration_ms: How long the freeze lasted.
        detected_at: When this freeze was detected/recorded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    start_time_ms: float
    duration_ms: float
    detected_at: datetime


class SessionSummary(BaseModel):
    """Summary response model for a session (used in list views).

    Provides a lightweight representation of a session without
    including related transcripts, latencies, or freeze events.

    Attributes:
        id: Unique identifier for the session.
        created_at: When the session started.
        ended_at: When the session ended (None if still active).
        status: Current state of the session.
        has_audio: Whether an audio recording exists for this session.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    ended_at: Optional[datetime]
    status: str
    audio_file_path: Optional[str] = None

    @computed_field
    @property
    def has_audio(self) -> bool:
        """Check if the session has an associated audio file.

        Returns:
            bool: True if audio_file_path is set, False otherwise.
        """
        return self.audio_file_path is not None


class SessionDetail(BaseModel):
    """Detailed response model for a session with all related data.

    Includes full session information along with transcripts,
    latency measurements, and freeze events.

    Attributes:
        id: Unique identifier for the session.
        created_at: When the session started.
        ended_at: When the session ended (None if still active).
        status: Current state of the session.
        audio_file_path: Path to the recorded audio file.
        transcripts: List of transcript entries for this session.
        turn_latencies: List of latency measurements for this session.
        freeze_events: List of freeze events detected during this session.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    ended_at: Optional[datetime]
    status: str
    audio_file_path: Optional[str]
    transcripts: List[TranscriptResponse]
    turn_latencies: List[TurnLatencyResponse]
    freeze_events: List[FreezeEventResponse]


class SessionListResponse(BaseModel):
    """Response model for paginated session list.

    Attributes:
        sessions: List of session summaries.
        total: Total number of sessions matching the query.
    """

    sessions: List[SessionSummary]
    total: int
