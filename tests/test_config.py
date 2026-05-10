"""Tests for configuration management."""

import pytest
from pathlib import Path
import tempfile
import json

from openclaw.config.validation import validate_config_key, ConfigValidationError


class TestValidateConfigKey:
    """Config key validation behavior."""

    def test_worker_cap_valid(self):
        """worker_cap within range is accepted."""
        result = validate_config_key("worker_cap", 5)
        assert result == 5

    def test_worker_cap_too_high(self):
        """worker_cap above max is rejected."""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config_key("worker_cap", 15)
        assert "1 and 10" in str(exc.value)

    def test_worker_cap_too_low(self):
        """worker_cap below min is rejected."""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config_key("worker_cap", 0)
        assert "1 and 10" in str(exc.value)

    def test_bash_timeout_valid(self):
        """bash_timeout within range is accepted."""
        result = validate_config_key("bash_timeout", 60)
        assert result == 60

    def test_bash_timeout_too_high(self):
        """bash_timeout above max is rejected."""
        with pytest.raises(ConfigValidationError):
            validate_config_key("bash_timeout", 400)

    def test_unknown_key_rejected(self):
        """Unknown config keys are rejected."""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config_key("unknown_key", "value")
        assert "Unknown config key" in str(exc.value)

    def test_sensitive_key_rejected(self):
        """Sensitive keys cannot be set via command."""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config_key("github.token", "secret")
        assert "sensitive" in str(exc.value).lower()

    def test_auto_approve_prd_boolean(self):
        """auto_approve_prd accepts boolean strings."""
        result = validate_config_key("auto_approve_prd", "true")
        assert result is True
        result = validate_config_key("auto_approve_prd", "false")
        assert result is False

    def test_model_in_allowed_list(self):
        """model must be in allowed models list."""
        result = validate_config_key("model", "kimi-2.6")
        assert result == "kimi-2.6"

    def test_model_not_allowed(self):
        """Unknown model is rejected."""
        with pytest.raises(ConfigValidationError):
            validate_config_key("model", "gpt-99")
