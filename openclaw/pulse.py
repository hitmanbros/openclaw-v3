"""Pulse monitor for OpenClaw."""

import hashlib
from pathlib import Path


class PulseMonitor:
    """Monitors logs and alerts on errors."""

    def __init__(self, ops_room, log_file, interval_sec=300):
        self.ops_room = ops_room
        self.log_file = Path(log_file)
        self.interval_sec = interval_sec
        self._seen = set()

    async def scan_logs(self):
        """Read log file and return new error lines."""
        if not self.log_file.exists():
            return []

        errors = []
        text = self.log_file.read_text()

        for line in text.splitlines():
            line_lower = line.lower()
            if "error" not in line_lower and "critical" not in line_lower:
                continue
            if "[pulse]" in line_lower or "pulse" in line_lower:
                continue

            fp = hashlib.sha1(line.encode()).hexdigest()[:12]
            if fp in self._seen:
                continue

            self._seen.add(fp)
            errors.append(line)

        return errors

    async def tick(self):
        """Scan logs and post alerts for new errors."""
        errors = await self.scan_logs()
        if errors:
            message = "\n".join(errors)
            await self.ops_room.post_alert(level="ERROR", message=message)
