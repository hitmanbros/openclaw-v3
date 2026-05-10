"""Matrix client bot."""

from openclaw.matrix.commands import parse_command
from openclaw.config.validation import validate_config_key, ConfigValidationError


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

    async def handle_message(self, room_id, sender, body):
        """Handle an incoming message."""
        if sender != self.owner_id:
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
