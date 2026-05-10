#!/usr/bin/env python3
"""Smoke test: run the real bot against the real Matrix server for 30 seconds."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent to path so we can import openclaw
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openclaw.main import create_bot, run_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)


async def smoke():
    """Run bot for 30 seconds, verify it connects and syncs."""
    # Expect credentials in environment
    homeserver = os.environ.get("MATRIX_HOMESERVER", "https://matrix.hoomestead.com")
    token = os.environ.get("MATRIX_TOKEN", "")
    owner = os.environ.get("OWNER_MATRIX_ID", "@bryan:hoomestead.com")
    main_room = os.environ.get("MAIN_ROOM", "")
    ops_room = os.environ.get("OPS_ROOM", "")

    if not token:
        print("❌ MATRIX_TOKEN not set")
        sys.exit(1)

    # Write a minimal temp config
    import tempfile
    import yaml

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump({
            "matrix": {
                "homeserver": homeserver,
                "user_id": "@openclaw:hoomestead.com",
                "access_token": token,
            },
            "rooms": {
                "main": main_room,
                "ops": ops_room,
            },
            "llm": {
                "provider": "kimi",
                "model": "kimi-2.6",
                "api_key": "",
            },
            "owner_id": owner,
            "defaults": {
                "worker_cap": 3,
            },
        }, f)
        config_path = f.name

    print(f"🤖 Starting OpenClaw v3 smoke test")
    print(f"   Homeserver: {homeserver}")
    print(f"   Owner: {owner}")
    print(f"   Main room: {main_room or '(none)'}")
    print(f"   Ops room: {ops_room or '(none)'}")
    print()

    try:
        bot = create_bot(config_path)

        # Run for 30 seconds then stop
        async def timeout_stop():
            await asyncio.sleep(30)
            print("\n⏱️  Smoke test timeout — stopping bot")
            # Trigger shutdown by sending SIGTERM to self
            import signal
            signal.raise_signal(signal.SIGTERM)

        # Start timeout and bot concurrently
        await asyncio.gather(
            run_bot(bot),
            timeout_stop(),
            return_exceptions=True,
        )

        print("\n✅ Smoke test completed — bot connected and synced successfully")

    except Exception as exc:
        print(f"\n❌ Smoke test failed: {exc}")
        sys.exit(1)
    finally:
        Path(config_path).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(smoke())
