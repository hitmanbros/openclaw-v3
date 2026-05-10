"""Tests for slicer and orchestrator dispatch."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from openclaw.agents.slicer import SlicerAgent
from openclaw.pipeline.dispatcher import Dispatcher


class TestSlicerAgent:
    """Slicer decomposition behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / ".pi" / "plans").mkdir(parents=True)
            prd = proj / ".pi" / "plans" / "test.prd.md"
            prd.write_text("""# PRD: Test App

## User Stories
1. As a user, I want auth so that I'm secure.
2. As a user, I want a profile page so that I see my data.
3. As a user, I want search so that I find things.
""")
            yield proj

    def test_slicer_reads_prd(self, temp_project):
        """Slicer reads the PRD file."""
        slicer = SlicerAgent(workspace_dir=temp_project)
        
        with patch.object(slicer, "_call_llm", return_value=json.dumps({
            "slices": [
                {"id": 1, "task": "Implement auth", "criteria": ["JWT works"], "blocked_by": []},
            ]
        })):
            slices = slicer.run()
            assert len(slices) == 1

    def test_slicer_outputs_valid_slices(self, temp_project):
        """Slicer outputs slices with required fields."""
        slicer = SlicerAgent(workspace_dir=temp_project)
        
        with patch.object(slicer, "_call_llm", return_value=json.dumps({
            "slices": [
                {"id": 1, "task": "Auth", "criteria": ["a"], "blocked_by": []},
                {"id": 2, "task": "Profile", "criteria": ["b"], "blocked_by": [1]},
            ]
        })):
            slices = slicer.run()
            assert all("id" in s and "task" in s and "criteria" in s and "blocked_by" in s for s in slices)

    def test_slicer_writes_to_workspace(self, temp_project):
        """Slicer writes slices to workspace.json."""
        slicer = SlicerAgent(workspace_dir=temp_project)
        
        with patch.object(slicer, "_call_llm", return_value=json.dumps({
            "slices": [{"id": 1, "task": "Auth", "criteria": ["a"], "blocked_by": []}]
        })):
            slicer.run()
            
            workspace = json.loads((temp_project / ".pi" / "workspace.json").read_text())
            assert "slices" in workspace["plan"]

    def test_slicer_parses_json_response(self, temp_project):
        """Slicer handles JSON with markdown code blocks."""
        slicer = SlicerAgent(workspace_dir=temp_project)
        
        response = '''```json
{"slices": [{"id": 1, "task": "Auth", "criteria": ["a"], "blocked_by": []}]}
```'''
        with patch.object(slicer, "_call_llm", return_value=response):
            slices = slicer.run()
            assert len(slices) == 1


class TestDispatcher:
    """Orchestrator dispatch behavior."""

    @pytest.fixture
    def dispatcher(self):
        return Dispatcher(worker_cap=3)

    def test_compute_ready_set_no_dependencies(self, dispatcher):
        """All slices with no blocked_by are ready."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "pending"},
            {"id": 2, "blocked_by": [], "status": "pending"},
        ]
        ready = dispatcher.compute_ready_set(slices)
        assert len(ready) == 2
        assert {s["id"] for s in ready} == {1, 2}

    def test_compute_ready_set_with_dependencies(self, dispatcher):
        """Slices blocked by pending slices are not ready."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "pending"},
            {"id": 2, "blocked_by": [1], "status": "pending"},
        ]
        ready = dispatcher.compute_ready_set(slices)
        assert len(ready) == 1
        assert ready[0]["id"] == 1

    def test_compute_ready_set_skips_done(self, dispatcher):
        """Done slices are not in ready set."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "done"},
            {"id": 2, "blocked_by": [], "status": "pending"},
        ]
        ready = dispatcher.compute_ready_set(slices)
        assert len(ready) == 1
        assert ready[0]["id"] == 2

    def test_compute_ready_set_respects_cap(self, dispatcher):
        """Ready set is limited by worker_cap."""
        slices = [
            {"id": i, "blocked_by": [], "status": "pending"}
            for i in range(10)
        ]
        ready = dispatcher.compute_ready_set(slices)
        assert len(ready) == 3  # worker_cap

    def test_compute_ready_set_chain(self, dispatcher):
        """Long dependency chains resolve step by step."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "done"},
            {"id": 2, "blocked_by": [1], "status": "done"},
            {"id": 3, "blocked_by": [2], "status": "pending"},
            {"id": 4, "blocked_by": [3], "status": "pending"},
        ]
        ready = dispatcher.compute_ready_set(slices)
        assert len(ready) == 1
        assert ready[0]["id"] == 3

    def test_compute_ready_set_complex_graph(self, dispatcher):
        """Diamond dependency graph resolves correctly."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "done"},
            {"id": 2, "blocked_by": [1], "status": "pending"},
            {"id": 3, "blocked_by": [1], "status": "pending"},
            {"id": 4, "blocked_by": [2, 3], "status": "pending"},
        ]
        ready = dispatcher.compute_ready_set(slices)
        assert len(ready) == 2
        assert {s["id"] for s in ready} == {2, 3}

    def test_compute_ready_set_failed_blocks_downstream(self, dispatcher):
        """Failed slices block downstream indefinitely."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "failed"},
            {"id": 2, "blocked_by": [1], "status": "pending"},
        ]
        ready = dispatcher.compute_ready_set(slices)
        assert len(ready) == 0

    @pytest.mark.asyncio
    async def test_dispatch_workers(self, dispatcher):
        """Dispatcher spawns workers for ready set."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "pending", "task": "Auth"},
        ]
        
        with patch.object(dispatcher, "_spawn_worker", return_value=AsyncMock()) as mock_spawn:
            await dispatcher.dispatch(slices, workspace_dir=Path("/tmp"))
            mock_spawn.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_no_ready_workers(self, dispatcher):
        """Dispatcher does nothing when no slices are ready."""
        slices = [
            {"id": 1, "blocked_by": [], "status": "done"},
        ]
        
        with patch.object(dispatcher, "_spawn_worker") as mock_spawn:
            await dispatcher.dispatch(slices, workspace_dir=Path("/tmp"))
            mock_spawn.assert_not_called()
