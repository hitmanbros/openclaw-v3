"""Tests for scout → planner pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from openclaw.agents.scout import ScoutAgent
from openclaw.agents.planner import PlannerAgent
from openclaw.pipeline.orchestrator import PipelineOrchestrator


class TestScoutAgent:
    """Scout reconnaissance behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            (src / "main.py").write_text("def main(): pass")
            (src / "utils.py").write_text("def helper(): pass")
            yield Path(d)

    def test_scout_maps_files(self, temp_project):
        """Scout discovers and reports project files."""
        scout = ScoutAgent(workspace_dir=temp_project)
        report = scout.run()
        
        assert "main.py" in report
        assert "utils.py" in report

    def test_scout_counts_lines(self, temp_project):
        """Scout includes line counts in report."""
        scout = ScoutAgent(workspace_dir=temp_project)
        report = scout.run()
        
        assert "lines" in report.lower() or "loc" in report.lower()

    def test_scout_writes_report_to_workspace(self, temp_project):
        """Scout writes report to workspace."""
        scout = ScoutAgent(workspace_dir=temp_project)
        scout.run()
        
        report_path = temp_project / ".pi" / "scout_report.md"
        assert report_path.exists()


class TestPlannerAgent:
    """Planner PRD creation behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / ".pi").mkdir()
            (proj / ".pi" / "scout_report.md").write_text("Project has 2 files.")
            yield proj

    def test_planner_reads_scout_report(self, temp_project):
        """Planner reads scout report before planning."""
        planner = PlannerAgent(workspace_dir=temp_project)
        
        with patch.object(planner, "_call_llm", return_value="# PRD\n\n## Goals\nBuild app.") as mock_llm:
            planner.run(goal="Build an app")
            
            prompt = mock_llm.call_args[0][0]
            assert "Project has 2 files" in prompt

    def test_planner_writes_prd(self, temp_project):
        """Planner writes PRD to .pi/plans/."""
        planner = PlannerAgent(workspace_dir=temp_project)
        
        with patch.object(planner, "_call_llm", return_value="# PRD\n\n## Goals\nBuild app."):
            planner.run(goal="Build an app")
            
            plans_dir = temp_project / ".pi" / "plans"
            assert any(plans_dir.glob("*.prd.md"))

    def test_planner_parses_prd_sections(self, temp_project):
        """Planner PRD includes required sections."""
        planner = PlannerAgent(workspace_dir=temp_project)
        
        prd_content = """# PRD: Test App

## Problem Statement
Need an app.

## Solution
Build it.

## User Stories
1. As a user, I want to log in.

## Implementation Decisions
- Use FastAPI

## Testing Decisions
- Unit tests

## Out of Scope
- Mobile app
"""
        with patch.object(planner, "_call_llm", return_value=prd_content):
            prd_path = planner.run(goal="Build an app")
            
            written = prd_path.read_text()
            assert "## Problem Statement" in written
            assert "## Solution" in written
            assert "## User Stories" in written


class TestPipelineOrchestrator:
    """Pipeline orchestration behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / ".pi").mkdir()
            (proj / "src").mkdir()
            yield proj

    @pytest.fixture
    def orch(self, temp_project):
        matrix_client = MagicMock()
        matrix_client.room_send = AsyncMock()
        
        return PipelineOrchestrator(
            workspace_dir=temp_project,
            matrix_client=matrix_client,
            room_id="!project:example.com",
            owner_id="@owner:example.com",
        )

    @pytest.mark.asyncio
    async def test_run_scout_phase(self, orch, temp_project):
        """Orchestrator runs scout and posts report summary."""
        with patch.object(orch, "_run_scout", return_value="Found 5 files"):
            with patch.object(orch, "_wait_for_agent"):
                await orch.run_phase("scout")
                
                orch.matrix_client.room_send.assert_called()
                call_body = orch.matrix_client.room_send.call_args.kwargs["content"]["body"]
                assert "Found 5 files" in call_body

    @pytest.mark.asyncio
    async def test_run_planner_phase(self, orch, temp_project):
        """Orchestrator runs planner and posts PRD summary."""
        prd_path = temp_project / ".pi" / "plans" / "test.prd.md"
        prd_path.parent.mkdir(parents=True)
        prd_path.write_text("# PRD\n\n## Goals\nBuild app.")
        
        with patch.object(orch, "_run_planner", return_value=prd_path):
            with patch.object(orch, "_wait_for_agent"):
                with patch.object(orch, "_wait_for_approval", return_value=True):
                    await orch.run_phase("planner")
                    
                    orch.matrix_client.room_send.assert_called()

    @pytest.mark.asyncio
    async def test_planner_hitl_gate(self, orch, temp_project):
        """Planner phase waits for owner approval."""
        prd_path = temp_project / ".pi" / "plans" / "test.prd.md"
        prd_path.parent.mkdir(parents=True)
        prd_path.write_text("# PRD")
        
        with patch.object(orch, "_run_planner", return_value=prd_path):
            with patch.object(orch, "_wait_for_agent"):
                with patch.object(orch, "_wait_for_approval", return_value=True):
                    result = await orch.run_phase("planner")
                    assert result is True

    @pytest.mark.asyncio
    async def test_hitl_rejection_stops_pipeline(self, orch, temp_project):
        """If owner rejects PRD, pipeline stops."""
        prd_path = temp_project / ".pi" / "plans" / "test.prd.md"
        prd_path.parent.mkdir(parents=True)
        prd_path.write_text("# PRD")
        
        with patch.object(orch, "_run_planner", return_value=prd_path):
            with patch.object(orch, "_wait_for_agent"):
                with patch.object(orch, "_wait_for_approval", return_value=False):
                    result = await orch.run_phase("planner")
                    assert result is False
