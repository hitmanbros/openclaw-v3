import json
import subprocess
from pathlib import Path


class SubagentRunner:
    def __init__(self, workspace_dir):
        self.workspace_dir = Path(workspace_dir)

    def spawn_worker(self, slice_id):
        cmd = [
            "python", "-m", "openclaw.agents.worker",
            str(self.workspace_dir),
            str(slice_id),
        ]
        proc = subprocess.Popen(cmd)
        return proc.pid

    def read_worker_task(self, slice_id):
        ws = self.workspace_dir / ".pi" / "workspace.json"
        if not ws.exists():
            return {"task": None}
        data = json.loads(ws.read_text())
        slices = data.get("plan", {}).get("slices", [])
        for s in slices:
            if s.get("id") == slice_id:
                return s
        return {"task": None}

    def write_worker_result(self, slice_id, result):
        ws = self.workspace_dir / ".pi" / "workspace.json"
        if ws.exists():
            data = json.loads(ws.read_text())
        else:
            data = {"plan": {"slices": []}}
        for s in data["plan"]["slices"]:
            if s.get("id") == slice_id:
                s["status"] = "done"
                s["result"] = result
                break
        else:
            data["plan"]["slices"].append({
                "id": slice_id,
                "status": "done",
                "result": result,
            })
        ws.write_text(json.dumps(data))
