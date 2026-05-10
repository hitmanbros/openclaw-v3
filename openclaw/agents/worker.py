from pathlib import Path

from openclaw.tools.registry import ToolRegistry
from openclaw.subagent.workspace import WorkspaceClient


class WorkerAgent:
    """Worker agent — implements a slice end-to-end."""

    def __init__(self, workspace_dir, slice_id):
        self.workspace_dir = Path(workspace_dir)
        self.slice_id = slice_id
        self.tools = ToolRegistry()

    def read_task(self):
        workspace = WorkspaceClient(self.workspace_dir / ".pi" / "workspace.json")
        data = workspace.read()
        return data["plan"]["slices"][self.slice_id - 1]["task"]

    def _validate_path(self, value):
        if isinstance(value, str):
            path = Path(value)
            if path.is_absolute():
                resolved = path.resolve()
            else:
                resolved = (self.workspace_dir / path).resolve()
            try:
                resolved.relative_to(self.workspace_dir.resolve())
            except ValueError:
                raise ValueError(f"Path escapes workspace: {value}")
        elif isinstance(value, list):
            for item in value:
                self._validate_path(item)
        elif isinstance(value, dict):
            for v in value.values():
                self._validate_path(v)

    def run_tool(self, name, kwargs):
        self._validate_path(kwargs)
        return self.tools.execute(name, kwargs)

    def complete(self, result):
        workspace = WorkspaceClient(self.workspace_dir / ".pi" / "workspace.json")
        data = workspace.read()
        slice_data = data["plan"]["slices"][self.slice_id - 1]
        slice_data["status"] = "done"
        slice_data["result"] = result
        workspace.write(data)
