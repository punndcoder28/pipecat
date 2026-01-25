#
# Copyright (c) 2024-2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Freeze simulator processor for testing voice agent resilience.

This module provides a processor that randomly introduces freezes in TTS audio
output to simulate bot freezes during voice interactions. Useful for testing
UI responsiveness and user experience during bot failures.
"""

import asyncio
import random
import time
from typing import Callable, Optional

from loguru import logger

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class FreezeSimulatorProcessor(FrameProcessor):
    """A processor that randomly pauses TTS audio output to simulate bot freezes.

    This processor intercepts TTS audio frames and can randomly introduce delays
    to simulate bot freeze scenarios. It tracks bot speaking turns and decides
    whether to trigger a freeze at the start of each new turn.

    Event handlers available:
        - on_freeze: Called when a freeze event occurs with (start_time_ms, duration_ms)

    Example:
        ```python
        async def on_freeze(processor, start_time_ms, duration_ms):
            print(f"Bot froze at {start_time_ms}ms for {duration_ms}ms")

        freeze_simulator = FreezeSimulatorProcessor(
            freeze_probability=0.2,
            min_freeze_duration=2.0,
            max_freeze_duration=5.0,
        )
        freeze_simulator.add_event_handler("on_freeze", on_freeze)
        ```

    Args:
        freeze_probability: Probability of triggering a freeze per turn (0.0 to 1.0).
            Default is 0.1 (10% chance).
        min_freeze_duration: Minimum freeze duration in seconds. Default is 1.0.
        max_freeze_duration: Maximum freeze duration in seconds. Default is 10.0.
        on_freeze_event: Optional callback to report freeze events. Called with
            (start_time_ms, duration_ms) when a freeze occurs.
        name: Optional name for this processor instance.
        **kwargs: Additional arguments passed to FrameProcessor.
    """

    def __init__(
        self,
        *,
        freeze_probability: float = 0.1,
        min_freeze_duration: float = 1.0,
        max_freeze_duration: float = 10.0,
        on_freeze_event: Optional[Callable[[int, int], None]] = None,
        name: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the freeze simulator processor.

        Args:
            freeze_probability: Probability of triggering a freeze per turn (0.0 to 1.0).
            min_freeze_duration: Minimum freeze duration in seconds.
            max_freeze_duration: Maximum freeze duration in seconds.
            on_freeze_event: Optional callback to report freeze events.
            name: Optional name for this processor instance.
            **kwargs: Additional arguments passed to FrameProcessor.

        Raises:
            ValueError: If freeze_probability is not between 0.0 and 1.0.
            ValueError: If min_freeze_duration is greater than max_freeze_duration.
            ValueError: If any duration is negative.
        """
        super().__init__(name=name, **kwargs)

        # Validate parameters
        if not 0.0 <= freeze_probability <= 1.0:
            raise ValueError(
                f"freeze_probability must be between 0.0 and 1.0, got {freeze_probability}"
            )
        if min_freeze_duration < 0 or max_freeze_duration < 0:
            raise ValueError("Freeze durations cannot be negative")
        if min_freeze_duration > max_freeze_duration:
            raise ValueError(
                f"min_freeze_duration ({min_freeze_duration}) cannot be greater than "
                f"max_freeze_duration ({max_freeze_duration})"
            )

        self._freeze_probability = freeze_probability
        self._min_freeze_duration = min_freeze_duration
        self._max_freeze_duration = max_freeze_duration
        self._on_freeze_event = on_freeze_event

        # Freeze state tracking
        self._is_frozen: bool = False
        self._freeze_start_time: Optional[float] = None
        self._freeze_duration: float = 0.0
        self._freeze_end_time: Optional[float] = None

        # Turn tracking
        self._bot_speaking: bool = False
        self._should_freeze_this_turn: bool = False
        self._freeze_triggered_this_turn: bool = False
        self._audio_frames_count: int = 0
        self._min_frames_before_freeze: int = 3  # Wait for some frames before freezing

        # Reference time for calculating offsets
        self._reference_time: Optional[float] = None

        # Register event handler for freeze events
        self._register_event_handler("on_freeze")

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process a frame, potentially introducing freezes for TTS audio.

        This method handles three types of frames:
        - BotStartedSpeakingFrame: Marks the start of a bot turn and decides
          whether to freeze this turn.
        - BotStoppedSpeakingFrame: Marks the end of a bot turn and resets state.
        - TTSAudioRawFrame: Audio frames that may be delayed during a freeze.

        All other frames are passed through unchanged.

        Args:
            frame: The frame to process.
            direction: The direction of frame flow (DOWNSTREAM or UPSTREAM).
        """
        await super().process_frame(frame, direction)

        # Initialize reference time on first frame
        if self._reference_time is None:
            self._reference_time = time.time()

        if isinstance(frame, BotStartedSpeakingFrame):
            await self._handle_bot_started_speaking(frame, direction)
        elif isinstance(frame, BotStoppedSpeakingFrame):
            await self._handle_bot_stopped_speaking(frame, direction)
        elif isinstance(frame, TTSAudioRawFrame):
            await self._handle_tts_audio_frame(frame, direction)
        else:
            # Pass through all other frames unchanged
            await self.push_frame(frame, direction)

    async def _handle_bot_started_speaking(
        self, frame: BotStartedSpeakingFrame, direction: FrameDirection
    ) -> None:
        """Handle the start of a bot speaking turn.

        Decides whether to trigger a freeze this turn based on probability.

        Args:
            frame: The BotStartedSpeakingFrame.
            direction: The direction of frame flow.
        """
        self._bot_speaking = True
        self._audio_frames_count = 0
        self._freeze_triggered_this_turn = False

        # Decide whether to freeze this turn
        self._should_freeze_this_turn = random.random() < self._freeze_probability

        if self._should_freeze_this_turn:
            # Pick a random freeze duration
            self._freeze_duration = random.uniform(
                self._min_freeze_duration, self._max_freeze_duration
            )
            logger.info(
                f"{self}: Freeze scheduled for this turn "
                f"(duration: {self._freeze_duration:.2f}s)"
            )

        await self.push_frame(frame, direction)

    async def _handle_bot_stopped_speaking(
        self, frame: BotStoppedSpeakingFrame, direction: FrameDirection
    ) -> None:
        """Handle the end of a bot speaking turn.

        Resets turn-related state and clears any active freeze.

        Args:
            frame: The BotStoppedSpeakingFrame.
            direction: The direction of frame flow.
        """
        self._bot_speaking = False
        self._should_freeze_this_turn = False
        self._freeze_triggered_this_turn = False
        self._audio_frames_count = 0

        # Clear freeze state if still frozen when bot stops speaking
        if self._is_frozen:
            logger.info(f"{self}: Freeze cleared (bot stopped speaking)")
            self._is_frozen = False
            self._freeze_start_time = None
            self._freeze_end_time = None

        await self.push_frame(frame, direction)

    async def _handle_tts_audio_frame(
        self, frame: TTSAudioRawFrame, direction: FrameDirection
    ) -> None:
        """Handle TTS audio frames, potentially introducing freeze delays.

        If a freeze is scheduled for this turn and hasn't been triggered yet,
        this method will introduce a delay before passing through frames.

        Args:
            frame: The TTSAudioRawFrame to process.
            direction: The direction of frame flow.
        """
        self._audio_frames_count += 1

        # Check if we should trigger a freeze
        if (
            self._should_freeze_this_turn
            and not self._freeze_triggered_this_turn
            and self._audio_frames_count >= self._min_frames_before_freeze
        ):
            await self._start_freeze()

        # If frozen, wait until freeze ends
        if self._is_frozen and self._freeze_end_time is not None:
            current_time = time.time()
            remaining_time = self._freeze_end_time - current_time

            if remaining_time > 0:
                logger.debug(
                    f"{self}: Delaying frame for {remaining_time:.2f}s (freeze in progress)"
                )
                await asyncio.sleep(remaining_time)

            # End the freeze after waiting
            await self._end_freeze()

        await self.push_frame(frame, direction)

    async def _start_freeze(self) -> None:
        """Start a freeze event.

        Records the freeze start time and calculates the end time.
        Calls the on_freeze event handler if registered.
        """
        self._is_frozen = True
        self._freeze_triggered_this_turn = True
        self._freeze_start_time = time.time()
        self._freeze_end_time = self._freeze_start_time + self._freeze_duration

        # Calculate offset from reference time
        start_time_ms = int((self._freeze_start_time - self._reference_time) * 1000)
        duration_ms = int(self._freeze_duration * 1000)

        logger.info(
            f"{self}: Freeze started at {start_time_ms}ms for {duration_ms}ms"
        )

        # Call the callback if provided
        if self._on_freeze_event:
            try:
                self._on_freeze_event(start_time_ms, duration_ms)
            except Exception as e:
                logger.error(f"{self}: Error in on_freeze_event callback: {e}")

        # Call registered event handlers
        await self._call_event_handler("on_freeze", start_time_ms, duration_ms)

    async def _end_freeze(self) -> None:
        """End the current freeze event.

        Clears freeze state and logs the end of the freeze.
        """
        if self._is_frozen:
            logger.info(f"{self}: Freeze ended")
            self._is_frozen = False
            self._freeze_start_time = None
            self._freeze_end_time = None

    @property
    def freeze_probability(self) -> float:
        """Get the current freeze probability.

        Returns:
            The probability of triggering a freeze per turn (0.0 to 1.0).
        """
        return self._freeze_probability

    @freeze_probability.setter
    def freeze_probability(self, value: float) -> None:
        """Set the freeze probability.

        Args:
            value: The new probability (0.0 to 1.0).

        Raises:
            ValueError: If value is not between 0.0 and 1.0.
        """
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"freeze_probability must be between 0.0 and 1.0, got {value}")
        self._freeze_probability = value

    @property
    def min_freeze_duration(self) -> float:
        """Get the minimum freeze duration.

        Returns:
            The minimum freeze duration in seconds.
        """
        return self._min_freeze_duration

    @min_freeze_duration.setter
    def min_freeze_duration(self, value: float) -> None:
        """Set the minimum freeze duration.

        Args:
            value: The new minimum duration in seconds.

        Raises:
            ValueError: If value is negative or greater than max_freeze_duration.
        """
        if value < 0:
            raise ValueError("min_freeze_duration cannot be negative")
        if value > self._max_freeze_duration:
            raise ValueError(
                f"min_freeze_duration ({value}) cannot be greater than "
                f"max_freeze_duration ({self._max_freeze_duration})"
            )
        self._min_freeze_duration = value

    @property
    def max_freeze_duration(self) -> float:
        """Get the maximum freeze duration.

        Returns:
            The maximum freeze duration in seconds.
        """
        return self._max_freeze_duration

    @max_freeze_duration.setter
    def max_freeze_duration(self, value: float) -> None:
        """Set the maximum freeze duration.

        Args:
            value: The new maximum duration in seconds.

        Raises:
            ValueError: If value is negative or less than min_freeze_duration.
        """
        if value < 0:
            raise ValueError("max_freeze_duration cannot be negative")
        if value < self._min_freeze_duration:
            raise ValueError(
                f"max_freeze_duration ({value}) cannot be less than "
                f"min_freeze_duration ({self._min_freeze_duration})"
            )
        self._max_freeze_duration = value

    @property
    def is_frozen(self) -> bool:
        """Check if the processor is currently in a frozen state.

        Returns:
            True if currently frozen, False otherwise.
        """
        return self._is_frozen

    def set_reference_time(self, reference_time: float) -> None:
        """Set the reference time for calculating freeze offsets.

        This allows synchronization with external timing systems (e.g., recording
        start time) for accurate freeze event timestamps.

        Args:
            reference_time: The reference time as a Unix timestamp (seconds since epoch).
        """
        self._reference_time = reference_time
        logger.debug(f"{self}: Reference time set to {reference_time}")
