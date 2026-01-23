"""Session recording functionality for the voice agent.

This module provides the SessionRecorder class that manages audio recording,
turn latency tracking, and transcript storage for voice agent sessions using
Pipecat's AudioBufferProcessor and TurnTrackingObserver. It handles capturing
stereo audio (user on left channel, bot on right channel), tracking conversation
turns, and storing session metadata in the database.
"""

import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from pipecat.observers.turn_tracking_observer import TurnTrackingObserver
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor

from backend.config import get_settings
from backend.db.models import Session, SessionStatus, Transcript, TurnLatency


class SessionRecorder:
    """Manages audio recording, turn latency tracking, and transcript storage.

    This class creates and manages an AudioBufferProcessor instance to capture
    audio from both the user and the bot during a conversation session. Audio
    is recorded in stereo format with the user on the left channel and the bot
    on the right channel.

    Additionally, it integrates a TurnTrackingObserver to monitor conversation
    turns and calculate latencies, and provides methods for storing transcripts
    in the database.

    Attributes:
        session_id: Unique identifier for the recording session.
        db_session: SQLAlchemy async session for database operations.
        sample_rate: Audio sample rate in Hz (default: 16000).
        num_channels: Number of audio channels (default: 2 for stereo).
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        db_session: AsyncSession,
        *,
        sample_rate: int = 16000,
        num_channels: int = 2,
    ) -> None:
        """Initialize the SessionRecorder.

        Args:
            session_id: Unique identifier for the recording session.
            db_session: SQLAlchemy async session for database operations.
            sample_rate: Audio sample rate in Hz. Defaults to 16000.
            num_channels: Number of audio channels. Defaults to 2 (stereo).
        """
        self._session_id = session_id
        self._db_session = db_session
        self._sample_rate = sample_rate
        self._num_channels = num_channels

        self._settings = get_settings()
        self._start_time: Optional[datetime] = None
        self._audio_data: bytearray = bytearray()
        self._session_record: Optional[Session] = None

        # Turn tracking state
        self._current_turn_number: int = 0
        self._turn_start_times: Dict[int, float] = {}

        # Create the AudioBufferProcessor with stereo output
        # User audio on left channel, bot audio on right channel
        self._audio_processor = AudioBufferProcessor(
            sample_rate=sample_rate,
            num_channels=num_channels,
            enable_turn_audio=True,
        )

        # Create the TurnTrackingObserver for monitoring conversation turns
        self._turn_observer = TurnTrackingObserver()

        # Register event handler for audio data
        self._audio_processor.event_handler("on_audio_data")(self._on_audio_data)

        # Register event handlers for turn tracking
        self._turn_observer.event_handler("on_turn_started")(self._on_turn_started)
        self._turn_observer.event_handler("on_turn_ended")(self._on_turn_ended)

        logger.info(
            f"SessionRecorder initialized for session {session_id} "
            f"(sample_rate={sample_rate}, num_channels={num_channels})"
        )

    @property
    def session_id(self) -> uuid.UUID:
        """Get the session ID.

        Returns:
            The unique identifier for this recording session.
        """
        return self._session_id

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate.

        Returns:
            The sample rate in Hz.
        """
        return self._sample_rate

    @property
    def num_channels(self) -> int:
        """Get the number of audio channels.

        Returns:
            The number of audio channels (1 for mono, 2 for stereo).
        """
        return self._num_channels

    @property
    def start_time(self) -> Optional[datetime]:
        """Get the session start timestamp.

        This timestamp can be used to calculate offsets for events like
        freeze events relative to the session start.

        Returns:
            The session start time, or None if the session hasn't started yet.
        """
        return self._start_time

    @property
    def current_turn_number(self) -> int:
        """Get the current turn number.

        Returns:
            The current turn number in the conversation.
        """
        return self._current_turn_number

    def get_processor(self) -> AudioBufferProcessor:
        """Get the AudioBufferProcessor instance.

        This processor should be added to the Pipecat pipeline to capture
        audio frames from both input (user) and output (bot) sources.

        Returns:
            The AudioBufferProcessor instance managed by this recorder.
        """
        return self._audio_processor

    def get_turn_observer(self) -> TurnTrackingObserver:
        """Get the TurnTrackingObserver instance.

        This observer should be attached to the Pipecat pipeline to track
        conversation turns and measure turn latencies.

        Returns:
            The TurnTrackingObserver instance managed by this recorder.
        """
        return self._turn_observer

    async def _on_audio_data(
        self,
        audio_data: bytes,
        sample_rate: int,
        num_channels: int,
    ) -> None:
        """Handle incoming audio data from the AudioBufferProcessor.

        This callback is invoked when the audio buffer is ready. It accumulates
        the audio data for later storage to a WAV file.

        Args:
            audio_data: The merged audio data (user + bot) as bytes.
            sample_rate: The sample rate of the audio data.
            num_channels: The number of channels in the audio data.
        """
        self._audio_data.extend(audio_data)
        logger.debug(
            f"Session {self._session_id}: Accumulated {len(audio_data)} bytes "
            f"(total: {len(self._audio_data)} bytes)"
        )

    async def _on_turn_started(
        self,
        observer: TurnTrackingObserver,
        turn_number: int,
    ) -> None:
        """Handle turn started events from the TurnTrackingObserver.

        Records the start time for the turn to calculate latency when the
        turn ends.

        Args:
            observer: The TurnTrackingObserver instance that triggered the event.
            turn_number: The sequential turn number that started.
        """
        self._current_turn_number = turn_number
        self._turn_start_times[turn_number] = datetime.now(timezone.utc).timestamp()
        logger.debug(f"Session {self._session_id}: Turn {turn_number} started")

    async def _on_turn_ended(
        self,
        observer: TurnTrackingObserver,
        turn_number: int,
        duration: float,
        was_interrupted: bool,
    ) -> None:
        """Handle turn ended events from the TurnTrackingObserver.

        Creates a TurnLatency record in the database with the turn duration
        and interruption status.

        Args:
            observer: The TurnTrackingObserver instance that triggered the event.
            turn_number: The sequential turn number that ended.
            duration: The duration of the turn in seconds.
            was_interrupted: Whether the turn was interrupted by the user.
        """
        # Convert duration from seconds to milliseconds
        latency_ms = duration * 1000.0

        # Create TurnLatency record
        turn_latency = TurnLatency(
            session_id=self._session_id,
            turn_number=turn_number,
            latency_ms=latency_ms,
            was_interrupted=was_interrupted,
        )
        self._db_session.add(turn_latency)
        await self._db_session.commit()

        # Clean up the start time for this turn
        self._turn_start_times.pop(turn_number, None)

        status = "interrupted" if was_interrupted else "completed"
        logger.debug(
            f"Session {self._session_id}: Turn {turn_number} {status} "
            f"(duration={latency_ms:.2f}ms)"
        )

    async def add_transcript(self, role: str, content: str) -> None:
        """Add a transcript entry to the database.

        Creates a Transcript record associated with the current session
        and the current turn number.

        Args:
            role: The role of the speaker ('user' or 'assistant').
            content: The text content of the transcript message.
        """
        transcript = Transcript(
            session_id=self._session_id,
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            turn_number=self._current_turn_number,
        )
        self._db_session.add(transcript)
        await self._db_session.commit()

        content_preview = f"{content[:50]}..." if len(content) > 50 else content
        logger.debug(
            f"Session {self._session_id}: Added {role} transcript "
            f"for turn {self._current_turn_number}: {content_preview}"
        )

    async def start(self) -> None:
        """Start recording the session.

        Creates a new Session record in the database with status='active',
        starts the audio buffer processor recording, and stores the session
        start time.

        Raises:
            Exception: If there is an error creating the database record.
        """
        self._start_time = datetime.now(timezone.utc)

        # Create a new Session record in the database
        self._session_record = Session(
            id=self._session_id,
            status=SessionStatus.ACTIVE,
            created_at=self._start_time,
        )
        self._db_session.add(self._session_record)
        await self._db_session.commit()

        # Start the audio buffer processor recording
        await self._audio_processor.start_recording()

        logger.info(
            f"Session {self._session_id}: Recording started at {self._start_time.isoformat()}"
        )

    async def stop(self) -> Optional[Path]:
        """Stop recording and save the session.

        Stops the audio buffer processor, saves the accumulated audio to a
        WAV file, and updates the Session record with ended_at, audio_file_path,
        and status='completed'.

        Returns:
            The path to the saved WAV file, or None if no audio was recorded.

        Raises:
            Exception: If there is an error saving the audio or updating the database.
        """
        # Stop the audio buffer processor
        await self._audio_processor.stop_recording()

        end_time = datetime.now(timezone.utc)
        audio_file_path: Optional[Path] = None

        # Save audio to WAV file if we have data
        if len(self._audio_data) > 0:
            audio_file_path = self._save_wav_file()
            logger.info(
                f"Session {self._session_id}: Saved {len(self._audio_data)} bytes "
                f"to {audio_file_path}"
            )
        else:
            logger.warning(f"Session {self._session_id}: No audio data to save")

        # Update the Session record in the database
        if self._session_record is not None:
            self._session_record.ended_at = end_time
            self._session_record.status = SessionStatus.COMPLETED
            if audio_file_path is not None:
                self._session_record.audio_file_path = str(audio_file_path)
            await self._db_session.commit()

        logger.info(
            f"Session {self._session_id}: Recording stopped at {end_time.isoformat()}"
        )

        return audio_file_path

    def _save_wav_file(self) -> Path:
        """Save the accumulated audio data to a WAV file.

        Creates a properly formatted WAV file with the correct headers for
        the configured sample rate and number of channels.

        Returns:
            The path to the saved WAV file.

        Raises:
            IOError: If there is an error writing the file.
        """
        # Ensure recordings directory exists
        recordings_path = self._settings.recordings_path
        recordings_path.mkdir(parents=True, exist_ok=True)

        # Generate filename using session ID
        filename = f"{self._session_id}.wav"
        file_path = recordings_path / filename

        # Write WAV file with proper headers
        # Audio is 16-bit PCM (2 bytes per sample)
        sample_width = 2

        with wave.open(str(file_path), "wb") as wav_file:
            wav_file.setnchannels(self._num_channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(self._sample_rate)
            wav_file.writeframes(bytes(self._audio_data))

        logger.debug(
            f"Session {self._session_id}: WAV file saved to {file_path} "
            f"(channels={self._num_channels}, sample_rate={self._sample_rate}, "
            f"sample_width={sample_width})"
        )

        return file_path

    async def mark_error(self, error_message: Optional[str] = None) -> None:
        """Mark the session as ended with an error.

        Updates the Session record with status='error' and the current time
        as ended_at. Optionally logs the error message.

        Args:
            error_message: Optional error message to log.
        """
        # Stop recording if still active
        try:
            await self._audio_processor.stop_recording()
        except Exception as e:
            logger.warning(f"Session {self._session_id}: Error stopping recording: {e}")

        end_time = datetime.now(timezone.utc)

        # Update the Session record
        if self._session_record is not None:
            self._session_record.ended_at = end_time
            self._session_record.status = SessionStatus.ERROR
            await self._db_session.commit()

        if error_message:
            logger.error(f"Session {self._session_id}: Error - {error_message}")
        else:
            logger.error(f"Session {self._session_id}: Session ended with error")


def create_session_recorder(
    session_id: uuid.UUID,
    db_session: AsyncSession,
    *,
    sample_rate: int = 16000,
    num_channels: int = 2,
) -> SessionRecorder:
    """Factory function to create a SessionRecorder instance.

    This is a convenience function for creating SessionRecorder instances
    with the specified configuration.

    Args:
        session_id: Unique identifier for the recording session.
        db_session: SQLAlchemy async session for database operations.
        sample_rate: Audio sample rate in Hz. Defaults to 16000.
        num_channels: Number of audio channels. Defaults to 2 (stereo).

    Returns:
        A configured SessionRecorder instance.

    Example:
        >>> from uuid import uuid4
        >>> from backend.db.database import get_db_session
        >>>
        >>> async with get_db_session() as db:
        ...     session_id = uuid4()
        ...     recorder = create_session_recorder(session_id, db)
        ...     await recorder.start()
        ...     # Add recorder.get_processor() to the pipeline
        ...     # ... run the voice agent ...
        ...     await recorder.stop()
    """
    return SessionRecorder(
        session_id=session_id,
        db_session=db_session,
        sample_rate=sample_rate,
        num_channels=num_channels,
    )
