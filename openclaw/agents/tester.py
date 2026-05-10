from pathlib import Path

from openclaw.tools.registry import ToolRegistry
from openclaw.subagent.workspace import WorkspaceClient


class TesterAgent:
    """Tester agent — runs test commands and reports results."""

    def __init__(self, workspace_dir):
        self.workspace_dir = Path(workspace_dir)
        self.tools = ToolRegistry()

    def run_tests(self, test_cmd, slice_id=None):
        output = self.tools.execute("bash", {"command": test_cmd})
        passed = output.get("returncode", 0) == 0
        result = {"passed": passed, "output": output}

        if slice_id is not None:
            workspace = WorkspaceClient(self.workspace_dir / ".pi" / "workspace.json")
            data = workspace.read()
            if "plan" in data and "slices" in data["plan"]:
                data["plan"]["slices"][slice_id - 1]["test"] = result
                workspace.write(data)

        return result
