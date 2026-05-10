"""Nexus orchestrator for OpenClaw."""

from pathlib import Path

from openclaw.project import ProjectManager
from openclaw.matrix.commands import parse_command


class Nexus:
    """Orchestrates commands and natural language via Matrix."""

    def __init__(self, matrix_client, homeserver, main_room, ops_room, owner_id, data_dir):
        self.matrix_client = matrix_client
        self.homeserver = homeserver
        self.main_room = main_room
        self.ops_room = ops_room
        self.owner_id = owner_id
        self.data_dir = Path(data_dir)
        self.active_projects = {}
        self.llm_client = None

    async def handle_message(self, room_id, sender, body):
        """Route commands and natural language."""
        if sender != self.owner_id:
            return

        command = parse_command(body)

        if command is None:
            if self.llm_client is not None:
                response = await self.llm_client.chat(body)
                await self.matrix_client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={"body": response, "msgtype": "m.text"},
                )
            return

        if command.name == "ping":
            await self.matrix_client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={"body": "pong", "msgtype": "m.text"},
            )
            return

        if command.name == "plan":
            repo_url = command.args[0] if command.args else ""
            name = repo_url.split("/")[-1] if repo_url else ""
            pm = ProjectManager(
                matrix_client=self.matrix_client,
                data_dir=self.data_dir,
                owner_id=self.owner_id,
                github_token="",
            )
            project_room = await pm.create_project(repo_url=repo_url, name=name)
            self.active_projects[name] = {"room_id": project_room, "status": "running"}
            return

        if command.name == "status":
            lines = []
            for name, info in self.active_projects.items():
                lines.append(f"{name}: {info.get('status', 'unknown')}")
            text = "\n".join(lines) if lines else "No active projects."
            await self.matrix_client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={"body": text, "msgtype": "m.text"},
            )
            return
