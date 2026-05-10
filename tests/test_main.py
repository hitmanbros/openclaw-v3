"""Tests for bot entry point."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import tempfile
import yaml

from openclaw.main import create_bot, run_bot


class TestCreateBot:
    """Bot creation behavior."""

    @pytest.fixture
    def temp_config(self):
        with tempfile.TemporaryDirectory() as d:
            config_file = Path(d) / "config.yaml"
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
                "owner_id": "@owner:example.com",
            }))
            yield config_file

    def test_create_bot_returns_matrix_bot(self, temp_config):
        """create_bot returns a MatrixBot instance with correct config."""
        with patch("openclaw.main.AsyncClient") as MockClient:
            bot = create_bot(temp_config)
            assert bot.user_id == "@bot:example.com"
            assert bot.homeserver == "https://matrix.example.com"
            assert bot.owner_id == "@owner:example.com"
            assert bot.main_room == "!main:example.com"
            assert bot.ops_room == "!ops:example.com"

    def test_create_bot_sets_llm_client(self, temp_config):
        """create_bot attaches an LLM client to the bot."""
        with patch("openclaw.main.AsyncClient"):
            bot = create_bot(temp_config)
            assert bot.llm_client is not None

    def test_create_bot_sets_config(self, temp_config):
        """create_bot loads config and makes it available."""
        with patch("openclaw.main.AsyncClient"):
            bot = create_bot(temp_config)
            assert bot.config["worker_cap"] == 3
            assert bot.config["model"] == "kimi-2.6"


class TestRunBot:
    """Bot runtime behavior."""

    @pytest.mark.asyncio
    async def test_run_bot_logs_in(self):
        """run_bot logs in and starts sync."""
        bot = MagicMock()
        bot.client = MagicMock()
        bot.client.login = AsyncMock()
        bot.client.sync = AsyncMock()
        bot.client.sync_forever = AsyncMock()
        bot.client.close = AsyncMock()
        bot.client.join = AsyncMock()
        bot.client.room_send = AsyncMock()
        bot.main_room = "!main:example.com"
        bot.ops_room = "!ops:example.com"

        with patch("asyncio.Event") as MockEvent:
            mock_event = MagicMock()
            mock_event.wait = AsyncMock()
            MockEvent.return_value = mock_event

            # Run for a short time then "stop"
            async def stop_soon():
                mock_event.wait = AsyncMock()
                return None

            await run_bot(bot)

        bot.client.login.assert_called_once()
        bot.client.sync_forever.assert_called_once()
