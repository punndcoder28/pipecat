"""Pipecat voice pipeline for the voice agent recording UI backend.

This module defines the voice processing pipeline that handles:
- Speech-to-text conversion using Deepgram
- Language model processing using Google Gemini
- Text-to-speech synthesis using Cartesia

The pipeline is designed for WebRTC-based voice interactions with
smart turn detection for natural conversation flow.
"""

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
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from backend.config import get_settings

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


async def run_bot(webrtc_connection: SmallWebRTCConnection) -> None:
    """Run the voice agent bot pipeline.

    Creates and runs a complete voice processing pipeline that handles
    speech recognition, language model interaction, and speech synthesis
    for real-time voice conversations over WebRTC.

    Args:
        webrtc_connection: The SmallWebRTCConnection instance for the
            WebRTC transport layer.

    Returns:
        None. The function runs until the client disconnects.
    """
    logger.info("Starting voice agent bot")

    settings = get_settings()

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

    # Build the pipeline
    # Flow: transport input -> STT -> user aggregator -> LLM -> TTS -> transport output -> assistant aggregator
    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            stt,  # Speech-to-text
            user_aggregator,  # User response aggregation
            llm,  # Language model
            tts,  # Text-to-speech
            transport.output(),  # Transport bot output
            assistant_aggregator,  # Assistant response aggregation
        ]
    )

    # Create pipeline task with metrics enabled
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
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
