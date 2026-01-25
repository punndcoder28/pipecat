"""Pydantic schemas for API request and response models.

This module defines the data transfer objects (DTOs) used by the REST API
endpoints for serializing session data, transcripts, latency measurements,
and freeze events.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class TranscriptResponse(BaseModel):
    """Response model for a single transcript entry."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "role": "user",
                "content": "Hello, how are you today?",
                "timestamp": "2024-01-15T10:30:00Z",
                "turn_number": 1,
            }
        },
    )

    id: UUID = Field(description="Unique identifier for the transcript")
    role: str = Field(description="Speaker role: 'user' or 'assistant'")
    content: str = Field(description="The text content of the message")
    timestamp: datetime = Field(description="When the message was recorded")
    turn_number: int = Field(description="Sequential turn number in the conversation")


class TurnLatencyResponse(BaseModel):
    """Response model for a turn latency measurement."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "turn_number": 1,
                "latency_ms": 1250.5,
                "was_interrupted": False,
                "created_at": "2024-01-15T10:30:05Z",
            }
        },
    )

    id: UUID = Field(description="Unique identifier for the latency measurement")
    turn_number: int = Field(description="Which conversation turn this measurement is for")
    latency_ms: float = Field(description="Response latency in milliseconds")
    was_interrupted: bool = Field(description="Whether the user interrupted the bot's response")
    created_at: datetime = Field(description="When this measurement was recorded")


class FreezeEventResponse(BaseModel):
    """Response model for a freeze detection event."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "start_time_ms": 15000.0,
                "duration_ms": 3500.0,
                "detected_at": "2024-01-15T10:30:18Z",
            }
        },
    )

    id: UUID = Field(description="Unique identifier for the freeze event")
    start_time_ms: float = Field(description="Freeze start time in ms (offset from session start)")
    duration_ms: float = Field(description="Duration of the freeze in milliseconds")
    detected_at: datetime = Field(description="When this freeze was detected/recorded")


class SessionSummary(BaseModel):
    """Summary response model for a session (used in list views)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-15T10:30:00Z",
                "ended_at": "2024-01-15T10:35:00Z",
                "status": "completed",
                "has_audio": True,
            }
        },
    )

    id: UUID = Field(description="Unique identifier for the session")
    created_at: datetime = Field(description="When the session started")
    ended_at: Optional[datetime] = Field(description="When the session ended (null if active)")
    status: str = Field(description="Session status: 'active', 'completed', or 'error'")
    audio_file_path: Optional[str] = Field(default=None, exclude=True)

    @computed_field
    @property
    def has_audio(self) -> bool:
        """Whether an audio recording exists for this session."""
        return self.audio_file_path is not None


class SessionDetail(BaseModel):
    """Detailed response model for a session with all related data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier for the session")
    created_at: datetime = Field(description="When the session started")
    ended_at: Optional[datetime] = Field(description="When the session ended (null if active)")
    status: str = Field(description="Session status: 'active', 'completed', or 'error'")
    audio_file_path: Optional[str] = Field(description="Path to the recorded audio file")
    transcripts: List[TranscriptResponse] = Field(description="Conversation transcripts")
    turn_latencies: List[TurnLatencyResponse] = Field(description="Turn latency measurements")
    freeze_events: List[FreezeEventResponse] = Field(description="Detected freeze events")


class SessionListResponse(BaseModel):
    """Response model for paginated session list."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessions": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "created_at": "2024-01-15T10:30:00Z",
                        "ended_at": "2024-01-15T10:35:00Z",
                        "status": "completed",
                        "has_audio": True,
                    }
                ],
                "total": 42,
            }
        },
    )

    sessions: List[SessionSummary] = Field(description="List of session summaries")
    total: int = Field(description="Total number of sessions matching the query")
