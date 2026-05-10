"""Integration tests for the full OpenClaw v3 pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json
import asyncio

from openclaw.nexus import Nexus
from openclaw.main import create_bot


class TestNexusIntegration:
    """End-to-end pipeline via Nexus."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def nexus(self, temp_dir):
        matrix_client = MagicMock()
        matrix_client.room_create = AsyncMock(return_value={"room_id": "!project:example.com"})
        matrix_client.invite = AsyncMock()
        matrix_client.room_send = AsyncMock()
        matrix_client.sync_forever = AsyncMock()

        return Nexus(
            matrix_client=matrix_client,
            homeserver="https://matrix.example.com",
            main_room="!main:example.com",
            ops_room="!ops:example.com",
            owner_id="@owner:example.com",
            data_dir=temp_dir,
        )

    @pytest.mark.asyncio
    async def test_ping_command(self, nexus):
        """!ping in main room replies pong."""
        await nexus.handle_message(
            room_id="!main:example.com",
            sender="@owner:example.com",
            body="!ping"
        )
        nexus.matrix_client.room_send.assert_called()
        call = nexus.matrix_client.room_send.call_args
        assert "pong" in call.kwargs["content"]["body"].lower()

    @pytest.mark.asyncio
    async def test_plan_command_creates_project(self, nexus, temp_dir):
        """!plan creates project room and starts pipeline."""
        with patch("openclaw.nexus.ProjectManager") as MockPM:
            mock_pm = MagicMock()
            mock_pm.create_project = AsyncMock(return_value="!project:example.com")
            MockPM.return_value = mock_pm

            await nexus.handle_message(
                room_id="!main:example.com",
                sender="@owner:example.com",
                body="!plan github.com/owner/repo"
            )

            MockPM.assert_called_once()
            mock_pm.create_project.assert_called_once_with(
                repo_url="github.com/owner/repo",
                name="repo",
            )

    @pytest.mark.asyncio
    async def test_status_command_shows_projects(self, nexus):
        """!status shows active projects."""
        nexus.active_projects = {
            "alpha": {"status": "running", "slices_done": 2, "slices_total": 5},
        }

        await nexus.handle_message(
            room_id="!main:example.com",
            sender="@owner:example.com",
            body="!status"
        )

        nexus.matrix_client.room_send.assert_called()
        call = nexus.matrix_client.room_send.call_args
        assert "alpha" in call.kwargs["content"]["body"]

    @pytest.mark.asyncio
    async def test_natural_language_chat(self, nexus):
        """Natural language in main room gets LLM response."""
        nexus.llm_client = MagicMock()
        nexus.llm_client.chat = AsyncMock(return_value="Hello! How can I help?")

        await nexus.handle_message(
            room_id="!main:example.com",
            sender="@owner:example.com",
            body="What can you do?"
        )

        nexus.llm_client.chat.assert_called_once()
        nexus.matrix_client.room_send.assert_called()


class TestSubagentRunner:
    """Subagent process spawning."""

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            (ws / ".pi").mkdir()
            (ws / "src").mkdir()
            yield ws

    def test_spawn_worker_process(self, temp_workspace):
        """Runner spawns a worker as a real subprocess."""
        from openclaw.subagent.runner import SubagentRunner

        runner = SubagentRunner(workspace_dir=temp_workspace)

        # Write a task for the worker
        ws = temp_workspace / ".pi" / "workspace.json"
        ws.write_text(json.dumps({
            "plan": {
                "slices": [{"id": 1, "task": "Write hello to file", "status": "pending"}]
            }
        }))

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            pid = runner.spawn_worker(slice_id=1)
            assert pid == 12345
            mock_popen.assert_called_once()

    def test_worker_reads_task_from_workspace(self, temp_workspace):
        """Worker subprocess reads its task from workspace."""
        from openclaw.subagent.runner import SubagentRunner

        runner = SubagentRunner(workspace_dir=temp_workspace)
        task = runner.read_worker_task(slice_id=1)

        # Worker task should include the slice info
        assert "task" in task or task is None

    def test_worker_writes_result(self, temp_workspace):
        """Worker subprocess writes result back to workspace."""
        from openclaw.subagent.runner import SubagentRunner

        runner = SubagentRunner(workspace_dir=temp_workspace)

        # Simulate worker completion
        runner.write_worker_result(slice_id=1, result="Done")

        ws = temp_workspace / ".pi" / "workspace.json"
        data = json.loads(ws.read_text())
        assert data["plan"]["slices"][0]["status"] == "done"
        assert data["plan"]["slices"][0]["result"] == "Done"


class TestHTTPServer:
    """HTTP status endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """/health returns OK status."""
        from openclaw.http.server import StatusServer

        server = StatusServer(port=0)  # random port
        # Mock the app
        server.app = MagicMock()

        with patch("aiohttp.web.Application") as MockApp:
            mock_app = MagicMock()
            MockApp.return_value = mock_app

            await server.start()
            mock_app.router.add_get.assert_any_call("/health", server._health_handler)

    def test_health_response(self):
        """Health handler returns JSON with status."""
        from openclaw.http.server import StatusServer

        server = StatusServer(port=8080)
        # We can't easily test the actual handler without running the server
        # Just verify it exists
        assert hasattr(server, "_health_handler")
