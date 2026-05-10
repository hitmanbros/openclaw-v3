#!/usr/bin/env python3
"""Fetch recent messages from Matrix rooms via REST API."""

import asyncio
import json
import os
from datetime import datetime

import aiohttp

HOMESERVER = os.environ.get("MATRIX_HOMESERVER", "https://matrix.hoomestead.com")
TOKEN = os.environ.get("MATRIX_TOKEN", "")


async def fetch_room_messages(room_id, limit=20):
    """Fetch recent messages from a room."""
    url = f"{HOMESERVER}/_matrix/client/v3/rooms/{room_id}/messages?dir=b&limit={limit}"
    headers = {"Authorization": f"Bearer {TOKEN}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

    messages = []
    for ev in data.get("chunk", []):
        if ev.get("type") != "m.room.message":
            continue
        content = ev.get("content", {})
        if content.get("msgtype") != "m.text":
            continue
        ts = ev.get("origin_server_ts", 0)
        messages.append({
            "ts": ts,
            "time": datetime.fromtimestamp(ts / 1000).strftime("%H:%M:%S"),
            "sender": ev["sender"],
            "body": content.get("body", ""),
            "event_id": ev["event_id"],
        })

    # Reverse so newest is last
    messages.reverse()
    return messages


async def main():
    rooms = os.environ.get("MATRIX_ROOMS", "").split(",")
    if not TOKEN:
        print("❌ MATRIX_TOKEN not set")
        return

    for room_id in rooms:
        room_id = room_id.strip()
        if not room_id:
            continue

        msgs = await fetch_room_messages(room_id)
        if not msgs:
            continue

        print(f"\n{'=' * 50}")
        print(f"Room: {room_id}")
        print(f"{'=' * 50}")
        for m in msgs:
            marker = "→" if m["sender"] == "@bryan:hoomestead.com" else "  "
            print(f"{marker} [{m['time']}] {m['sender']}: {m['body']}")


if __name__ == "__main__":
    asyncio.run(main())
