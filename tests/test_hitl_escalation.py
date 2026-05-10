"""Tests for HITL gating and escalation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from openclaw.pipeline.hitl import HITLGate
from openclaw.pipeline.escalation import EscalationManager


class TestHITLGate:
    """HITL gate behavior."""

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d) / ".pi"
            workspace.mkdir()
            ws = workspace / "workspace.json"
            ws.write_text(json.dumps({
                "plan": {"slices": [{"id": 1, "task": "Auth", "status": "pending"}]}
            }))
            yield workspace.parent

    def test_hitl_creates_approval_request(self, temp_workspace):
        """HITL gate writes approval request to workspace."""
        gate = HITLGate(workspace_dir=temp_workspace)
        gate.request_approval(
            slice_id=1,
            reason="Destructive command: rm -rf",
        )
        
        data = json.loads((temp_workspace / ".pi" / "workspace.json").read_text())
        assert data["plan"]["slices"][0]["hitl"]["status"] == "pending"
        assert "rm -rf" in data["plan"]["slices"][0]["hitl"]["reason"]

    def test_hitl_approval_granted(self, temp_workspace):
        """Owner approval updates slice status."""
        gate = HITLGate(workspace_dir=temp_workspace)
        gate.request_approval(slice_id=1, reason="test")
        gate.approve(slice_id=1)
        
        data = json.loads((temp_workspace / ".pi" / "workspace.json").read_text())
        assert data["plan"]["slices"][0]["hitl"]["status"] == "approved"

    def test_hitl_rejection_blocks_slice(self, temp_workspace):
        """Owner rejection blocks slice execution."""
        gate = HITLGate(workspace_dir=temp_workspace)
        gate.request_approval(slice_id=1, reason="test")
        gate.reject(slice_id=1)
        
        data = json.loads((temp_workspace / ".pi" / "workspace.json").read_text())
        assert data["plan"]["slices"][0]["hitl"]["status"] == "rejected"

    def test_hitl_check_approved_returns_true(self, temp_workspace):
        """check_approval returns True when approved."""
        gate = HITLGate(workspace_dir=temp_workspace)
        gate.request_approval(slice_id=1, reason="test")
        gate.approve(slice_id=1)
        
        assert gate.check_approval(slice_id=1) is True

    def test_hitl_check_pending_returns_false(self, temp_workspace):
        """check_approval returns False when still pending."""
        gate = HITLGate(workspace_dir=temp_workspace)
        gate.request_approval(slice_id=1, reason="test")
        
        assert gate.check_approval(slice_id=1) is False

    def test_hitl_timeout_auto_rejects(self, temp_workspace):
        """Pending HITL auto-rejects after timeout."""
        gate = HITLGate(workspace_dir=temp_workspace, timeout_sec=0)
        gate.request_approval(slice_id=1, reason="test")
        
        # Simulate timeout by manipulating timestamp
        data = json.loads((temp_workspace / ".pi" / "workspace.json").read_text())
        data["plan"]["slices"][0]["hitl"]["requested_at"] = "2020-01-01T00:00:00Z"
        (temp_workspace / ".pi" / "workspace.json").write_text(json.dumps(data))
        
        assert gate.check_approval(slice_id=1) is False


class TestEscalationManager:
    """Escalation behavior."""

    @pytest.fixture
    def escalation(self):
        nexus = MagicMock()
        nexus.post_to_main_room = AsyncMock()
        
        return EscalationManager(
            nexus=nexus,
            project_room="!project:example.com",
        )

    @pytest.mark.asyncio
    async def test_escalate_blocked_project(self, escalation):
        """Blocked project escalates to Nexus."""
        await escalation.escalate(
            reason="Slice 3 failed after retry",
            project_name="Alpha",
            slice_id=3,
        )
        
        escalation.nexus.post_to_main_room.assert_called_once()
        call_args = escalation.nexus.post_to_main_room.call_args
        assert "Alpha" in call_args.kwargs["message"]
        assert "Slice 3" in call_args.kwargs["message"]

    @pytest.mark.asyncio
    async def test_escalate_safety_critical(self, escalation):
        """Safety-critical operations escalate with high priority."""
        await escalation.escalate(
            reason="rm -rf requested",
            project_name="Alpha",
            priority="critical",
        )
        
        call_args = escalation.nexus.post_to_main_room.call_args
        assert "[CRITICAL]" in call_args.kwargs["message"]

    @pytest.mark.asyncio
    async def test_no_duplicate_escalations(self, escalation):
        """Same issue is not escalated twice."""
        await escalation.escalate(
            reason="Slice 3 failed",
            project_name="Alpha",
            slice_id=3,
        )
        await escalation.escalate(
            reason="Slice 3 failed",
            project_name="Alpha",
            slice_id=3,
        )
        
        assert escalation.nexus.post_to_main_room.call_count == 1

    @pytest.mark.asyncio
    async def test_escalation_includes_context(self, escalation):
        """Escalation message includes project context."""
        await escalation.escalate(
            reason="Worker crashed",
            project_name="Beta",
            slice_id=1,
            context={"error": "OOM"},
        )
        
        call_args = escalation.nexus.post_to_main_room.call_args
        assert "Beta" in call_args.kwargs["message"]
        assert "OOM" in call_args.kwargs["message"]
