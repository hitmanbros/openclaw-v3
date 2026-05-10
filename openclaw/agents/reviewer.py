import json
from pathlib import Path

from openclaw.tools.registry import ToolRegistry


class ReviewerAgent:
    """Reviewer agent — read-only verification."""

    allowed_tools = {"read", "grep", "find", "ls"}

    def __init__(self, workspace_dir):
        self.workspace_dir = Path(workspace_dir)
        self.tools = ToolRegistry()
        self.tools.restrict_to(self.allowed_tools)

    def _call_llm(self, prompt):
        raise NotImplementedError("LLM backend not configured")

    def review(self, slice_id, criteria):
        prompt = f"Slice {slice_id}\nCriteria: {criteria}"
        response = self._call_llm(prompt)
        try:
            result = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

        findings = {
            "pass": result["pass"],
            "findings": result["findings"],
        }

        return findings
