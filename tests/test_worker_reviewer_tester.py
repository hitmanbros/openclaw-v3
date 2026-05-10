"""Tests for worker, reviewer, and tester agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from openclaw.agents.worker import WorkerAgent
from openclaw.agents.reviewer import ReviewerAgent
from openclaw.agents.tester import TesterAgent
from openclaw.tools.registry import ToolRegistry


class TestWorkerAgent:
    """Worker code implementation behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / "src").mkdir()
            (proj / ".pi").mkdir()
            (proj / ".pi" / "snapshots").mkdir()
            yield proj

    def test_worker_reads_slice_task(self, temp_project):
        """Worker reads its assigned slice from workspace."""
        workspace = temp_project / ".pi" / "workspace.json"
        workspace.write_text(json.dumps({
            "plan": {"slices": [{"id": 1, "task": "Add auth", "criteria": ["JWT works"]}]}
        }))
        
        worker = WorkerAgent(workspace_dir=temp_project, slice_id=1)
        task = worker.read_task()
        assert task == "Add auth"

    def test_worker_executes_tools(self, temp_project):
        """Worker can execute tools from the registry."""
        worker = WorkerAgent(workspace_dir=temp_project, slice_id=1)
        
        with patch.object(worker.tools, "execute", return_value="file content") as mock_exec:
            result = worker.run_tool("read", {"path": "src/main.py"})
            assert result == "file content"
            mock_exec.assert_called_once_with("read", {"path": "src/main.py"})

    def test_worker_blocks_path_escape(self, temp_project):
        """Worker raises ValueError when tool arguments escape workspace."""
        worker = WorkerAgent(workspace_dir=temp_project, slice_id=1)
        
        with patch.object(worker.tools, "execute"):
            with pytest.raises(ValueError, match="Path escapes workspace"):
                worker.run_tool("read", {"path": "../../../etc/passwd"})
            
            with pytest.raises(ValueError, match="Path escapes workspace"):
                worker.run_tool("read", {"path": "/etc/passwd"})
            
            with pytest.raises(ValueError, match="Path escapes workspace"):
                worker.run_tool("read", {"path": ["../escape.txt"]})

    def test_worker_allows_valid_paths(self, temp_project):
        """Worker allows paths inside workspace."""
        worker = WorkerAgent(workspace_dir=temp_project, slice_id=1)
        
        with patch.object(worker.tools, "execute", return_value="ok") as mock_exec:
            result = worker.run_tool("read", {"path": "src/main.py"})
            assert result == "ok"
            mock_exec.assert_called_once_with("read", {"path": "src/main.py"})

    def test_worker_writes_result_to_workspace(self, temp_project):
        """Worker writes completion result to workspace."""
        workspace = temp_project / ".pi" / "workspace.json"
        workspace.write_text(json.dumps({
            "plan": {"slices": [{"id": 1, "task": "Add auth", "criteria": ["JWT works"], "status": "pending"}]}
        }))
        
        worker = WorkerAgent(workspace_dir=temp_project, slice_id=1)
        worker.complete(result="Implemented auth in auth.py")
        
        data = json.loads(workspace.read_text())
        slice_data = data["plan"]["slices"][0]
        assert slice_data["status"] == "done"
        assert slice_data["result"] == "Implemented auth in auth.py"

    def test_worker_is_leaf_node(self, temp_project):
        """Worker cannot spawn other agents."""
        worker = WorkerAgent(workspace_dir=temp_project, slice_id=1)
        assert not hasattr(worker, "spawn_agent")


