"""Tests for subagent IPC (workspace, inbox, snapshot)."""

import pytest
import tempfile
from pathlib import Path
import json
import time

from openclaw.subagent.workspace import WorkspaceClient
from openclaw.subagent.inbox import InboxClient
from openclaw.subagent.snapshot import SnapshotManager


class TestWorkspaceClient:
    """Workspace read/write behavior."""

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            workspace_dir = Path(d) / ".pi"
            workspace_dir.mkdir()
            yield workspace_dir

    def test_read_missing_file_returns_empty_dict(self, temp_workspace):
        """Reading a missing workspace returns empty dict."""
        client = WorkspaceClient(temp_workspace / "workspace.json")
        data = client.read()
        assert data == {}

    def test_write_and_read_roundtrip(self, temp_workspace):
        """Written data can be read back."""
        client = WorkspaceClient(temp_workspace / "workspace.json")
        client.write({"key": "value", "nested": {"a": 1}})
        
        data = client.read()
        assert data["key"] == "value"
        assert data["nested"]["a"] == 1

    def test_read_merges_with_defaults(self, temp_workspace):
        """Read merges stored data with default values."""
        client = WorkspaceClient(temp_workspace / "workspace.json")
        client.write({"custom": "data"})
        
        data = client.read(defaults={"default_key": "default_value"})
        assert data["custom"] == "data"
        assert data["default_key"] == "default_value"

    def test_update_patches_existing_data(self, temp_workspace):
        """Update merges new data with existing."""
        client = WorkspaceClient(temp_workspace / "workspace.json")
        client.write({"a": 1, "b": 2})
        client.update({"b": 3, "c": 4})
        
        data = client.read()
        assert data["a"] == 1
        assert data["b"] == 3
        assert data["c"] == 4

    def test_concurrent_reads_are_safe(self, temp_workspace):
        """Multiple reads don't corrupt data."""
        client = WorkspaceClient(temp_workspace / "workspace.json")
        client.write({"counter": 0})
        
        data1 = client.read()
        data2 = client.read()
        assert data1 == data2


class TestInboxClient:
    """Inbox messaging behavior."""

    @pytest.fixture
    def temp_inbox(self):
        with tempfile.TemporaryDirectory() as d:
            inbox_path = Path(d) / ".pi" / "inbox.json"
            inbox_path.parent.mkdir()
            yield inbox_path

    def test_send_message_adds_to_inbox(self, temp_inbox):
        """Sending a message adds it to the inbox."""
        client = InboxClient(temp_inbox)
        client.send(from_agent="orchestrator", to_agent="worker", content="do task")
        
        messages = client.read_all()
        assert len(messages) == 1
        assert messages[0]["from"] == "orchestrator"
        assert messages[0]["to"] == "worker"
        assert messages[0]["content"] == "do task"

    def test_read_for_agent_filters_messages(self, temp_inbox):
        """Read returns only messages for the specified agent."""
        client = InboxClient(temp_inbox)
        client.send(from_agent="orchestrator", to_agent="worker-1", content="task 1")
        client.send(from_agent="orchestrator", to_agent="worker-2", content="task 2")
        
        messages = client.read_for("worker-1")
        assert len(messages) == 1
        assert messages[0]["content"] == "task 1"

    def test_read_marks_messages_as_read(self, temp_inbox):
        """Reading messages marks them as read."""
        client = InboxClient(temp_inbox)
        client.send(from_agent="orchestrator", to_agent="worker", content="task")
        
        client.read_for("worker")
        unread = client.read_unread_for("worker")
        assert len(unread) == 0

    def test_multiple_sends_preserve_order(self, temp_inbox):
        """Messages maintain insertion order."""
        client = InboxClient(temp_inbox)
        client.send(from_agent="a", to_agent="worker", content="first")
        client.send(from_agent="b", to_agent="worker", content="second")
        
        messages = client.read_all()
        assert messages[0]["content"] == "first"
        assert messages[1]["content"] == "second"


class TestSnapshotManager:
    """Snapshot creation and restore behavior."""

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d)
            (workspace / "src").mkdir()
            (workspace / "src" / "main.py").write_text("original")
            yield workspace

    def test_create_snapshot_copies_files(self, temp_workspace):
        """Snapshot creates a copy of workspace files."""
        mgr = SnapshotManager(temp_workspace)
        mgr.create("slice-1")
        
        snapshot = temp_workspace / ".pi" / "snapshots" / "slice-1"
        assert snapshot.exists()
        assert (snapshot / "src" / "main.py").exists()
        assert (snapshot / "src" / "main.py").read_text() == "original"

    def test_restore_reverts_changes(self, temp_workspace):
        """Restore reverts files to snapshot state."""
        mgr = SnapshotManager(temp_workspace)
        mgr.create("slice-1")
        
        # Modify the file
        (temp_workspace / "src" / "main.py").write_text("modified")
        
        # Restore
        mgr.restore("slice-1")
        assert (temp_workspace / "src" / "main.py").read_text() == "original"

    def test_restore_deletes_new_files(self, temp_workspace):
        """Restore removes files created after snapshot."""
        mgr = SnapshotManager(temp_workspace)
        mgr.create("slice-1")
        
        # Add a new file
        (temp_workspace / "src" / "new.py").write_text("new")
        
        # Restore
        mgr.restore("slice-1")
        assert not (temp_workspace / "src" / "new.py").exists()

    def test_cleanup_removes_old_snapshots(self, temp_workspace):
        """Cleanup removes snapshots beyond keep limit."""
        mgr = SnapshotManager(temp_workspace, keep=2)
        mgr.create("slice-1")
        mgr.create("slice-2")
        mgr.create("slice-3")
        
        mgr.cleanup()
        
        snapshots_dir = temp_workspace / ".pi" / "snapshots"
        assert not (snapshots_dir / "slice-1").exists()
        assert (snapshots_dir / "slice-2").exists()
        assert (snapshots_dir / "slice-3").exists()
