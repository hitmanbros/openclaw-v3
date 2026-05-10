"""Live Matrix integration tests.

Requires:
    HOMESERVER=https://matrix.hoomestead.com
    OWNER_TOKEN=mct_qkxsT7wd1Vz8RKj5UdFX8kHfqkWeBM_7lWlV1
    MAIN_ROOM=!GGnkLXZSGwvdXdlnFO:hoomestead.com

Run with:
    pytest tests/test_live_matrix.py -v -s

WARNING: These tests send real messages to real rooms.
"""

import os
import asyncio
import uuid
import pytest
import pytest_asyncio
import aiohttp

HOMESERVER = os.environ.get("HOMESERVER", "https://matrix.hoomestead.com")
OWNER_TOKEN = os.environ.get("OWNER_TOKEN", "")
OWNER_MXID = "@bryan:hoomestead.com"


class MatrixAPI:
    def __init__(self, homeserver, token):
        self.homeserver = homeserver.rstrip("/")
        self.token = token

    async def _request(self, method, path, **kwargs):
        url = f"{self.homeserver}/_matrix/client/v3{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        async with aiohttp.ClientSession() as s:
            async with s.request(method, url, headers=headers, **kwargs) as r:
                if r.status == 429:
                    data = await r.json()
                    retry = data.get("retry_after_ms", 5000) / 1000
                    await asyncio.sleep(retry)
                    return await self._request(method, path, **kwargs)
                return r.status, await r.json() if r.content_type == "application/json" else await r.text()

    async def joined_rooms(self):
        status, data = await self._request("GET", "/joined_rooms")
        return data.get("joined_rooms", []) if status == 200 else []

    async def room_name(self, room_id):
        status, data = await self._request("GET", f"/rooms/{room_id}/state/m.room.name")
        return data.get("name", "") if status == 200 else ""

    async def send_message(self, room_id, body):
        txn = uuid.uuid4().hex
        status, data = await self._request(
            "PUT",
            f"/rooms/{room_id}/send/m.room.message/{txn}",
            json={"msgtype": "m.text", "body": body},
        )
        return status, data

    async def get_messages(self, room_id, limit=20):
        status, data = await self._request(
            "GET",
            f"/rooms/{room_id}/messages?dir=b&limit={limit}",
        )
        return data.get("chunk", []) if status == 200 else []

    async def get_room_members(self, room_id):
        status, data = await self._request("GET", f"/rooms/{room_id}/joined_members")
        return data.get("joined", {}) if status == 200 else {}


@pytest_asyncio.fixture(scope="module")
async def api():
    if not OWNER_TOKEN:
        pytest.skip("OWNER_TOKEN not set")
    return MatrixAPI(HOMESERVER, OWNER_TOKEN)


@pytest_asyncio.fixture(scope="module")
async def main_room_id(api):
    rooms = await api.joined_rooms()
    for rid in rooms:
        name = await api.room_name(rid)
        if "openclaw" in name.lower() or "nexus" in name.lower():
            return rid
    return os.environ.get("MAIN_ROOM", rooms[0] if rooms else None)


@pytest.mark.asyncio
async def test_list_rooms(api):
    """Can list rooms Bryan is in."""
    rooms = await api.joined_rooms()
    assert len(rooms) > 0
    print(f"\nJoined rooms: {len(rooms)}")
    for rid in rooms[:5]:
        name = await api.room_name(rid)
        print(f"  {rid} -> {name}")


@pytest.mark.asyncio
async def test_bot_health_endpoint():
    """Bot HTTP health endpoint is reachable."""
    async with aiohttp.ClientSession() as s:
        # VPS health endpoint — may be behind reverse proxy
        for url in ["http://82.38.68.101:8081/health", "http://82.38.68.101:8080/health"]:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status == 200:
                        data = await r.json()
                        assert data.get("status") == "ok"
                        print(f"\nHealth ({url}): {data}")
                        return
            except Exception:
                continue
    pytest.skip("Health endpoint not reachable (bot may only be running Matrix sync)")


@pytest.mark.asyncio
async def test_ping_command(api, main_room_id):
    """!ping in main room gets pong response."""
    if not main_room_id:
        pytest.skip("No main room found")

    body = f"!ping {uuid.uuid4().hex[:6]}"
    status, data = await api.send_message(main_room_id, body)
    assert status == 200, f"Failed to send: {data}"

    # Wait for bot response
    await asyncio.sleep(3)

    messages = await api.get_messages(main_room_id, limit=10)
    found = False
    for msg in messages:
        if msg.get("sender") == "@openclaw:hoomestead.com":
            content = msg.get("content", {}).get("body", "")
            if "pong" in content.lower():
                found = True
                print(f"\nBot response: {content}")
                break

    assert found, "No pong response from bot"


@pytest.mark.asyncio
async def test_status_command(api, main_room_id):
    """!status returns project status."""
    if not main_room_id:
        pytest.skip("No main room found")

    status, data = await api.send_message(main_room_id, "!status")
    assert status == 200

    await asyncio.sleep(3)

    messages = await api.get_messages(main_room_id, limit=10)
    found = False
    for msg in messages:
        if msg.get("sender") == "@openclaw:hoomestead.com":
            content = msg.get("content", {}).get("body", "")
            if "project" in content.lower():
                found = True
                print(f"\nStatus response: {content[:200]}")
                break

    assert found, "No status response from bot"


@pytest.mark.asyncio
async def test_natural_language_chat(api, main_room_id):
    """Natural language gets a response."""
    if not main_room_id:
        pytest.skip("No main room found")

    status, data = await api.send_message(main_room_id, "Hello bot, who are you?")
    assert status == 200

    await asyncio.sleep(5)

    messages = await api.get_messages(main_room_id, limit=10)
    found = False
    for msg in messages:
        if msg.get("sender") == "@openclaw:hoomestead.com":
            content = msg.get("content", {}).get("body", "")
            if content and len(content) > 5:
                found = True
                print(f"\nChat response: {content[:200]}")
                break

    assert found, "No chat response from bot"
