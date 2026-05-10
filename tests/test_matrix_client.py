"""Tests for Matrix client message handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from openclaw.matrix.client import MatrixBot


class TestMatrixBot:
    """Matrix bot behavior."""

    @pytest.fixture
    def bot(self):
        """Create a MatrixBot with mocked client."""
        return MatrixBot(
            homeserver="https://matrix.hoomestead.com",
            user_id="@openclaw:hoomestead.com",
            access_token="test_token",
            owner_id="@bryan:hoomestead.com",
            main_room="!main123:hoomestead.com",
            ops_room="!ops456:hoomestead.com",
        )

    @pytest.mark.asyncio
    async def test_handle_ping_command(self, bot):
        """Bot replies 'pong' to !ping in main room."""
        bot.client = MagicMock()
        bot.client.room_send = AsyncMock()
        
        await bot.handle_message(
            room_id="!main123:hoomestead.com",
            sender="@bryan:hoomestead.com",
            body="!ping"
        )
        
        bot.client.room_send.assert_called_once()
        call_args = bot.client.room_send.call_args
        assert call_args.kwargs["content"]["body"] == "pong"

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self, bot):
        """Bot replies with help for unknown commands."""
        bot.client = MagicMock()
        bot.client.room_send = AsyncMock()
        
        await bot.handle_message(
            room_id="!main123:hoomestead.com",
            sender="@bryan:hoomestead.com",
            body="!unknown"
        )
        
        bot.client.room_send.assert_called_once()
        call_args = bot.client.room_send.call_args
        assert "unknown command" in call_args.kwargs["content"]["body"].lower()

    @pytest.mark.asyncio
    async def test_ignore_non_owner(self, bot):
        """Bot ignores messages from non-owners."""
        bot.client = MagicMock()
        bot.client.room_send = AsyncMock()
        
        await bot.handle_message(
            room_id="!main123:hoomestead.com",
            sender="@stranger:hoomestead.com",
            body="!ping"
        )
        
        bot.client.room_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_natural_language_chat(self, bot):
        """Bot replies to natural language via LLM in main room."""
        bot.client = MagicMock()
        bot.client.room_send = AsyncMock()
        bot.llm_client = MagicMock()
        bot.llm_client.chat = AsyncMock(return_value="Hello! How can I help?")
        
        await bot.handle_message(
            room_id="!main123:hoomestead.com",
            sender="@bryan:hoomestead.com",
            body="Hello bot"
        )
        
        bot.llm_client.chat.assert_called_once()
        bot.client.room_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_get_command(self, bot):
        """Bot replies with config value for !config get."""
        bot.client = MagicMock()
        bot.client.room_send = AsyncMock()
        bot.config = {"worker_cap": 5}
        
        await bot.handle_message(
            room_id="!main123:hoomestead.com",
            sender="@bryan:hoomestead.com",
            body="!config get worker_cap"
        )
        
        bot.client.room_send.assert_called_once()
        call_args = bot.client.room_send.call_args
        assert "5" in call_args.kwargs["content"]["body"]

    @pytest.mark.asyncio
    async def test_config_set_command(self, bot):
        """Bot updates config and confirms for !config set."""
        bot.client = MagicMock()
        bot.client.room_send = AsyncMock()
        bot.config = {"worker_cap": 3}
        
        await bot.handle_message(
            room_id="!main123:hoomestead.com",
            sender="@bryan:hoomestead.com",
            body="!config set worker_cap 5"
        )
        
        assert bot.config["worker_cap"] == 5
        bot.client.room_send.assert_called_once()
        call_args = bot.client.room_send.call_args
        assert "set to 5" in call_args.kwargs["content"]["body"]
