"""Tests for Pulse monitor."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import tempfile

from openclaw.pulse import PulseMonitor


class TestPulseMonitor:
    """Pulse monitor behavior."""

    @pytest.fixture
    def temp_log(self):
        with tempfile.TemporaryDirectory() as d:
            log_file = Path(d) / "bot.log"
            yield log_file

    @pytest.fixture
    def pulse(self, temp_log):
        ops = MagicMock()
        ops.post_alert = AsyncMock()
        
        return PulseMonitor(
            ops_room=ops,
            log_file=temp_log,
            interval_sec=60,
        )

    @pytest.mark.asyncio
    async def test_detects_errors_in_logs(self, pulse, temp_log):
        """Pulse detects error lines in log file."""
        temp_log.write_text("INFO: normal operation\nERROR: something broke\n")
        
        errors = await pulse.scan_logs()
        assert len(errors) == 1
        assert "something broke" in errors[0]

    @pytest.mark.asyncio
    async def test_ignores_info_lines(self, pulse, temp_log):
        """Pulse ignores non-error lines."""
        temp_log.write_text("INFO: normal\nDEBUG: details\n")
        
        errors = await pulse.scan_logs()
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_dedup_by_fingerprint(self, pulse, temp_log):
        """Same error fingerprint is not reported twice."""
        temp_log.write_text("ERROR: database timeout\nERROR: database timeout\n")
        
        errors1 = await pulse.scan_logs()
        assert len(errors1) == 1
        
        # Second scan should find no new errors
        errors2 = await pulse.scan_logs()
        assert len(errors2) == 0

    @pytest.mark.asyncio
    async def test_posts_alert_to_ops_room(self, pulse, temp_log):
        """Detected errors are posted to ops room."""
        temp_log.write_text("ERROR: worker crashed\n")
        
        await pulse.tick()
        
        pulse.ops_room.post_alert.assert_called_once()
        call_args = pulse.ops_room.post_alert.call_args
        assert "worker crashed" in call_args.kwargs["message"]

    @pytest.mark.asyncio
    async def test_no_alert_when_no_errors(self, pulse, temp_log):
        """No alert posted when logs are clean."""
        temp_log.write_text("INFO: all good\n")
        
        await pulse.tick()
        
        pulse.ops_room.post_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_filters_pulse_lines(self, pulse, temp_log):
        """Pulse ignores its own log lines to avoid loops."""
        temp_log.write_text("INFO: normal\n[pulse] scanning logs\nERROR: real error\n")
        
        errors = await pulse.scan_logs()
        assert len(errors) == 1
        assert "real error" in errors[0]
