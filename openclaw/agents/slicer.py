import json
import re
from pathlib import Path


class SlicerAgent:
    def __init__(self, workspace_dir):
        self.workspace_dir = Path(workspace_dir)

    def _call_llm(self, prompt):
        raise NotImplementedError("LLM backend not configured — override _call_llm in subclass or patch in tests")

    def run(self):
        plans_dir = self.workspace_dir / ".pi" / "plans"
        prd_files = list(plans_dir.glob("*.prd.md"))
        if not prd_files:
            raise FileNotFoundError(f"No PRD found in {plans_dir}")
        prd_path = prd_files[0]
        prd_content = prd_path.read_text()

        prompt = f"Decompose the following PRD into implementation slices.\n\n{prd_content}"
        response = self._call_llm(prompt)

        m = re.search(r'```(?:json)?\s*(.*?)\s*```', response, re.DOTALL)
        response = m.group(1) if m else response
        response = response.strip()

        data = json.loads(response)
        if not isinstance(data, dict) or "slices" not in data:
            raise ValueError("LLM response missing 'slices' key")
        if not isinstance(data["slices"], list):
            raise ValueError("LLM response 'slices' must be a list")
        slices = data["slices"]

        workspace_path = self.workspace_dir / ".pi" / "workspace.json"
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        if workspace_path.exists():
            workspace = json.loads(workspace_path.read_text())
        else:
            workspace = {}
        if "plan" not in workspace:
            workspace["plan"] = {}
        workspace["plan"]["slices"] = slices
        workspace_path.write_text(json.dumps(workspace, indent=2))

        return slices
