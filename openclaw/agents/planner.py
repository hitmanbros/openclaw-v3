from pathlib import Path
import re


class PlannerAgent:
    def __init__(self, workspace_dir):
        self.workspace_dir = Path(workspace_dir)

    def _call_llm(self, prompt):
        raise NotImplementedError("LLM backend not configured — override _call_llm in subclass or patch in tests")

    def run(self, goal):
        scout_report_path = self.workspace_dir / ".pi" / "scout_report.md"
        scout_report = scout_report_path.read_text() if scout_report_path.exists() else ""

        prompt = f"Goal: {goal}\n\nScout Report:\n{scout_report}"
        prd_content = self._call_llm(prompt)

        slug = re.sub(r"[^\w\s-]", "", goal).strip().lower()
        slug = re.sub(r"[-\s]+", "-", slug)
        prd_path = self.workspace_dir / ".pi" / "plans" / f"{slug}.prd.md"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(prd_content)

        return prd_path
