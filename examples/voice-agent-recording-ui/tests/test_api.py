"""Tests for API routes."""

import os
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Session, SessionStatus, Transcript, TurnLatency, FreezeEvent


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_db_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine):
    """Create a test database session."""
    async_session_maker = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def test_client(test_db_engine):
    """Create a test client with mocked database."""
    from backend.main import app
    from backend.db import get_db

    async_session_maker = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_sessions(test_db_session: AsyncSession):
    """Create sample sessions for testing."""
    sessions = []
    for i in range(5):
        session = Session(
            id=uuid.uuid4(),
            status=SessionStatus.COMPLETED if i < 3 else SessionStatus.ACTIVE,
            created_at=datetime.utcnow() - timedelta(hours=i),
            ended_at=datetime.utcnow() if i < 3 else None,
            audio_file_path=f"/tmp/audio_{i}.wav" if i < 2 else None,
        )
        test_db_session.add(session)
        sessions.append(session)

    await test_db_session.commit()
    return sessions


class TestListSessions:
    """Tests for GET /api/sessions endpoint."""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, test_client: AsyncClient):
        """Test listing sessions when database is empty."""
        response = await test_client.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()
        assert data["sessions"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_sessions_with_data(
        self, test_client: AsyncClient, sample_sessions
    ):
        """Test listing sessions with data."""
        response = await test_client.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 5
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_sessions_pagination(
        self, test_client: AsyncClient, sample_sessions
    ):
        """Test pagination parameters."""
        response = await test_client.get("/api/sessions?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_sessions_pagination_offset(
        self, test_client: AsyncClient, sample_sessions
    ):
        """Test pagination with offset."""
        response = await test_client.get("/api/sessions?limit=2&offset=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_status(
        self, test_client: AsyncClient, sample_sessions
    ):
        """Test filtering by status."""
        response = await test_client.get("/api/sessions?status=completed")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        for session in data["sessions"]:
            assert session["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_sessions_filter_active(
        self, test_client: AsyncClient, sample_sessions
    ):
        """Test filtering active sessions."""
        response = await test_client.get("/api/sessions?status=active")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for session in data["sessions"]:
            assert session["status"] == "active"

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_status(self, test_client: AsyncClient):
        """Test invalid status filter."""
        response = await test_client.get("/api/sessions?status=invalid")

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_sessions_limit_validation(self, test_client: AsyncClient):
        """Test limit parameter validation."""
        # Limit above maximum
        response = await test_client.get("/api/sessions?limit=200")
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_sessions_has_audio_field(
        self, test_client: AsyncClient, sample_sessions
    ):
        """Test has_audio computed field."""
        response = await test_client.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()

        # Find sessions with and without audio
        has_audio_sessions = [s for s in data["sessions"] if s["has_audio"]]
        no_audio_sessions = [s for s in data["sessions"] if not s["has_audio"]]

        assert len(has_audio_sessions) >= 1
        assert len(no_audio_sessions) >= 1


class TestGetSession:
    """Tests for GET /api/sessions/{session_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, test_client: AsyncClient):
        """Test getting non-existent session."""
        fake_id = uuid.uuid4()
        response = await test_client.get(f"/api/sessions/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_session_success(
        self, test_client: AsyncClient, test_db_session: AsyncSession
    ):
        """Test getting session details."""
        # Create a session with related data
        session_id = uuid.uuid4()
        session = Session(
            id=session_id,
            status=SessionStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(hours=1),
            ended_at=datetime.utcnow(),
            audio_file_path="/tmp/test.wav",
        )
        test_db_session.add(session)

        # Add transcript
        transcript = Transcript(
            session_id=session_id,
            role="user",
            content="Hello",
            timestamp=datetime.utcnow(),
            turn_number=1,
        )
        test_db_session.add(transcript)

        # Add turn latency
        latency = TurnLatency(
            session_id=session_id,
            turn_number=1,
            latency_ms=100.0,
            was_interrupted=False,
        )
        test_db_session.add(latency)

        # Add freeze event
        freeze = FreezeEvent(
            session_id=session_id,
            start_time_ms=5000,
            duration_ms=1000,
        )
        test_db_session.add(freeze)

        await test_db_session.commit()

        # Get session
        response = await test_client.get(f"/api/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(session_id)
        assert len(data["transcripts"]) == 1
        assert len(data["turn_latencies"]) == 1
        assert len(data["freeze_events"]) == 1

    @pytest.mark.asyncio
    async def test_get_session_invalid_uuid(self, test_client: AsyncClient):
        """Test getting session with invalid UUID."""
        response = await test_client.get("/api/sessions/not-a-uuid")

        assert response.status_code == 422  # Validation error


class TestGetSessionAudio:
    """Tests for GET /api/sessions/{session_id}/audio endpoint."""

    @pytest.mark.asyncio
    async def test_get_audio_session_not_found(self, test_client: AsyncClient):
        """Test getting audio for non-existent session."""
        fake_id = uuid.uuid4()
        response = await test_client.get(f"/api/sessions/{fake_id}/audio")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_audio_no_audio_file(
        self, test_client: AsyncClient, test_db_session: AsyncSession
    ):
        """Test getting audio when no file exists."""
        session_id = uuid.uuid4()
        session = Session(
            id=session_id,
            status=SessionStatus.COMPLETED,
            created_at=datetime.utcnow(),
            audio_file_path=None,  # No audio
        )
        test_db_session.add(session)
        await test_db_session.commit()

        response = await test_client.get(f"/api/sessions/{session_id}/audio")

        assert response.status_code == 404
        assert "No audio file" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_audio_file_missing_on_disk(
        self, test_client: AsyncClient, test_db_session: AsyncSession
    ):
        """Test getting audio when file doesn't exist on disk."""
        session_id = uuid.uuid4()
        session = Session(
            id=session_id,
            status=SessionStatus.COMPLETED,
            created_at=datetime.utcnow(),
            audio_file_path="/nonexistent/path/audio.wav",
        )
        test_db_session.add(session)
        await test_db_session.commit()

        response = await test_client.get(f"/api/sessions/{session_id}/audio")

        assert response.status_code == 404
        assert "not found on disk" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_audio_success(
        self, test_client: AsyncClient, test_db_session: AsyncSession
    ):
        """Test successful audio file retrieval."""
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".wav", delete=False
        ) as f:
            # Write a minimal WAV header
            f.write(b"RIFF")
            f.write((36).to_bytes(4, "little"))  # File size - 8
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write((16).to_bytes(4, "little"))  # Chunk size
            f.write((1).to_bytes(2, "little"))  # Audio format (PCM)
            f.write((1).to_bytes(2, "little"))  # Num channels
            f.write((16000).to_bytes(4, "little"))  # Sample rate
            f.write((32000).to_bytes(4, "little"))  # Byte rate
            f.write((2).to_bytes(2, "little"))  # Block align
            f.write((16).to_bytes(2, "little"))  # Bits per sample
            f.write(b"data")
            f.write((0).to_bytes(4, "little"))  # Data size
            temp_path = f.name

        try:
            session_id = uuid.uuid4()
            session = Session(
                id=session_id,
                status=SessionStatus.COMPLETED,
                created_at=datetime.utcnow(),
                audio_file_path=temp_path,
            )
            test_db_session.add(session)
            await test_db_session.commit()

            response = await test_client.get(f"/api/sessions/{session_id}/audio")

            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/wav"
        finally:
            os.unlink(temp_path)


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    @pytest.mark.asyncio
    async def test_openapi_schema_available(self, test_client: AsyncClient):
        """Test OpenAPI schema is accessible."""
        response = await test_client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

    @pytest.mark.asyncio
    async def test_docs_endpoint(self, test_client: AsyncClient):
        """Test /docs endpoint is accessible."""
        response = await test_client.get("/docs")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_redoc_endpoint(self, test_client: AsyncClient):
        """Test /redoc endpoint is accessible."""
        response = await test_client.get("/redoc")

        assert response.status_code == 200
