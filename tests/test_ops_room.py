"""Tests for ops room and structured logging."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import tempfile
import json

from openclaw.logging.jsonl import JsonlLogger
from openclaw.ops import OpsRoom


class TestJsonlLogger:
    """Structured logging behavior."""

    @pytest.fixture
    def temp_log_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_log_single_event(self, temp_log_dir):
        """A single event is written as one JSON line."""
        logger = JsonlLogger(temp_log_dir / "events.jsonl")
        logger.log(
            event="slice_complete",
            project="alpha",
            slice_id=3,
            agent="worker",
            status="done",
        )
        
        lines = (temp_log_dir / "events.jsonl").read_text().strip().split("\n")
        assert len(lines) == 1
        
        data = json.loads(lines[0])
        assert data["event"] == "slice_complete"
        assert data["project"] == "alpha"
        assert data["slice_id"] == 3

    def test_log_multiple_events(self, temp_log_dir):
        """Multiple events are written as separate JSON lines."""
        logger = JsonlLogger(temp_log_dir / "events.jsonl")
        logger.log(event="slice_start", project="alpha", slice_id=1)
        logger.log(event="slice_complete", project="alpha", slice_id=1)
        
        lines = (temp_log_dir / "events.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        
        data1 = json.loads(lines[0])
        data2 = json.loads(lines[1])
        assert data1["event"] == "slice_start"
        assert data2["event"] == "slice_complete"

    def test_log_includes_timestamp(self, temp_log_dir):
        """Each event includes an ISO timestamp."""
        logger = JsonlLogger(temp_log_dir / "events.jsonl")
        logger.log(event="test")
        
        lines = (temp_log_dir / "events.jsonl").read_text().strip().split("\n")
        data = json.loads(lines[0])
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO8601 format

    def test_log_appends_to_existing_file(self, temp_log_dir):
        """New events are appended to existing log file."""
        log_file = temp_log_dir / "events.jsonl"
        log_file.write_text('{"event":"old"}\n')
        
        logger = JsonlLogger(log_file)
        logger.log(event="new")
        
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "old"
        assert json.loads(lines[1])["event"] == "new"


class TestOpsRoom:
    """Ops room behavior."""

    @pytest.fixture
    def ops(self):
        client = MagicMock()
        client.room_send = AsyncMock()
        
        return OpsRoom(
            matrix_client=client,
            ops_room="!ops:example.com",
        )

    @pytest.mark.asyncio
    async def test_post_critical_error(self, ops):
        """Critical errors are posted to ops room."""
        await ops.post_error(
            message="Worker crashed",
            project="alpha",
            slice_id=3,
        )
        
        ops.matrix_client.room_send.assert_called_once()
        call_args = ops.matrix_client.room_send.call_args
        assert call_args.kwargs["room_id"] == "!ops:example.com"
        assert "Worker crashed" in call_args.kwargs["content"]["body"]

    @pytest.mark.asyncio
    async def test_post_status(self, ops):
        """Status updates are posted to ops room."""
        await ops.post_status(
            projects=[
                {"name": "alpha", "status": "running", "slices_done": 2, "slices_total": 5},
            ],
        )
        
        ops.matrix_client.room_send.assert_called_once()
        call_args = ops.matrix_client.room_send.call_args
        assert "alpha" in call_args.kwargs["content"]["body"]

    @pytest.mark.asyncio
    async def test_post_system_alert(self, ops):
        """System alerts include level prefix."""
        await ops.post_alert(
            level="WARNING",
            message="High token usage",
        )
        
        call_args = ops.matrix_client.room_send.call_args
        assert "[WARNING]" in call_args.kwargs["content"]["body"]
