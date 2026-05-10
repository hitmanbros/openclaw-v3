import json
from datetime import datetime, timezone
from pathlib import Path

from openclaw.subagent.workspace import WorkspaceClient


class HITLGate:
    def __init__(self, workspace_dir, timeout_sec=3600):
        self.workspace_dir = Path(workspace_dir)
        self.timeout_sec = timeout_sec
        self._client = WorkspaceClient(self.workspace_dir / ".pi" / "workspace.json")

    def _load(self):
        return self._client.read(defaults={"plan": {"slices": []}})

    def _save(self, data):
        self._client.write(data)

    def _get_slice(self, data, slice_id):
        for s in data.get("plan", {}).get("slices", []):
            if s.get("id") == slice_id:
                return s
        return None

    def request_approval(self, slice_id, reason):
        data = self._load()
        s = self._get_slice(data, slice_id)
        if s is None:
            return
        s["hitl"] = {
            "status": "pending",
            "reason": reason,
            "requested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._save(data)

    def approve(self, slice_id):
        data = self._load()
        s = self._get_slice(data, slice_id)
        if s is None:
            return
        s.setdefault("hitl", {})["status"] = "approved"
        self._save(data)

    def reject(self, slice_id):
        data = self._load()
        s = self._get_slice(data, slice_id)
        if s is None:
            return
        s.setdefault("hitl", {})["status"] = "rejected"
        self._save(data)

    def check_approval(self, slice_id):
        data = self._load()
        s = self._get_slice(data, slice_id)
        if s is None:
            return False
        hitl = s.get("hitl", {})
        if hitl.get("status") == "approved":
            return True
        if hitl.get("status") == "pending":
            requested_at = hitl.get("requested_at")
            if requested_at:
                try:
                    ts = datetime.strptime(requested_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except ValueError:
                    return False
                if (datetime.now(timezone.utc) - ts).total_seconds() > self.timeout_sec:
                    return False
        return False
