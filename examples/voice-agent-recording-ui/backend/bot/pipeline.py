"""Pipecat voice pipeline for the voice agent recording UI backend.

This module defines the voice processing pipeline that handles:
- Speech-to-text conversion using Deepgram
- Language model processing using Google Gemini
- Text-to-speech synthesis using Cartesia
- Session recording with audio capture and latency tracking
- Freeze simulation for testing resilience
- Transcript and freeze event storage to database

The pipeline is designed for WebRTC-based voice interactions with
smart turn detection for natural conversation flow.
"""

import uuid
from typing import Optional

from loguru import logger

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    AssistantTurnStoppedMessage,
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    UserTurnStoppedMessage,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from backend.bot.freeze_simulator import FreezeSimulatorProcessor
from backend.bot.session_recorder import create_session_recorder
from backend.config import get_settings
from backend.db import async_session_maker
from backend.db.models import FreezeEvent

# System prompt for the voice assistant
SYSTEM_PROMPT = """You are a helpful voice assistant. Your goal is to assist users \
in a friendly and conversational manner.

Important guidelines:
- Your output will be spoken aloud through text-to-speech.
- Avoid using special characters, emojis, bullet points, or formatting that cannot \
be easily spoken.
- Keep your responses concise and natural for voice interaction.
- Be helpful, friendly, and engage naturally with the user.

Respond to what the user says in a helpful and conversational way."""


async def run_bot(
    webrtc_connection: SmallWebRTCConnection,
    session_id: Optional[uuid.UUID] = None,
) -> uuid.UUID:
    """Run the voice agent bot pipeline.

    Creates and runs a complete voice processing pipeline that handles
    speech recognition, language model interaction, and speech synthesis
    for real-time voice conversations over WebRTC. Integrates session
    recording, freeze simulation, transcript capture, and freeze event
    storage to the database.

    Args:
        webrtc_connection: The SmallWebRTCConnection instance for the
            WebRTC transport layer.
        session_id: Optional unique identifier for the session. If None,
            a new UUID will be generated.

    Returns:
        The session_id used for this bot run.
    """
    # Generate session ID if not provided
    if session_id is None:
        session_id = uuid.uuid4()

    logger.info(f"Starting voice agent bot with session_id={session_id}")

    settings = get_settings()

    # Create database session for the entire bot run
    async with async_session_maker() as db_session:
        # Initialize SessionRecorder for audio recording and latency tracking
        recorder = create_session_recorder(session_id, db_session)

        # Initialize FreezeSimulatorProcessor for simulating freezes during testing
        freeze_simulator = FreezeSimulatorProcessor(
            freeze_probability=0.3,  # 30% chance to see freezes during testing
            min_freeze_duration=1.0,
            max_freeze_duration=5.0,
        )

        # Start recording and set up freeze simulator reference time
        await recorder.start()

        # Set reference time to match session start for accurate freeze timestamps
        if recorder.start_time is not None:
            freeze_simulator.set_reference_time(recorder.start_time.timestamp())

        # Register handler to save freeze events to the database
        @freeze_simulator.event_handler("on_freeze")
        async def on_freeze(
            processor: FreezeSimulatorProcessor,
            start_time_ms: int,
            duration_ms: int,
        ) -> None:
            """Handle freeze events by storing them in the database."""
            freeze_event = FreezeEvent(
                session_id=session_id,
                start_time_ms=start_time_ms,
                duration_ms=duration_ms,
            )
            db_session.add(freeze_event)
            await db_session.commit()
            logger.debug(
                f"Session {session_id}: Freeze event recorded "
                f"(start={start_time_ms}ms, duration={duration_ms}ms)"
            )

        try:
            # Create transport with VAD analyzer
            transport = SmallWebRTCTransport(
                webrtc_connection=webrtc_connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
                ),
            )

            # Initialize speech-to-text service
            stt = DeepgramSTTService(api_key=settings.deepgram_api_key)

            # Initialize language model service
            llm = GoogleLLMService(
                api_key=settings.google_api_key,
                model="gemini-2.5-flash",
            )

            # Initialize text-to-speech service
            tts = CartesiaTTSService(
                api_key=settings.cartesia_api_key,
                voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",  # British Reading Lady
            )

            # Set up conversation context with system prompt
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
            ]

            context = LLMContext(messages)

            # Create aggregators for user and assistant turns with smart turn detection
            user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
                context,
                user_params=LLMUserAggregatorParams(
                    user_turn_strategies=UserTurnStrategies(
                        stop=[
                            TurnAnalyzerUserTurnStopStrategy(
                                turn_analyzer=LocalSmartTurnAnalyzerV3()
                            )
                        ]
                    ),
                ),
            )

            # Wire up transcript capture for user messages
            @user_aggregator.event_handler("on_user_turn_stopped")
            async def on_user_turn_stopped(
                aggregator,
                strategy,
                message: UserTurnStoppedMessage,
            ) -> None:
                """Capture user transcript when their turn ends."""
                if message.content:
                    await recorder.add_transcript("user", message.content)

            # Wire up transcript capture for assistant messages
            @assistant_aggregator.event_handler("on_assistant_turn_stopped")
            async def on_assistant_turn_stopped(
                aggregator,
                message: AssistantTurnStoppedMessage,
            ) -> None:
                """Capture assistant transcript when their turn ends."""
                if message.content:
                    await recorder.add_transcript("assistant", message.content)

            # Build the pipeline
            # Flow: transport input -> STT -> user aggregator -> LLM -> TTS ->
            #       freeze_simulator -> recorder -> transport output -> assistant aggregator
            pipeline = Pipeline(
                [
                    transport.input(),  # Transport user input
                    stt,  # Speech-to-text
                    user_aggregator,  # User response aggregation
                    llm,  # Language model
                    tts,  # Text-to-speech
                    freeze_simulator,  # Freeze simulation (after TTS)
                    recorder.get_processor(),  # Audio recording
                    transport.output(),  # Transport bot output
                    assistant_aggregator,  # Assistant response aggregation
                ]
            )

            # Create pipeline task with metrics enabled and turn observer attached
            task = PipelineTask(
                pipeline,
                params=PipelineParams(
                    enable_metrics=True,
                    enable_usage_metrics=True,
                ),
                observers=[recorder.get_turn_observer()],
            )

            @transport.event_handler("on_client_connected")
            async def on_client_connected(transport, client) -> None:
                """Handle client connection event.

                Initiates the conversation by adding an introduction prompt
                and queuing an LLM run frame.
                """
                logger.info("Client connected")
                # Add introduction prompt and kick off the conversation
                messages.append(
                    {"role": "system", "content": "Please introduce yourself to the user."}
                )
                await task.queue_frames([LLMRunFrame()])

            @transport.event_handler("on_client_disconnected")
            async def on_client_disconnected(transport, client) -> None:
                """Handle client disconnection event.

                Cancels the pipeline task when the client disconnects.
                """
                logger.info("Client disconnected")
                await task.cancel()

            # Run the pipeline
            runner = PipelineRunner(handle_sigint=False)
            await runner.run(task)

        except Exception as e:
            logger.error(f"Session {session_id}: Pipeline error - {e}")
            await recorder.mark_error(str(e))
            raise

        finally:
            # Stop recording and save audio file
            await recorder.stop()

    return session_id
