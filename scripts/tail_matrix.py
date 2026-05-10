#!/usr/bin/env python3
"""Real-time Matrix room monitor — prints all messages as they arrive."""

import asyncio
import logging
import os
import time

from nio import AsyncClient, RoomMessageText

# Suppress noisy nio logs
logging.getLogger("nio").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)

HOMESERVER = os.environ.get("MATRIX_HOMESERVER", "https://matrix.hoomestead.com")
TOKEN = os.environ.get("MATRIX_TOKEN", "")
USER_ID = os.environ.get("MATRIX_USER_ID", "@openclaw:hoomestead.com")


def fmt(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts / 1000))


async def main():
    if not TOKEN:
        print("❌ MATRIX_TOKEN not set")
        return

    client = AsyncClient(HOMESERVER, USER_ID)
    client.access_token = TOKEN
    client.user_id = USER_ID
    client.device_id = "tail-monitor"
    startup_ts = int(time.time() * 1000)

    async def on_message(room, event):
        if event.sender == USER_ID:
            return
        if event.server_timestamp < startup_ts:
            return
        ts = fmt(event.server_timestamp)
        room_name = room.display_name or room.room_id
        line = f"[{ts}] [{room_name}] {event.sender}: {event.body}"
        print(line, flush=True)
        # Persist to file so I can read it later
        with open("/home/bryan/openclaw-v3/matrix_messages.log", "a") as f:
            f.write(line + "\n")

    client.add_event_callback(on_message, RoomMessageText)

    await client.sync(timeout=10000, full_state=True)

    try:
        await client.sync_forever(timeout=30000)
    except KeyboardInterrupt:
        pass
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