class TestReviewerAgent:
    """Reviewer verification behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / "src").mkdir()
            (proj / ".pi").mkdir()
            (proj / "src" / "auth.py").write_text("def login(): pass")
            yield proj

    def test_reviewer_is_read_only(self, temp_project):
        """Reviewer cannot write files."""
        reviewer = ReviewerAgent(workspace_dir=temp_project)
        assert "write" not in reviewer.allowed_tools
        assert "edit" not in reviewer.allowed_tools

    def test_reviewer_restricts_tools_at_init(self, temp_project):
        """Reviewer restricts its tool registry to allowed_tools on init."""
        with patch.object(ToolRegistry, "restrict_to") as mock_restrict:
            reviewer = ReviewerAgent(workspace_dir=temp_project)
            mock_restrict.assert_called_once_with(reviewer.allowed_tools)

    def test_reviewer_restricts_tools(self, temp_project):
        """Reviewer registry only keeps allowed tools after restrict_to."""
        reviewer = ReviewerAgent(workspace_dir=temp_project)
        reviewer.tools.register("read", lambda: None, {"reviewer"})
        reviewer.tools.register("write", lambda: None, {"reviewer"})
        reviewer.tools.register("edit", lambda: None, {"reviewer"})
        reviewer.tools.register("grep", lambda: None, {"reviewer"})
        reviewer.tools.restrict_to(reviewer.allowed_tools)
        
        assert "read" in reviewer.tools._tools
        assert "grep" in reviewer.tools._tools
        assert "write" not in reviewer.tools._tools
        assert "edit" not in reviewer.tools._tools

    def test_reviewer_checks_criteria(self, temp_project):
        """Reviewer verifies slice criteria are met."""
        reviewer = ReviewerAgent(workspace_dir=temp_project)
        
        with patch.object(reviewer, "_call_llm", return_value=json.dumps({
            "pass": True,
            "findings": ["Auth correctly implemented"]
        })):
            result = reviewer.review(slice_id=1, criteria=["JWT works"])
            assert result["pass"] is True

    def test_reviewer_blocks_on_failure(self, temp_project):
        """Reviewer returns pass=False when criteria not met."""
        reviewer = ReviewerAgent(workspace_dir=temp_project)
        
        with patch.object(reviewer, "_call_llm", return_value=json.dumps({
            "pass": False,
            "findings": ["Missing JWT validation"]
        })):
            result = reviewer.review(slice_id=1, criteria=["JWT works"])
            assert result["pass"] is False
            assert "Missing JWT validation" in result["findings"]

    def test_reviewer_does_not_write_to_workspace(self, temp_project):
        """Reviewer returns findings without writing to workspace."""
        workspace = temp_project / ".pi" / "workspace.json"
        workspace.write_text(json.dumps({
            "plan": {"slices": [{"id": 1, "task": "Add auth", "criteria": ["JWT works"]}]}
        }))
        
        reviewer = ReviewerAgent(workspace_dir=temp_project)
        
        with patch.object(reviewer, "_call_llm", return_value=json.dumps({
            "pass": True,
            "findings": ["Good"]
        })):
            result = reviewer.review(slice_id=1, criteria=["JWT works"])
            
            assert result["pass"] is True
            assert result["findings"] == ["Good"]
            
            data = json.loads(workspace.read_text())
            assert "review" not in data["plan"]["slices"][0]

    def test_reviewer_handles_invalid_json(self, temp_project):
        """Reviewer raises ValueError when LLM returns invalid JSON."""
        reviewer = ReviewerAgent(workspace_dir=temp_project)
        
        with patch.object(reviewer, "_call_llm", return_value="not json"):
            with pytest.raises(ValueError, match="Invalid JSON from LLM"):
                reviewer.review(slice_id=1, criteria=["JWT works"])


class TestTesterAgent:
    """Tester validation behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / "src").mkdir()
            (proj / ".pi").mkdir()
            yield proj

    def test_tester_runs_tests(self, temp_project):
        """Tester executes test commands via bash tool."""
        tester = TesterAgent(workspace_dir=temp_project)
        
        with patch.object(tester.tools, "execute", return_value={
            "stdout": "3 passed",
            "stderr": "",
            "returncode": 0
        }) as mock_exec:
            result = tester.run_tests(test_cmd="pytest")
            assert result["passed"] is True
            mock_exec.assert_called_once_with("bash", {"command": "pytest"})

    def test_tester_detects_failures(self, temp_project):
        """Tester detects test failures via returncode."""
        tester = TesterAgent(workspace_dir=temp_project)
        
        with patch.object(tester.tools, "execute", return_value={
            "stdout": "1 failed",
            "stderr": "",
            "returncode": 1
        }):
            result = tester.run_tests(test_cmd="pytest")
            assert result["passed"] is False

    def test_tester_writes_results_to_workspace(self, temp_project):
        """Tester writes test results to workspace."""
        workspace = temp_project / ".pi" / "workspace.json"
        workspace.write_text(json.dumps({
            "plan": {"slices": [{"id": 1, "task": "Add auth"}]}
        }))
        
        tester = TesterAgent(workspace_dir=temp_project)
        
        with patch.object(tester.tools, "execute", return_value={
            "stdout": "3 passed",
            "stderr": "",
            "returncode": 0
        }):
            tester.run_tests(test_cmd="pytest", slice_id=1)
            
            data = json.loads(workspace.read_text())
            assert "test" in data["plan"]["slices"][0]
            assert data["plan"]["slices"][0]["test"]["passed"] is True
