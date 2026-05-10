"""Tests for configuration loading."""

import pytest
import tempfile
from pathlib import Path
import yaml

from openclaw.config.loader import ConfigLoader


class TestConfigLoader:
    """Config loading behavior."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_load_basic_config(self, temp_dir):
        """Load a minimal config.yaml file."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(yaml.safe_dump({
            "matrix": {
                "homeserver": "https://matrix.example.com",
                "user_id": "@bot:example.com",
                "access_token": "test_token",
            },
            "rooms": {
                "main": "!main:example.com",
                "ops": "!ops:example.com",
            },
            "llm": {
                "provider": "kimi",
                "model": "kimi-2.6",
                "api_key": "test_key",
            },
        }))

        loader = ConfigLoader(config_file)
        config = loader.load()

        assert config["matrix"]["homeserver"] == "https://matrix.example.com"
        assert config["matrix"]["user_id"] == "@bot:example.com"
        assert config["rooms"]["main"] == "!main:example.com"
        assert config["llm"]["model"] == "kimi-2.6"

    def test_env_substitution(self, temp_dir, monkeypatch):
        """Environment variables in config are substituted."""
        monkeypatch.setenv("MATRIX_TOKEN", "secret_token_123")
        monkeypatch.setenv("KIMI_KEY", "secret_key_456")

        config_file = temp_dir / "config.yaml"
        config_file.write_text(yaml.safe_dump({
            "matrix": {
                "access_token": "${MATRIX_TOKEN}",
            },
            "llm": {
                "api_key": "${KIMI_KEY}",
            },
        }))

        loader = ConfigLoader(config_file)
        config = loader.load()

        assert config["matrix"]["access_token"] == "secret_token_123"
        assert config["llm"]["api_key"] == "secret_key_456"

    def test_missing_file_raises(self, temp_dir):
        """Missing config file raises FileNotFoundError."""
        loader = ConfigLoader(temp_dir / "nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_default_values_applied(self, temp_dir):
        """Default values are applied for missing keys."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(yaml.safe_dump({
            "matrix": {
                "homeserver": "https://matrix.example.com",
                "user_id": "@bot:example.com",
                "access_token": "token",
            },
        }))

        loader = ConfigLoader(config_file)
        config = loader.load()

        assert config["defaults"]["worker_cap"] == 3
        assert config["defaults"]["daily_input_cap"] == 3_000_000
        assert config["http"]["port"] == 8080

    def test_project_registry(self, temp_dir):
        """Project short names are loaded from config."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(yaml.safe_dump({
            "projects": {
                "alpha": {"repo": "github.com/owner/alpha"},
                "beta": {"repo": "github.com/owner/beta"},
            },
        }))

        loader = ConfigLoader(config_file)
        config = loader.load()

        assert config["projects"]["alpha"]["repo"] == "github.com/owner/alpha"
        assert config["projects"]["beta"]["repo"] == "github.com/owner/beta"
