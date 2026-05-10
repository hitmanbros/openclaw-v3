"""OpenClaw bot entry point."""

import asyncio
import signal

from nio import AsyncClient

from openclaw.config.loader import ConfigLoader
from openclaw.matrix.client import MatrixBot


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

    return bot


async def run_bot(bot):
    """Log in, join rooms, and start syncing with graceful shutdown."""
    shutdown_event = asyncio.Event()

    def _shutdown():
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    try:
        await bot.client.login(bot.access_token)

        for room in (bot.main_room, bot.ops_room):
            result = bot.client.join(room)
            if asyncio.iscoroutine(result):
                await result

        sync_task = asyncio.create_task(bot.client.sync_forever())

        try:
            await shutdown_event.wait()
        finally:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
