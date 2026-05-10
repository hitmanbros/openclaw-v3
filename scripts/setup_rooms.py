#!/usr/bin/env python3
"""Create main + ops rooms and invite owner."""

import asyncio
import json
import os
import sys

import aiohttp

HOMESERVER = "https://matrix.hoomestead.com"
TOKEN = os.environ.get("MATRIX_TOKEN", "")
OWNER = os.environ.get("OWNER_MATRIX_ID", "@bryan:hoomestead.com")


async def create_room(session, name, invitees=None):
    """Create a room and return its ID."""
    url = f"{HOMESERVER}/_matrix/client/v3/createRoom"
    body = {
        "name": name,
        "preset": "private_chat",
        "is_direct": False,
    }
    if invitees:
        body["invite"] = invitees

    async with session.post(
        url,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json=body,
    ) as resp:
        data = await resp.json()
        if resp.status != 200:
            print(f"❌ Create room failed: {data}")
            sys.exit(1)
        return data["room_id"]


async def invite_user(session, room_id, user_id):
    """Invite a user to a room."""
    url = f"{HOMESERVER}/_matrix/client/v3/rooms/{room_id}/invite"
    async with session.post(
        url,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"user_id": user_id},
    ) as resp:
        if resp.status not in (200, 204):
            data = await resp.json()
            print(f"⚠️ Invite {user_id} to {room_id} failed: {data}")
        else:
            print(f"   ✅ Invited {user_id}")


async def main():
    if not TOKEN:
        print("❌ MATRIX_TOKEN not set")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        # Verify bot token works
        whoami_url = f"{HOMESERVER}/_matrix/client/v3/account/whoami"
        async with session.get(whoami_url, headers={"Authorization": f"Bearer {TOKEN}"}) as resp:
            whoami = await resp.json()
            if resp.status != 200:
                print(f"❌ Token invalid: {whoami}")
                sys.exit(1)
            print(f"Bot: {whoami.get('user_id')} (device: {whoami.get('device_id')})")

        # Create main room
        print("\nCreating main room...")
        main_room = await create_room(session, "OpenClaw Main")
        print(f"   ✅ Main room: {main_room}")
        await invite_user(session, main_room, OWNER)

        # Create ops room
        print("\nCreating ops room...")
        ops_room = await create_room(session, "OpenClaw Ops")
        print(f"   ✅ Ops room: {ops_room}")
        await invite_user(session, ops_room, OWNER)

        print("\n" + "=" * 50)
        print("Add these to your config.yaml:")
        print(f"  rooms:")
        print(f"    main: \"{main_room}\"")
        print(f"    ops:  \"{ops_room}\"")
        print("\nAccept the invites in your Matrix client to join.")


if __name__ == "__main__":
    asyncio.run(main())
