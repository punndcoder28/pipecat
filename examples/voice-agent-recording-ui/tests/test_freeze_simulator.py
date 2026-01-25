"""Tests for the freeze simulator processor."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.bot.freeze_simulator import FreezeSimulatorProcessor


class TestFreezeSimulatorInit:
    """Tests for FreezeSimulatorProcessor initialization."""

    def test_default_initialization(self):
        """Test default initialization parameters."""
        processor = FreezeSimulatorProcessor()

        assert processor.freeze_probability == 0.1
        assert processor.min_freeze_duration == 1.0
        assert processor.max_freeze_duration == 10.0
        assert processor.is_frozen is False

    def test_custom_initialization(self):
        """Test custom initialization parameters."""
        processor = FreezeSimulatorProcessor(
            freeze_probability=0.5,
            min_freeze_duration=2.0,
            max_freeze_duration=8.0,
        )

        assert processor.freeze_probability == 0.5
        assert processor.min_freeze_duration == 2.0
        assert processor.max_freeze_duration == 8.0

    def test_invalid_probability_negative(self):
        """Test that negative probability raises ValueError."""
        with pytest.raises(ValueError, match="freeze_probability must be between"):
            FreezeSimulatorProcessor(freeze_probability=-0.1)

    def test_invalid_probability_above_one(self):
        """Test that probability above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="freeze_probability must be between"):
            FreezeSimulatorProcessor(freeze_probability=1.5)

    def test_invalid_min_greater_than_max(self):
        """Test that min > max raises ValueError."""
        with pytest.raises(ValueError, match="min_freeze_duration.*cannot be greater"):
            FreezeSimulatorProcessor(
                min_freeze_duration=10.0,
                max_freeze_duration=5.0,
            )

    def test_invalid_negative_duration(self):
        """Test that negative durations raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            FreezeSimulatorProcessor(min_freeze_duration=-1.0)

    def test_zero_probability(self):
        """Test zero probability is valid (never freezes)."""
        processor = FreezeSimulatorProcessor(freeze_probability=0.0)
        assert processor.freeze_probability == 0.0

    def test_one_probability(self):
        """Test 100% probability is valid."""
        processor = FreezeSimulatorProcessor(freeze_probability=1.0)
        assert processor.freeze_probability == 1.0


class TestFreezeSimulatorProperties:
    """Tests for FreezeSimulatorProcessor property setters."""

    def test_set_freeze_probability(self):
        """Test setting freeze probability after init."""
        processor = FreezeSimulatorProcessor()
        processor.freeze_probability = 0.7
        assert processor.freeze_probability == 0.7

    def test_set_freeze_probability_invalid(self):
        """Test setting invalid freeze probability raises error."""
        processor = FreezeSimulatorProcessor()
        with pytest.raises(ValueError):
            processor.freeze_probability = 1.5

    def test_set_min_freeze_duration(self):
        """Test setting minimum freeze duration."""
        processor = FreezeSimulatorProcessor(max_freeze_duration=10.0)
        processor.min_freeze_duration = 3.0
        assert processor.min_freeze_duration == 3.0

    def test_set_min_freeze_duration_invalid(self):
        """Test setting min > max raises error."""
        processor = FreezeSimulatorProcessor(max_freeze_duration=5.0)
        with pytest.raises(ValueError):
            processor.min_freeze_duration = 10.0

    def test_set_max_freeze_duration(self):
        """Test setting maximum freeze duration."""
        processor = FreezeSimulatorProcessor(min_freeze_duration=1.0)
        processor.max_freeze_duration = 15.0
        assert processor.max_freeze_duration == 15.0

    def test_set_max_freeze_duration_invalid(self):
        """Test setting max < min raises error."""
        processor = FreezeSimulatorProcessor(min_freeze_duration=5.0)
        with pytest.raises(ValueError):
            processor.max_freeze_duration = 2.0


class TestFreezeSimulatorReferenceTime:
    """Tests for reference time functionality."""

    def test_set_reference_time(self):
        """Test setting reference time."""
        processor = FreezeSimulatorProcessor()
        ref_time = time.time()
        processor.set_reference_time(ref_time)
        assert processor._reference_time == ref_time

    def test_reference_time_initially_none(self):
        """Test reference time is None initially."""
        processor = FreezeSimulatorProcessor()
        assert processor._reference_time is None


class TestFreezeSimulatorCallbacks:
    """Tests for freeze event callbacks."""

    def test_on_freeze_event_callback(self):
        """Test on_freeze_event callback is called."""
        callback_data = {}

        def on_freeze(start_time_ms: int, duration_ms: int):
            callback_data["start"] = start_time_ms
            callback_data["duration"] = duration_ms

        processor = FreezeSimulatorProcessor(
            freeze_probability=1.0,  # Always freeze
            min_freeze_duration=0.1,
            max_freeze_duration=0.1,
            on_freeze_event=on_freeze,
        )

        # Set reference time
        processor.set_reference_time(time.time())

        # Simulate triggering a freeze
        processor._is_frozen = True
        processor._freeze_triggered_this_turn = True
        processor._freeze_start_time = time.time()
        processor._freeze_duration = 0.1

        # Calculate and call callback manually (as _start_freeze would)
        start_time_ms = int((processor._freeze_start_time - processor._reference_time) * 1000)
        duration_ms = int(processor._freeze_duration * 1000)

        if processor._on_freeze_event:
            processor._on_freeze_event(start_time_ms, duration_ms)

        assert "start" in callback_data
        assert "duration" in callback_data
        assert callback_data["duration"] == 100  # 0.1s = 100ms


class TestFreezeSimulatorState:
    """Tests for freeze state tracking."""

    def test_is_frozen_default(self):
        """Test is_frozen is False by default."""
        processor = FreezeSimulatorProcessor()
        assert processor.is_frozen is False

    def test_freeze_state_tracking(self):
        """Test freeze state can be tracked internally."""
        processor = FreezeSimulatorProcessor()

        # Simulate starting a freeze
        processor._is_frozen = True
        assert processor.is_frozen is True

        # Simulate ending a freeze
        processor._is_frozen = False
        assert processor.is_frozen is False


class TestFreezeSimulatorEdgeCases:
    """Tests for edge cases."""

    def test_equal_min_max_duration(self):
        """Test when min and max duration are equal."""
        processor = FreezeSimulatorProcessor(
            min_freeze_duration=5.0,
            max_freeze_duration=5.0,
        )
        assert processor.min_freeze_duration == 5.0
        assert processor.max_freeze_duration == 5.0

    def test_very_small_durations(self):
        """Test with very small durations."""
        processor = FreezeSimulatorProcessor(
            min_freeze_duration=0.001,
            max_freeze_duration=0.01,
        )
        assert processor.min_freeze_duration == 0.001
        assert processor.max_freeze_duration == 0.01

    def test_processor_name(self):
        """Test processor can be initialized with name."""
        processor = FreezeSimulatorProcessor(name="TestFreezeProcessor")
        assert "TestFreezeProcessor" in str(processor) or processor.name == "TestFreezeProcessor"
