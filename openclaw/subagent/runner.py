import json
import os
import subprocess
from pathlib import Path


class SubagentRunner:
    def __init__(self, workspace_dir):
        self.workspace_dir = Path(workspace_dir)

    def _env(self):
        """Environment for subprocess — inject API key so agents can call LLM."""
        env = os.environ.copy()
        return env

    def spawn_agent(self, agent_name, *args):
        """Spawn any agent type (worker, scout, planner, etc.)."""
        cmd = [
            "python", "-m", "openclaw.agents",
            agent_name,
            str(self.workspace_dir),
        ] + [str(a) for a in args]
        proc = subprocess.Popen(cmd, env=self._env())
        return proc.pid

    def spawn_worker(self, slice_id):
        """Legacy convenience method."""
        return self.spawn_agent("worker", slice_id)

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
