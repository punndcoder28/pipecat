"""Bot module for voice agent pipeline configuration."""

from backend.bot.freeze_simulator import FreezeSimulatorProcessor
from backend.bot.pipeline import run_bot
from backend.bot.session_recorder import SessionRecorder, create_session_recorder

__all__ = [
    "run_bot",
    "SessionRecorder",
    "create_session_recorder",
    "FreezeSimulatorProcessor",
]
