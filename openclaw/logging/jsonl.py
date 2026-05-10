"""Structured JSON Lines logging."""

import json
from datetime import datetime, timezone
from pathlib import Path


class JsonlLogger:
    """Append-only JSON Lines logger."""

    def __init__(self, log_path):
        self.log_path = Path(log_path)

    def log(self, **kwargs):
        kwargs["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(kwargs) + "\n")
