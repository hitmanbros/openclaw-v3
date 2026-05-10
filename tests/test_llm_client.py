"""Tests for LLM client."""

import pytest
from unittest.mock import AsyncMock, patch

from openclaw.llm.client import KimiClient


class TestKimiClient:
    """Kimi API client behavior."""

    def test_init_stores_config(self):
        client = KimiClient(api_key="test_key", model="kimi-2.6")
        assert client.api_key == "test_key"
        assert client.model == "kimi-2.6"

    @pytest.mark.asyncio
    async def test_chat_sends_request(self):
        client = KimiClient(api_key="test_key", model="kimi-2.6")
        
        mock_response = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(
                return_value=AsyncMock(
                    status=200,
                    json=AsyncMock(return_value=mock_response),
                )
            )
            mock_post.return_value.__aexit__ = AsyncMock(return_value=False)
            
            result = await client.chat(messages=[{"role": "user", "content": "Hi"}])
            assert result == {"content": "Hello!"}
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_handles_api_error(self):
        client = KimiClient(api_key="test_key", model="kimi-2.6")
        
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(
                return_value=AsyncMock(
                    status=429,
                    json=AsyncMock(return_value={"error": "Rate limited"}),
                    text=AsyncMock(return_value="Rate limited"),
                )
            )
            mock_post.return_value.__aexit__ = AsyncMock(return_value=False)
            
            with pytest.raises(RuntimeError) as exc:
                await client.chat(messages=[{"role": "user", "content": "Hi"}])
            assert "Rate limited" in str(exc.value)

    @pytest.mark.asyncio
    async def test_chat_counts_tokens(self):
        client = KimiClient(api_key="test_key", model="kimi-2.6")
        client.token_tracker = {"input": 0, "output": 0}
        
        mock_response = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(
                return_value=AsyncMock(
                    status=200,
                    json=AsyncMock(return_value=mock_response),
                )
            )
            mock_post.return_value.__aexit__ = AsyncMock(return_value=False)
            
            await client.chat(messages=[{"role": "user", "content": "Hi"}])
            assert client.token_tracker["input"] == 10
            assert client.token_tracker["output"] == 5

    def test_build_headers(self):
        client = KimiClient(api_key="secret123")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer secret123"
        assert headers["Content-Type"] == "application/json"

    def test_build_payload(self):
        client = KimiClient(api_key="test", model="kimi-2.6")
        payload = client._build_payload(
            messages=[{"role": "user", "content": "Hi"}],
            tools=None,
        )
        assert payload["model"] == "kimi-2.6"
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]
        assert "tools" not in payload
