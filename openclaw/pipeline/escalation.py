import hashlib
import json
from pathlib import Path


class EscalationManager:
    def __init__(self, nexus, project_room, workspace_dir=None):
        self.nexus = nexus
        self.project_room = project_room
        self._seen = set()
        self._workspace_dir = Path(workspace_dir) if workspace_dir else None
        if self._workspace_dir:
            self._load_seen()

    def _escalation_path(self):
        return self._workspace_dir / ".pi" / "escalations.json"

    def _load_seen(self):
        path = self._escalation_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._seen = set(data.get("seen", []))
            except (json.JSONDecodeError, OSError):
                self._seen = set()

    def _save_seen(self):
        if not self._workspace_dir:
            return
        path = self._escalation_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"seen": sorted(self._seen)}))

    async def escalate(self, reason, project_name, slice_id=None, priority="normal", context=None):
        fingerprint = hashlib.sha1(
            f"{reason}:{project_name}:{slice_id}".encode()
        ).hexdigest()
        if fingerprint in self._seen:
            return
        self._seen.add(fingerprint)
        self._save_seen()

        parts = []
        if priority == "critical":
            parts.append("[CRITICAL]")
        if slice_id is not None:
            parts.append(f"Slice {slice_id}")
        parts.append(f"Project: {project_name}")
        parts.append(f"Reason: {reason}")
        if context:
            for k, v in context.items():
                parts.append(f"{k}: {v}")

        message = " | ".join(parts)
        await self.nexus.post_to_main_room(message=message)
