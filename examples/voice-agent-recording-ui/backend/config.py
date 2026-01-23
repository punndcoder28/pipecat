"""Configuration settings for the Voice Agent Recording UI backend.

This module provides a centralized configuration management system using
pydantic-settings for type-safe environment variable loading with validation.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        deepgram_api_key: API key for Deepgram speech-to-text service.
        google_api_key: API key for Google AI services (Gemini).
        cartesia_api_key: API key for Cartesia text-to-speech service.
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

    # API Keys
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

    def validate_required_keys(self) -> list[str]:
        """Validate that all required API keys are configured.

        Returns:
            List of missing API key names.
        """
        missing = []
        if not self.has_deepgram_key:
            missing.append("DEEPGRAM_API_KEY")
        if not self.has_google_key:
            missing.append("GOOGLE_API_KEY")
        if not self.has_cartesia_key:
            missing.append("CARTESIA_API_KEY")
        return missing


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings instance.

    Returns:
        Singleton Settings instance loaded from environment.
    """
    return Settings()
