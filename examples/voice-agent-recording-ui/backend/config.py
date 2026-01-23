"""Configuration settings for the Voice Agent Recording UI backend.

This module provides a centralized configuration management system using
pydantic-settings for type-safe environment variable loading with validation.

The configuration supports multiple service providers for STT, LLM, and TTS,
allowing easy swapping of providers via environment variables.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class STTProvider(str, Enum):
    """Supported Speech-to-Text providers."""

    DEEPGRAM = "deepgram"


class LLMProvider(str, Enum):
    """Supported Language Model providers."""

    GOOGLE = "google"
    OPENAI = "openai"


class TTSProvider(str, Enum):
    """Supported Text-to-Speech providers."""

    CARTESIA = "cartesia"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    The settings support multiple service providers, allowing you to swap
    implementations by changing environment variables.

    Attributes:
        stt_provider: Speech-to-text provider selection.
        llm_provider: Language model provider selection.
        tts_provider: Text-to-speech provider selection.
        deepgram_api_key: API key for Deepgram STT.
        google_api_key: API key for Google AI services (Gemini).
        openai_api_key: API key for OpenAI services.
        cartesia_api_key: API key for Cartesia TTS.
        llm_model: Model identifier for the selected LLM provider.
        tts_voice_id: Voice identifier for the selected TTS provider.
        database_url: PostgreSQL connection URL with asyncpg driver.
        host: Server host address.
        port: Server port number.
        recordings_path: Path to store audio recordings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service Provider Selection
    stt_provider: STTProvider = Field(
        default=STTProvider.DEEPGRAM,
        description="Speech-to-text provider: deepgram",
    )
    llm_provider: LLMProvider = Field(
        default=LLMProvider.GOOGLE,
        description="Language model provider: google, openai",
    )
    tts_provider: TTSProvider = Field(
        default=TTSProvider.CARTESIA,
        description="Text-to-speech provider: cartesia",
    )

    # API Keys - Primary providers
    deepgram_api_key: str = Field(
        default="",
        description="API key for Deepgram speech-to-text service",
    )
    google_api_key: str = Field(
        default="",
        description="API key for Google AI services (Gemini)",
    )
    cartesia_api_key: str = Field(
        default="",
        description="API key for Cartesia text-to-speech service",
    )

    # API Keys - Alternative providers
    openai_api_key: str = Field(
        default="",
        description="API key for OpenAI services (GPT)",
    )

    # Model Configuration
    llm_model: str = Field(
        default="",
        description="Model identifier for LLM (e.g., 'gemini-2.5-flash', 'gpt-4o'). "
        "Leave empty for provider default.",
    )
    tts_voice_id: str = Field(
        default="",
        description="Voice identifier for TTS. Leave empty for provider default.",
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/voice_agent_db",
        description="PostgreSQL connection URL with asyncpg driver",
    )

    # Server
    host: str = Field(
        default="localhost",
        description="Server host address",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port number",
    )

    # Storage
    recordings_path: Path = Field(
        default=Path("./storage/recordings"),
        description="Path to store audio recordings",
    )

    @field_validator("recordings_path", mode="before")
    @classmethod
    def validate_recordings_path(cls, v: str | Path) -> Path:
        """Convert string path to Path object and ensure it exists."""
        path = Path(v) if isinstance(v, str) else v
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def has_deepgram_key(self) -> bool:
        """Check if Deepgram API key is configured."""
        return bool(self.deepgram_api_key and self.deepgram_api_key != "your_deepgram_api_key")

    @property
    def has_google_key(self) -> bool:
        """Check if Google API key is configured."""
        return bool(self.google_api_key and self.google_api_key != "your_google_api_key")

    @property
    def has_cartesia_key(self) -> bool:
        """Check if Cartesia API key is configured."""
        return bool(self.cartesia_api_key and self.cartesia_api_key != "your_cartesia_api_key")

    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key and self.openai_api_key != "your_openai_api_key")

    def validate_required_keys(self) -> list[str]:
        """Validate that all required API keys are configured based on selected providers.

        Returns:
            List of missing API key names.
        """
        missing = []

        # STT provider validation
        if self.stt_provider == STTProvider.DEEPGRAM and not self.has_deepgram_key:
            missing.append("DEEPGRAM_API_KEY")

        # LLM provider validation
        if self.llm_provider == LLMProvider.GOOGLE and not self.has_google_key:
            missing.append("GOOGLE_API_KEY")
        elif self.llm_provider == LLMProvider.OPENAI and not self.has_openai_key:
            missing.append("OPENAI_API_KEY")

        # TTS provider validation
        if self.tts_provider == TTSProvider.CARTESIA and not self.has_cartesia_key:
            missing.append("CARTESIA_API_KEY")

        return missing

    def get_llm_model(self) -> str:
        """Get the LLM model identifier, using provider defaults if not specified."""
        if self.llm_model:
            return self.llm_model
        # Provider-specific defaults
        if self.llm_provider == LLMProvider.GOOGLE:
            return "gemini-2.5-flash"
        elif self.llm_provider == LLMProvider.OPENAI:
            return "gpt-4o"
        return "gemini-2.5-flash"

    def get_tts_voice_id(self) -> str:
        """Get the TTS voice identifier, using provider defaults if not specified."""
        if self.tts_voice_id:
            return self.tts_voice_id
        # Provider-specific defaults
        if self.tts_provider == TTSProvider.CARTESIA:
            return "71a7ad14-091c-4e8e-a314-022ece01c121"  # British Reading Lady
        return "71a7ad14-091c-4e8e-a314-022ece01c121"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings instance.

    Returns:
        Singleton Settings instance loaded from environment.
    """
    return Settings()
