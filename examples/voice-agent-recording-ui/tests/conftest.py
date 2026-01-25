"""Pytest configuration and shared fixtures for backend tests."""

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Session, SessionStatus, Transcript, TurnLatency, FreezeEvent


# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create an async engine for testing."""
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
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create an async session for testing."""
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def sample_session(async_session: AsyncSession) -> Session:
    """Create a sample session for testing."""
    session = Session(
        id=uuid.uuid4(),
        status=SessionStatus.COMPLETED,
        created_at=datetime.utcnow() - timedelta(hours=1),
        ended_at=datetime.utcnow(),
        audio_file_path="/tmp/test_audio.wav",
    )
    async_session.add(session)
    await async_session.commit()
    await async_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def sample_session_with_data(async_session: AsyncSession) -> Session:
    """Create a sample session with transcripts, latencies, and freeze events."""
    session_id = uuid.uuid4()
    session = Session(
        id=session_id,
        status=SessionStatus.COMPLETED,
        created_at=datetime.utcnow() - timedelta(hours=1),
        ended_at=datetime.utcnow(),
        audio_file_path="/tmp/test_audio.wav",
    )
    async_session.add(session)
    await async_session.flush()

    # Add transcripts
    transcripts = [
        Transcript(
            session_id=session_id,
            role="user",
            content="Hello, how are you?",
            timestamp=datetime.utcnow() - timedelta(minutes=5),
            turn_number=1,
        ),
        Transcript(
            session_id=session_id,
            role="assistant",
            content="I'm doing well, thank you! How can I help you today?",
            timestamp=datetime.utcnow() - timedelta(minutes=4),
            turn_number=2,
        ),
    ]
    for t in transcripts:
        async_session.add(t)

    # Add turn latencies
    latency = TurnLatency(
        session_id=session_id,
        turn_number=1,
        latency_ms=1250.5,
        was_interrupted=False,
    )
    async_session.add(latency)

    # Add freeze event
    freeze = FreezeEvent(
        session_id=session_id,
        start_time_ms=15000,
        duration_ms=3500,
    )
    async_session.add(freeze)

    await async_session.commit()
    await async_session.refresh(session)
    return session


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    from backend.config import Settings, STTProvider, LLMProvider, TTSProvider

    return Settings(
        stt_provider=STTProvider.DEEPGRAM,
        llm_provider=LLMProvider.GOOGLE,
        tts_provider=TTSProvider.CARTESIA,
        deepgram_api_key="test_deepgram_key",
        google_api_key="test_google_key",
        cartesia_api_key="test_cartesia_key",
        openai_api_key="test_openai_key",
        database_url=TEST_DATABASE_URL,
        host="localhost",
        port=8000,
    )


@pytest.fixture
def temp_env_vars():
    """Fixture to temporarily set environment variables."""
    original_env = os.environ.copy()

    def _set_env(**kwargs):
        for key, value in kwargs.items():
            os.environ[key] = value

    yield _set_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
