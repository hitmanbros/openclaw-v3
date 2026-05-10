"""Nexus — main room orchestrator and chat agent."""

import asyncio
import json
from pathlib import Path

from openclaw.project import ProjectManager
from openclaw.matrix.commands import parse_command
from openclaw.llm.prompts import build_messages
from openclaw.pipeline.orchestrator import PipelineOrchestrator
from openclaw.subagent.workspace import WorkspaceClient


class Nexus:
    """Main room hub. Handles chat, commands, and spawns projects."""

    def __init__(self, matrix_client, homeserver, main_room, ops_room, owner_id, data_dir):
        self.matrix_client = matrix_client
        self.homeserver = homeserver
        self.main_room = main_room
        self.ops_room = ops_room
        self.owner_id = owner_id
        self.data_dir = Path(data_dir)
        self.active_projects = {}
        self.active_orchestrators = {}
        self.llm_client = None
        self._chat_history = []  # Simple in-memory history for context

    def _context(self):
        """Build room context string for prompt injection."""
        lines = [
            f"Active projects: {len(self.active_projects)}",
        ]
        for name, info in self.active_projects.items():
            lines.append(f"  - {name}: {info.get('status', 'unknown')} ({info.get('room_id', '')})")
        lines.append(f"Data directory: {self.data_dir}")
        lines.append(f"Main room: {self.main_room}")
        lines.append(f"Ops room: {self.ops_room}")
        return "\n".join(lines)

    async def handle_message(self, room_id, sender, body):
        """Route commands and natural language."""
        if sender != self.owner_id:
            return

        command = parse_command(body)

        # Project room commands (approve/reject)
        if room_id != self.main_room and room_id in self.active_orchestrators:
            if command and command.name in ("approve", "reject"):
                await self._handle_hitl(room_id, command.name)
                return
            # Other messages in project room are ignored for now
            return

        if command is None:
            # Natural language — use Nexus prompt + context
            await self._handle_chat(room_id, body)
            return

        # Explicit commands in main room
        if command.name == "ping":
            await self._send(room_id, "pong")
            return

        if command.name == "plan":
            await self._handle_plan(room_id, command.args)
            return

        if command.name == "status":
            await self._handle_status(room_id)
            return

        if command.name == "config":
            await self._handle_config(room_id, command.args)
            return

        if command.name == "help":
            await self._handle_help(room_id)
            return

        await self._send(room_id, f"Unknown command: `{command.name}`. Try `!help`.")

    async def _handle_hitl(self, room_id, decision):
        """Handle !approve or !reject in a project room."""
        ws_path = self.data_dir / room_id / ".pi" / "workspace.json"
        ws = WorkspaceClient(ws_path)
        data = ws.read()

        if decision == "approve":
            data["hitl"] = {"status": "approved"}
            ws.write(data)
            await self._send(room_id, "✅ Approved. Resuming pipeline...")
        else:
            data["hitl"] = {"status": "rejected"}
            ws.write(data)
            await self._send(room_id, "❌ Rejected. Project paused.")

    async def _handle_chat(self, room_id, body):
        """Natural language chat with full Nexus prompt and context."""
        if self.llm_client is None:
            await self._send(room_id, "LLM not configured. I can only respond to `!` commands.")
            return

        try:
            messages = build_messages(
                agent_name="nexus",
                user_message=body,
                room_context=self._context(),
                history=self._chat_history[-10:],  # last 10 messages for context
            )
            response = await self.llm_client.chat_text(messages=messages)

            # Store in history
            self._chat_history.append({"role": "user", "content": body})
            self._chat_history.append({"role": "assistant", "content": response})
            if len(self._chat_history) > 20:
                self._chat_history = self._chat_history[-20:]

            await self._send(room_id, response)
        except Exception as exc:
            await self._send(room_id, f"LLM error: {exc}")

    async def _handle_plan(self, room_id, args):
        """!plan <repo> — create project room, fork, clone, start pipeline."""
        repo_url = args[0] if args else ""
        if not repo_url:
            await self._send(room_id, "Usage: `!plan <github.com/owner/repo>`")
            return

        name = repo_url.split("/")[-1] if "/" in repo_url else repo_url
        await self._send(room_id, f"🚀 Starting project **{name}**...")

        pm = ProjectManager(
            matrix_client=self.matrix_client,
            data_dir=self.data_dir,
            owner_id=self.owner_id,
            github_token="",  # TODO: from env
        )
        try:
            project_room = await pm.create_project(repo_url=repo_url, name=name)
            self.active_projects[name] = {
                "room_id": project_room,
                "status": "running",
                "repo_url": repo_url,
            }
            await self._send(
                room_id,
                f"✅ Project **{name}** created!\n"
                f"📁 Room: `{project_room}`\n"
                f"Join the room to see progress.",
            )

            # Start pipeline in background
            workspace_dir = self.data_dir / project_room
            orchestrator = PipelineOrchestrator(
                workspace_dir=workspace_dir,
                matrix_client=self.matrix_client,
                room_id=project_room,
                owner_id=self.owner_id,
                nexus=self,
            )
            self.active_orchestrators[project_room] = orchestrator

            # Fire-and-forget pipeline task
            asyncio.create_task(orchestrator.run_full_pipeline(goal=f"Implement features for {name}"))

        except Exception as exc:
            await self._send(room_id, f"❌ Failed to create project: {exc}")

    async def _handle_status(self, room_id):
        """!status — show active projects."""
        if not self.active_projects:
            await self._send(room_id, "No active projects.")
            return

        lines = ["**Active projects:**"]
        for name, info in self.active_projects.items():
            status = info.get("status", "unknown")
            emoji = "🟢" if status == "running" else "🔴"
            lines.append(f"{emoji} **{name}**: {status}")
        await self._send(room_id, "\n".join(lines))

    async def _handle_config(self, room_id, args):
        """!config get/set/reset/help — runtime config management."""
        if not args:
            await self._send(room_id, "Usage: `!config get <key>` | `!config set <key> <value>` | `!config help`")
            return

        subcmd = args[0]
        if subcmd == "help":
            await self._send(
                room_id,
                "**Config keys:**\n"
                "- `worker_cap` — max parallel workers (1-10)\n"
                "- `daily_input_cap` — daily token limit\n"
                "- `hourly_input_cap` — hourly token limit\n"
                "- `model` — LLM model (kimi-k2.6)\n"
                "- `bash_timeout` — command timeout seconds\n"
            )
            return

        if subcmd == "get" and len(args) >= 2:
            key = args[1]
            config_path = self.data_dir / "config.json"
            if config_path.exists():
                data = json.loads(config_path.read_text())
                val = data.get(key, "(not set)")
            else:
                val = "(not set)"
            await self._send(room_id, f"`{key}` = {val}")
            return

        if subcmd == "set" and len(args) >= 3:
            key, value = args[1], args[2]
            config_path = self.data_dir / "config.json"
            if config_path.exists():
                data = json.loads(config_path.read_text())
            else:
                data = {}
            data[key] = value
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(data, indent=2))
            await self._send(room_id, f"`{key}` set to `{value}`")
            return

        await self._send(room_id, f"Unknown config subcommand: `{subcmd}`")

    async def _handle_help(self, room_id):
        """!help — list available commands."""
        await self._send(
            room_id,
            "**Commands:**\n"
            "- `!ping` — test bot connectivity\n"
            "- `!plan <repo>` — start a new project\n"
            "- `!status` — list active projects\n"
            "- `!config get/set/help` — manage runtime settings\n"
            "- `!help` — show this message\n"
            "\n"
            "Or just chat naturally — I understand context and can help plan, debug, or explain.",
        )

    async def _send(self, room_id, body):
        """Send a plain text message to a room."""
        await self.matrix_client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={"body": body, "msgtype": "m.text"},
        )

    async def post_to_main_room(self, message):
        """Post a message to the main room (used by EscalationManager)."""
        await self._send(self.main_room, message)
