"""Tests for API schemas."""

import uuid
from datetime import datetime

import pytest

from backend.api.schemas import (
    FreezeEventResponse,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
    TranscriptResponse,
    TurnLatencyResponse,
)


class TestTranscriptResponse:
    """Tests for TranscriptResponse schema."""

    def test_valid_transcript(self):
        """Test valid transcript creation."""
        transcript = TranscriptResponse(
            id=uuid.uuid4(),
            role="user",
            content="Hello, how are you?",
            timestamp=datetime.utcnow(),
            turn_number=1,
        )

        assert transcript.role == "user"
        assert transcript.content == "Hello, how are you?"
        assert transcript.turn_number == 1

    def test_transcript_roles(self):
        """Test transcript accepts different roles."""
        for role in ["user", "assistant"]:
            transcript = TranscriptResponse(
                id=uuid.uuid4(),
                role=role,
                content="Test content",
                timestamp=datetime.utcnow(),
                turn_number=1,
            )
            assert transcript.role == role

    def test_from_orm_mode(self):
        """Test from_attributes mode is enabled."""
        assert TranscriptResponse.model_config.get("from_attributes") is True


class TestTurnLatencyResponse:
    """Tests for TurnLatencyResponse schema."""

    def test_valid_latency(self):
        """Test valid latency creation."""
        latency = TurnLatencyResponse(
            id=uuid.uuid4(),
            turn_number=1,
            latency_ms=1250.5,
            was_interrupted=False,
            created_at=datetime.utcnow(),
        )

        assert latency.turn_number == 1
        assert latency.latency_ms == 1250.5
        assert latency.was_interrupted is False

    def test_interrupted_turn(self):
        """Test interrupted turn."""
        latency = TurnLatencyResponse(
            id=uuid.uuid4(),
            turn_number=2,
            latency_ms=500.0,
            was_interrupted=True,
            created_at=datetime.utcnow(),
        )

        assert latency.was_interrupted is True


class TestFreezeEventResponse:
    """Tests for FreezeEventResponse schema."""

    def test_valid_freeze_event(self):
        """Test valid freeze event creation."""
        freeze = FreezeEventResponse(
            id=uuid.uuid4(),
            start_time_ms=15000.0,
            duration_ms=3500.0,
            detected_at=datetime.utcnow(),
        )

        assert freeze.start_time_ms == 15000.0
        assert freeze.duration_ms == 3500.0

    def test_freeze_event_zero_start(self):
        """Test freeze event at start of session."""
        freeze = FreezeEventResponse(
            id=uuid.uuid4(),
            start_time_ms=0.0,
            duration_ms=1000.0,
            detected_at=datetime.utcnow(),
        )

        assert freeze.start_time_ms == 0.0


class TestSessionSummary:
    """Tests for SessionSummary schema."""

    def test_valid_session_summary(self):
        """Test valid session summary creation."""
        summary = SessionSummary(
            id=uuid.uuid4(),
            created_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            status="completed",
            audio_file_path="/path/to/audio.wav",
        )

        assert summary.status == "completed"
        assert summary.has_audio is True

    def test_has_audio_true_with_path(self):
        """Test has_audio is True when path exists."""
        summary = SessionSummary(
            id=uuid.uuid4(),
            created_at=datetime.utcnow(),
            ended_at=None,
            status="active",
            audio_file_path="/some/path.wav",
        )

        assert summary.has_audio is True

    def test_has_audio_false_without_path(self):
        """Test has_audio is False when path is None."""
        summary = SessionSummary(
            id=uuid.uuid4(),
            created_at=datetime.utcnow(),
            ended_at=None,
            status="active",
            audio_file_path=None,
        )

        assert summary.has_audio is False

    def test_active_session_no_end_time(self):
        """Test active session with no end time."""
        summary = SessionSummary(
            id=uuid.uuid4(),
            created_at=datetime.utcnow(),
            ended_at=None,
            status="active",
        )

        assert summary.ended_at is None
        assert summary.status == "active"

    def test_audio_file_path_excluded_from_json(self):
        """Test audio_file_path is excluded from JSON output."""
        summary = SessionSummary(
            id=uuid.uuid4(),
            created_at=datetime.utcnow(),
            ended_at=None,
            status="active",
            audio_file_path="/path/to/audio.wav",
        )

        json_data = summary.model_dump()
        assert "audio_file_path" not in json_data or json_data.get("audio_file_path") is None


class TestSessionDetail:
    """Tests for SessionDetail schema."""

    def test_valid_session_detail(self):
        """Test valid session detail creation."""
        session_id = uuid.uuid4()
        detail = SessionDetail(
            id=session_id,
            created_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            status="completed",
            audio_file_path="/path/to/audio.wav",
            transcripts=[],
            turn_latencies=[],
            freeze_events=[],
        )

        assert detail.id == session_id
        assert len(detail.transcripts) == 0
        assert len(detail.turn_latencies) == 0
        assert len(detail.freeze_events) == 0

    def test_session_detail_with_data(self):
        """Test session detail with related data."""
        session_id = uuid.uuid4()
        now = datetime.utcnow()

        transcript = TranscriptResponse(
            id=uuid.uuid4(),
            role="user",
            content="Hello",
            timestamp=now,
            turn_number=1,
        )

        latency = TurnLatencyResponse(
            id=uuid.uuid4(),
            turn_number=1,
            latency_ms=100.0,
            was_interrupted=False,
            created_at=now,
        )

        freeze = FreezeEventResponse(
            id=uuid.uuid4(),
            start_time_ms=5000.0,
            duration_ms=1000.0,
            detected_at=now,
        )

        detail = SessionDetail(
            id=session_id,
            created_at=now,
            ended_at=now,
            status="completed",
            audio_file_path=None,
            transcripts=[transcript],
            turn_latencies=[latency],
            freeze_events=[freeze],
        )

        assert len(detail.transcripts) == 1
        assert len(detail.turn_latencies) == 1
        assert len(detail.freeze_events) == 1


class TestSessionListResponse:
    """Tests for SessionListResponse schema."""

    def test_empty_list(self):
        """Test empty session list."""
        response = SessionListResponse(sessions=[], total=0)

        assert len(response.sessions) == 0
        assert response.total == 0

    def test_list_with_sessions(self):
        """Test list with sessions."""
        sessions = [
            SessionSummary(
                id=uuid.uuid4(),
                created_at=datetime.utcnow(),
                ended_at=datetime.utcnow(),
                status="completed",
            )
            for _ in range(3)
        ]

        response = SessionListResponse(sessions=sessions, total=10)

        assert len(response.sessions) == 3
        assert response.total == 10

    def test_pagination_scenario(self):
        """Test pagination scenario where total > returned."""
        sessions = [
            SessionSummary(
                id=uuid.uuid4(),
                created_at=datetime.utcnow(),
                ended_at=datetime.utcnow(),
                status="completed",
            )
            for _ in range(10)
        ]

        response = SessionListResponse(sessions=sessions, total=100)

        assert len(response.sessions) == 10
        assert response.total == 100
