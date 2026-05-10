"""OpenClaw bot entry point."""

import asyncio
import logging
import signal

from nio import AsyncClient

from openclaw.config.loader import ConfigLoader
from openclaw.matrix.client import MatrixBot
from openclaw.nexus import Nexus

log = logging.getLogger("openclaw.main")


class MockLLMClient:
    """Simple mock LLM client for chat responses."""

    async def chat(self, message):
        return "Mock response"


def create_bot(config_path):
    """Load config and construct a MatrixBot with all dependencies."""
    loader = ConfigLoader(config_path)
    config = loader.load()

    matrix_config = config["matrix"]
    rooms_config = config["rooms"]

    bot = MatrixBot(
        homeserver=matrix_config["homeserver"],
        user_id=matrix_config["user_id"],
        access_token=matrix_config["access_token"],
        owner_id=config["owner_id"],
        main_room=rooms_config["main"],
        ops_room=rooms_config["ops"],
    )

    bot.client = AsyncClient(
        homeserver=matrix_config["homeserver"],
        user=matrix_config["user_id"],
    )

    bot.llm_client = MockLLMClient()

    # Flatten defaults and llm settings for runtime config access
    bot.config = {**config.get("defaults", {}), **config.get("llm", {})}

    # Wire Nexus for main room orchestration
    bot.nexus = Nexus(
        matrix_client=bot.client,
        homeserver=matrix_config["homeserver"],
        main_room=rooms_config["main"],
        ops_room=rooms_config["ops"],
        owner_id=config["owner_id"],
        data_dir=config.get("data_dir", "/data/projects"),
    )

    return bot


async def run_bot(bot):
    """Log in, join rooms, register callbacks, and start syncing."""
    shutdown_event = asyncio.Event()

    def _shutdown():
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    try:
        log.info("Logging in as %s", bot.user_id)
        await bot.client.login(bot.access_token)
        log.info("Login successful")

        # Register message callbacks before syncing
        bot._register_callbacks()

        # Join configured rooms
        for room in (bot.main_room, bot.ops_room):
            if room:
                try:
                    result = await bot.client.join(room)
                    log.info("Joined room %s", room)
                except Exception as exc:
                    log.warning("Could not join room %s: %s", room, exc)

        # Post startup message to ops room
        if bot.ops_room:
            try:
                await bot.client.room_send(
                    room_id=bot.ops_room,
                    message_type="m.room.message",
                    content={
                        "body": "OpenClaw v3 bot started",
                        "msgtype": "m.text",
                    },
                )
            except Exception as exc:
                log.warning("Could not post to ops room: %s", exc)

        log.info("Starting sync loop")
        sync_task = asyncio.create_task(bot.client.sync_forever())

        try:
            await shutdown_event.wait()
        finally:
            log.info("Shutting down...")
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
        await bot.client.close()
