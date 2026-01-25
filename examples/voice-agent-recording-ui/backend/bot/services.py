"""Service factory functions with retry logic for external AI services.

This module provides factory functions for creating Pipecat service instances
(STT, LLM, TTS) with built-in retry logic for handling transient failures.

The services are configurable via environment variables, allowing easy swapping
of providers:
- STT: Deepgram (default)
- LLM: Google Gemini (default), OpenAI GPT
- TTS: Cartesia (default)

Each factory function includes retry logic for initialization failures
and returns a configured service instance ready for use in the pipeline.

Example:
    ```python
    from backend.bot.services import create_services_from_settings
    from backend.config import get_settings

    settings = get_settings()
    stt, llm, tts = await create_services_from_settings(settings)
    ```
"""

from typing import Any, Union

from loguru import logger

from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService

from backend.config import Settings, STTProvider, LLMProvider, TTSProvider
from backend.utils.retry import RetryConfig, service_retry


# Type aliases for service types
STTService = DeepgramSTTService  # Currently only Deepgram supported
LLMService = Union[GoogleLLMService, OpenAILLMService]
TTSService = CartesiaTTSService  # Currently only Cartesia supported


# Service-specific retry configurations
# STT may need faster retries due to real-time nature
STT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    service_name="STT",
)

# LLM can tolerate slightly longer retries
LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    service_name="LLM",
)

# TTS also needs responsive retries for voice output
TTS_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    service_name="TTS",
)


# =============================================================================
# STT Service Factories
# =============================================================================


@service_retry(config=STT_RETRY_CONFIG, service_name="Deepgram STT")
async def _create_deepgram_stt(api_key: str, **kwargs: Any) -> DeepgramSTTService:
    """Create a Deepgram Speech-to-Text service."""
    logger.debug("Creating Deepgram STT service...")
    service = DeepgramSTTService(api_key=api_key, **kwargs)
    logger.info("Deepgram STT service created successfully")
    return service


async def create_stt_service(
    settings: Settings,
    **kwargs: Any,
) -> STTService:
    """Create a Speech-to-Text service based on configuration.

    Args:
        settings: Application settings containing provider selection and API keys.
        **kwargs: Additional arguments passed to the service constructor.

    Returns:
        A configured STT service instance.

    Raises:
        ValueError: If the configured provider is not supported.
        Exception: If service creation fails after all retry attempts.
    """
    provider = settings.stt_provider

    if provider == STTProvider.DEEPGRAM:
        return await _create_deepgram_stt(
            api_key=settings.deepgram_api_key,
            **kwargs,
        )
    else:
        raise ValueError(f"Unsupported STT provider: {provider}")


# =============================================================================
# LLM Service Factories
# =============================================================================


@service_retry(config=LLM_RETRY_CONFIG, service_name="Google Gemini LLM")
async def _create_google_llm(
    api_key: str,
    model: str,
    **kwargs: Any,
) -> GoogleLLMService:
    """Create a Google Gemini Language Model service."""
    logger.debug(f"Creating Google Gemini LLM service with model: {model}...")
    service = GoogleLLMService(api_key=api_key, model=model, **kwargs)
    logger.info(f"Google Gemini LLM service created successfully (model: {model})")
    return service


@service_retry(config=LLM_RETRY_CONFIG, service_name="OpenAI LLM")
async def _create_openai_llm(
    api_key: str,
    model: str,
    **kwargs: Any,
) -> OpenAILLMService:
    """Create an OpenAI Language Model service."""
    logger.debug(f"Creating OpenAI LLM service with model: {model}...")
    service = OpenAILLMService(api_key=api_key, model=model, **kwargs)
    logger.info(f"OpenAI LLM service created successfully (model: {model})")
    return service


async def create_llm_service(
    settings: Settings,
    model: str | None = None,
    **kwargs: Any,
) -> LLMService:
    """Create a Language Model service based on configuration.

    Args:
        settings: Application settings containing provider selection and API keys.
        model: Optional model override. If not provided, uses settings default.
        **kwargs: Additional arguments passed to the service constructor.

    Returns:
        A configured LLM service instance.

    Raises:
        ValueError: If the configured provider is not supported.
        Exception: If service creation fails after all retry attempts.
    """
    provider = settings.llm_provider
    model_name = model or settings.get_llm_model()

    if provider == LLMProvider.GOOGLE:
        return await _create_google_llm(
            api_key=settings.google_api_key,
            model=model_name,
            **kwargs,
        )
    elif provider == LLMProvider.OPENAI:
        return await _create_openai_llm(
            api_key=settings.openai_api_key,
            model=model_name,
            **kwargs,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


# =============================================================================
# TTS Service Factories
# =============================================================================


@service_retry(config=TTS_RETRY_CONFIG, service_name="Cartesia TTS")
async def _create_cartesia_tts(
    api_key: str,
    voice_id: str,
    **kwargs: Any,
) -> CartesiaTTSService:
    """Create a Cartesia Text-to-Speech service."""
    logger.debug(f"Creating Cartesia TTS service with voice_id: {voice_id}...")
    service = CartesiaTTSService(api_key=api_key, voice_id=voice_id, **kwargs)
    logger.info(f"Cartesia TTS service created successfully (voice_id: {voice_id})")
    return service


async def create_tts_service(
    settings: Settings,
    voice_id: str | None = None,
    **kwargs: Any,
) -> TTSService:
    """Create a Text-to-Speech service based on configuration.

    Args:
        settings: Application settings containing provider selection and API keys.
        voice_id: Optional voice ID override. If not provided, uses settings default.
        **kwargs: Additional arguments passed to the service constructor.

    Returns:
        A configured TTS service instance.

    Raises:
        ValueError: If the configured provider is not supported.
        Exception: If service creation fails after all retry attempts.
    """
    provider = settings.tts_provider
    voice = voice_id or settings.get_tts_voice_id()

    if provider == TTSProvider.CARTESIA:
        return await _create_cartesia_tts(
            api_key=settings.cartesia_api_key,
            voice_id=voice,
            **kwargs,
        )
    else:
        raise ValueError(f"Unsupported TTS provider: {provider}")


# =============================================================================
# Convenience Functions
# =============================================================================


async def create_services_from_settings(
    settings: Settings,
) -> tuple[STTService, LLMService, TTSService]:
    """Create all external services based on configuration.

    Convenience function to initialize all three services at once based on
    the provider selections in settings. Each service is created independently
    with its own retry logic.

    Args:
        settings: Application settings containing provider selections and API keys.

    Returns:
        A tuple of (stt, llm, tts) service instances.

    Raises:
        ValueError: If any configured provider is not supported.
        Exception: If any service creation fails after all retry attempts.
    """
    logger.info(
        f"Initializing services - STT: {settings.stt_provider.value}, "
        f"LLM: {settings.llm_provider.value}, TTS: {settings.tts_provider.value}"
    )

    stt = await create_stt_service(settings)
    llm = await create_llm_service(settings)
    tts = await create_tts_service(settings)

    logger.info("All external services initialized successfully")
    return stt, llm, tts
