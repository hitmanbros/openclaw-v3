"""Tests for project room lifecycle."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile

from openclaw.project import ProjectManager


class TestProjectManager:
    """Project room creation behavior."""

    @pytest.fixture
    def temp_data_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def manager(self, temp_data_dir):
        client = MagicMock()
        client.room_create = AsyncMock(return_value={"room_id": "!newroom:example.com"})
        client.invite = AsyncMock()
        client.room_send = AsyncMock()
        
        return ProjectManager(
            matrix_client=client,
            data_dir=temp_data_dir,
            owner_id="@owner:example.com",
            github_token="ghp_test",
        )

    @pytest.mark.asyncio
    async def test_create_project_room(self, manager):
        """!plan creates a new Matrix room."""
        room_id = await manager.create_project(
            repo_url="github.com/owner/repo",
            name="alpha",
        )
        
        assert room_id == "!newroom:example.com"
        manager.matrix_client.room_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_invite_owner_to_room(self, manager):
        """Owner is invited to the new project room."""
        await manager.create_project(
            repo_url="github.com/owner/repo",
            name="alpha",
        )
        
        manager.matrix_client.invite.assert_called_once_with(
            "!newroom:example.com",
            "@owner:example.com",
        )

    @pytest.mark.asyncio
    async def test_creates_workspace_directory(self, manager, temp_data_dir):
        """Workspace directory is created for the project."""
        await manager.create_project(
            repo_url="github.com/owner/repo",
            name="alpha",
        )
        
        workspace = temp_data_dir / "!newroom:example.com"
        assert workspace.exists()
        assert (workspace / ".pi").exists()
        assert (workspace / "src").exists()

    @pytest.mark.asyncio
    async def test_writes_workspace_json(self, manager, temp_data_dir):
        """workspace.json is seeded with project metadata."""
        await manager.create_project(
            repo_url="github.com/owner/repo",
            name="alpha",
        )
        
        workspace_json = temp_data_dir / "!newroom:example.com" / ".pi" / "workspace.json"
        assert workspace_json.exists()
        
        import json
        data = json.loads(workspace_json.read_text())
        assert data["config"]["repo_url"] == "github.com/owner/repo"
        assert data["config"]["name"] == "alpha"

    @pytest.mark.asyncio
    async def test_sets_room_state(self, manager):
        """com.openclaw.project state event is set."""
        await manager.create_project(
            repo_url="github.com/owner/repo",
            name="alpha",
        )
        
        manager.matrix_client.room_send.assert_called()
        # Check that a state event was sent
        calls = manager.matrix_client.room_send.call_args_list
        state_calls = [c for c in calls if c.kwargs.get("content", {}).get("name") == "alpha"]
        assert len(state_calls) > 0

    @pytest.mark.asyncio
    async def test_close_project(self, manager, temp_data_dir):
        """!close archives the project room."""
        await manager.create_project(
            repo_url="github.com/owner/repo",
            name="alpha",
        )
        
        await manager.close_project("!newroom:example.com")
        
        # Workspace should still exist but be marked archived
        workspace_json = temp_data_dir / "!newroom:example.com" / ".pi" / "workspace.json"
        import json
        data = json.loads(workspace_json.read_text())
        assert data["config"]["status"] == "archived"

    @pytest.mark.asyncio
    async def test_short_name_lookup(self, manager):
        """Project short names resolve to repo URLs."""
        manager.project_registry = {
            "alpha": {"repo": "github.com/owner/alpha"},
        }
        
        repo = manager.resolve_repo("alpha")
        assert repo == "github.com/owner/alpha"

    @pytest.mark.asyncio
    async def test_short_name_not_found(self, manager):
        """Unknown short name returns None."""
        manager.project_registry = {}
        
        repo = manager.resolve_repo("unknown")
        assert repo is None
