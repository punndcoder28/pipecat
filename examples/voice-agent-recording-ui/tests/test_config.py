"""Tests for configuration module."""

import pytest
from unittest.mock import patch

from backend.config import (
    Settings,
    STTProvider,
    LLMProvider,
    TTSProvider,
    get_settings,
)


class TestProviderEnums:
    """Tests for provider enum classes."""

    def test_stt_provider_values(self):
        """Test STTProvider enum values."""
        assert STTProvider.DEEPGRAM.value == "deepgram"

    def test_llm_provider_values(self):
        """Test LLMProvider enum values."""
        assert LLMProvider.GOOGLE.value == "google"
        assert LLMProvider.OPENAI.value == "openai"

    def test_tts_provider_values(self):
        """Test TTSProvider enum values."""
        assert TTSProvider.CARTESIA.value == "cartesia"


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(
                _env_file=None,  # Don't load .env file
            )

        assert settings.stt_provider == STTProvider.DEEPGRAM
        assert settings.llm_provider == LLMProvider.GOOGLE
        assert settings.tts_provider == TTSProvider.CARTESIA
        assert settings.host == "localhost"
        assert settings.port == 8000

    def test_provider_selection_from_env(self, temp_env_vars):
        """Test provider selection from environment variables."""
        temp_env_vars(
            STT_PROVIDER="deepgram",
            LLM_PROVIDER="openai",
            TTS_PROVIDER="cartesia",
        )
        # Clear the lru_cache
        get_settings.cache_clear()

        settings = Settings(_env_file=None)

        assert settings.stt_provider == STTProvider.DEEPGRAM
        assert settings.llm_provider == LLMProvider.OPENAI
        assert settings.tts_provider == TTSProvider.CARTESIA

    def test_has_deepgram_key_true(self):
        """Test has_deepgram_key returns True with valid key."""
        settings = Settings(
            deepgram_api_key="actual_api_key",
            _env_file=None,
        )
        assert settings.has_deepgram_key is True

    def test_has_deepgram_key_false_placeholder(self):
        """Test has_deepgram_key returns False with placeholder."""
        settings = Settings(
            deepgram_api_key="your_deepgram_api_key",
            _env_file=None,
        )
        assert settings.has_deepgram_key is False

    def test_has_deepgram_key_false_empty(self):
        """Test has_deepgram_key returns False when empty."""
        settings = Settings(
            deepgram_api_key="",
            _env_file=None,
        )
        assert settings.has_deepgram_key is False

    def test_has_google_key(self):
        """Test has_google_key property."""
        settings = Settings(
            google_api_key="test_key",
            _env_file=None,
        )
        assert settings.has_google_key is True

    def test_has_cartesia_key(self):
        """Test has_cartesia_key property."""
        settings = Settings(
            cartesia_api_key="test_key",
            _env_file=None,
        )
        assert settings.has_cartesia_key is True

    def test_has_openai_key(self):
        """Test has_openai_key property."""
        settings = Settings(
            openai_api_key="test_key",
            _env_file=None,
        )
        assert settings.has_openai_key is True


class TestSettingsValidation:
    """Tests for Settings validation methods."""

    def test_validate_required_keys_google_provider(self):
        """Test validation with Google LLM provider."""
        settings = Settings(
            llm_provider=LLMProvider.GOOGLE,
            deepgram_api_key="valid_key",
            google_api_key="",  # Missing
            cartesia_api_key="valid_key",
            _env_file=None,
        )

        missing = settings.validate_required_keys()
        assert "GOOGLE_API_KEY" in missing
        assert "DEEPGRAM_API_KEY" not in missing
        assert "CARTESIA_API_KEY" not in missing

    def test_validate_required_keys_openai_provider(self):
        """Test validation with OpenAI LLM provider."""
        settings = Settings(
            llm_provider=LLMProvider.OPENAI,
            deepgram_api_key="valid_key",
            google_api_key="valid_key",  # Not needed for OpenAI
            openai_api_key="",  # Missing
            cartesia_api_key="valid_key",
            _env_file=None,
        )

        missing = settings.validate_required_keys()
        assert "OPENAI_API_KEY" in missing
        assert "GOOGLE_API_KEY" not in missing

    def test_validate_required_keys_all_valid(self):
        """Test validation with all keys valid."""
        settings = Settings(
            deepgram_api_key="valid_key",
            google_api_key="valid_key",
            cartesia_api_key="valid_key",
            _env_file=None,
        )

        missing = settings.validate_required_keys()
        assert len(missing) == 0


class TestLLMModelDefaults:
    """Tests for LLM model default selection."""

    def test_get_llm_model_custom(self):
        """Test get_llm_model with custom model."""
        settings = Settings(
            llm_model="custom-model-v1",
            _env_file=None,
        )
        assert settings.get_llm_model() == "custom-model-v1"

    def test_get_llm_model_google_default(self):
        """Test get_llm_model defaults to gemini for Google."""
        settings = Settings(
            llm_provider=LLMProvider.GOOGLE,
            llm_model="",
            _env_file=None,
        )
        assert settings.get_llm_model() == "gemini-2.5-flash"

    def test_get_llm_model_openai_default(self):
        """Test get_llm_model defaults to gpt-4o for OpenAI."""
        settings = Settings(
            llm_provider=LLMProvider.OPENAI,
            llm_model="",
            _env_file=None,
        )
        assert settings.get_llm_model() == "gpt-4o"


class TestTTSVoiceDefaults:
    """Tests for TTS voice default selection."""

    def test_get_tts_voice_id_custom(self):
        """Test get_tts_voice_id with custom voice."""
        settings = Settings(
            tts_voice_id="custom-voice-id",
            _env_file=None,
        )
        assert settings.get_tts_voice_id() == "custom-voice-id"

    def test_get_tts_voice_id_cartesia_default(self):
        """Test get_tts_voice_id defaults to British Reading Lady."""
        settings = Settings(
            tts_provider=TTSProvider.CARTESIA,
            tts_voice_id="",
            _env_file=None,
        )
        # British Reading Lady voice ID
        assert settings.get_tts_voice_id() == "71a7ad14-091c-4e8e-a314-022ece01c121"


class TestPortValidation:
    """Tests for port validation."""

    def test_valid_port(self):
        """Test valid port number."""
        settings = Settings(port=8080, _env_file=None)
        assert settings.port == 8080

    def test_port_minimum(self):
        """Test minimum port number."""
        settings = Settings(port=1, _env_file=None)
        assert settings.port == 1

    def test_port_maximum(self):
        """Test maximum port number."""
        settings = Settings(port=65535, _env_file=None)
        assert settings.port == 65535

    def test_invalid_port_below_minimum(self):
        """Test port below minimum raises error."""
        with pytest.raises(ValueError):
            Settings(port=0, _env_file=None)

    def test_invalid_port_above_maximum(self):
        """Test port above maximum raises error."""
        with pytest.raises(ValueError):
            Settings(port=65536, _env_file=None)
