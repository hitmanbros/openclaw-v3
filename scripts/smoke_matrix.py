#!/usr/bin/env python3
"""Smoke test: verify bot can connect to real Matrix server."""

import asyncio
import os
import sys
import uuid

import aiohttp


HOMESERVER = os.environ.get("MATRIX_HOMESERVER", "https://matrix.hoomestead.com")
TOKEN = os.environ.get("MATRIX_TOKEN", "")
USER_ID = os.environ.get("MATRIX_USER_ID", "@openclaw:hoomestead.com")


async def whoami() -> dict:
    """Verify token works."""
    url = f"{HOMESERVER}/_matrix/client/v3/account/whoami"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"Authorization": f"Bearer {TOKEN}"}) as resp:
            body = await resp.json()
            return {"status": resp.status, "body": body}


async def sync_once() -> dict:
    """One-shot sync to verify event listening."""
    url = f"{HOMESERVER}/_matrix/client/v3/sync"
    params = {"timeout": 30000, "limit": 1}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={"Authorization": f"Bearer {TOKEN}"},
            params=params,
        ) as resp:
            body = await resp.json()
            return {"status": resp.status, "next_batch": body.get("next_batch")}


async def main():
    print(f"Matrix smoke test for {USER_ID}")
    print(f"Homeserver: {HOMESERVER}")
    print()

    if not TOKEN:
        print("❌ MATRIX_TOKEN not set")
        sys.exit(1)

    # Test 1: whoami
    print("1. Testing /account/whoami ...")
    result = await whoami()
    if result["status"] == 200:
        print(f"   ✅ Auth OK — device: {result['body'].get('device_id')}")
    else:
        print(f"   ❌ Auth failed: {result['body']}")
        sys.exit(1)

    # Test 2: sync
    print("2. Testing /sync ...")
    result = await sync_once()
    if result["status"] == 200:
        print(f"   ✅ Sync OK — next_batch: {result['next_batch'][:20]}...")
    else:
        print(f"   ❌ Sync failed: {result}")
        sys.exit(1)

    print()
    print("All smoke tests passed. Bot can connect to Matrix.")


if __name__ == "__main__":
    asyncio.run(main())
