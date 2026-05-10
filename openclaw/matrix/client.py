"""Matrix client bot."""

import logging
import time

from nio import RoomMessageText, InviteMemberEvent

from openclaw.matrix.commands import parse_command
from openclaw.config.validation import validate_config_key, ConfigValidationError

log = logging.getLogger("openclaw.matrix")


class MatrixBot:
    """Matrix bot for OpenClaw."""

    def __init__(self, homeserver, user_id, access_token, owner_id, main_room, ops_room):
        self.homeserver = homeserver
        self.user_id = user_id
        self.access_token = access_token
        self.owner_id = owner_id
        self.main_room = main_room
        self.ops_room = ops_room
        self.client = None
        self.llm_client = None
        self.config = {}
        self.nexus = None
        self._startup_ts_ms = int(time.time() * 1000)

    def _register_callbacks(self):
        """Wire nio event callbacks to handlers."""
        self.client.add_event_callback(self._on_room_message, RoomMessageText)
        self.client.add_event_callback(self._on_invite, InviteMemberEvent)

    async def _on_room_message(self, room, event):
        """nio callback for RoomMessageText events."""
        if event.sender == self.user_id:
            return  # ignore self

        # Ignore events older than process start (replayed on reconnect)
        if hasattr(event, "server_timestamp") and event.server_timestamp < self._startup_ts_ms:
            return

        body = event.body or ""
        log.info("[%s] %s: %s", room.room_id, event.sender, body[:80])
        await self.handle_message(room.room_id, event.sender, body)

    async def _on_invite(self, room, event):
        """Auto-join rooms we're invited to."""
        if event.sender == self.user_id:
            return
        log.info("Invited to %s by %s — joining", room.room_id, event.sender)
        try:
            await self.client.join(room.room_id)
        except Exception as exc:
            log.warning("Failed to join %s: %s", room.room_id, exc)

    async def handle_message(self, room_id, sender, body):
        """Handle an incoming message."""
        if sender != self.owner_id:
            return

        if room_id == self.main_room and self.nexus is not None:
            await self.nexus.handle_message(room_id, sender, body)
            return

        command = parse_command(body)

        if command is None:
            if self.llm_client is not None:
                response = await self.llm_client.chat(body)
                await self.client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={"body": response, "msgtype": "m.text"},
                )
            return

        if command.name == "ping":
            await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={"body": "pong", "msgtype": "m.text"},
            )
            return

        if command.name == "config":
            if len(command.args) >= 2 and command.args[0] == "get":
                key = command.args[1]
                value = self.config.get(key, "(not set)")
                await self.client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={"body": str(value), "msgtype": "m.text"},
                )
                return

            if len(command.args) >= 3 and command.args[0] == "set":
                key = command.args[1]
                raw_value = command.args[2]
                try:
                    value = validate_config_key(key, raw_value)
                    self.config[key] = value
                    await self.client.room_send(
                        room_id=room_id,
                        message_type="m.room.message",
                        content={"body": f"{key} set to {value}", "msgtype": "m.text"},
                    )
                except ConfigValidationError as exc:
                    await self.client.room_send(
                        room_id=room_id,
                        message_type="m.room.message",
                        content={"body": str(exc), "msgtype": "m.text"},
                    )
                return

        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={"body": f"Unknown command: {command.name}", "msgtype": "m.text"},
        )
