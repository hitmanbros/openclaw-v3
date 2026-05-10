"""Agent subprocess entry point.

Usage: python -m openclaw.agents <agent_name> <workspace_dir> [<args>]

Examples:
    python -m openclaw.agents worker /data/projects/!room:server.com 3
    python -m openclaw.agents scout /data/projects/!room:server.com
    python -m openclaw.agents planner /data/projects/!room:server.com
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from openclaw.llm.client import KimiClient
from openclaw.llm.prompts import load_prompt
from openclaw.subagent.workspace import WorkspaceClient
from openclaw.agents.loop import AgentLoop


async def main():
    if len(sys.argv) < 3:
        print("Usage: python -m openclaw.agents <agent_name> <workspace_dir> [args...]")
        sys.exit(1)

    agent_name = sys.argv[1]
    workspace_dir = Path(sys.argv[2])
    extra_args = sys.argv[3:]

    # Load config from workspace
    ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
    config = ws.read()

    # Init LLM client
    api_key = os.environ.get("KIMI_API_KEY", "")
    model = config.get("config", {}).get("model", "kimi-k2.6")
    llm = KimiClient(api_key=api_key, model=model) if api_key else None

    if not llm:
        print("No LLM configured (KIMI_API_KEY not set)")
        sys.exit(1)

    # Load prompt
    room_context = f"Project: {config.get('config', {}).get('name', 'unknown')}\nRepo: {config.get('config', {}).get('repo_url', '')}"
    system_prompt = load_prompt(agent_name, room_context)

    # Run agent-specific logic
    if agent_name == "worker":
        await run_worker(llm, system_prompt, workspace_dir, extra_args, config)
    elif agent_name == "scout":
        await run_scout(llm, system_prompt, workspace_dir, config)
    elif agent_name == "planner":
        await run_planner(llm, system_prompt, workspace_dir, config)
    elif agent_name == "slicer":
        await run_slicer(llm, system_prompt, workspace_dir, config)
    elif agent_name == "reviewer":
        await run_reviewer(llm, system_prompt, workspace_dir, extra_args, config)
    elif agent_name == "tester":
        await run_tester(llm, system_prompt, workspace_dir, extra_args, config)
    elif agent_name == "security-auditor":
        await run_security_auditor(llm, system_prompt, workspace_dir, extra_args, config)
    else:
        print(f"Unknown agent: {agent_name}")
        sys.exit(1)


async def run_worker(llm, system_prompt, workspace_dir, args, config):
    """Worker: read task, execute with tools, write result."""
    slice_id = int(args[0]) if args else 1
    slices = config.get("plan", {}).get("slices", [])
    task = next((s for s in slices if s.get("id") == slice_id), None)
    if not task:
        print(f"Worker: slice {slice_id} not found")
        return

    print(f"Worker starting: {task.get('task', 'unknown')}")

    task_message = (
        f"Your task: {task.get('task')}\n\n"
        f"Acceptance criteria: {task.get('criteria', [])}\n\n"
        f"Begin implementing. Use your tools to edit files and run tests. "
        f"When finished, summarize what you changed."
    )

    loop = AgentLoop(llm, system_prompt, "worker", workspace_dir)
    result = await loop.run(task_message)

    # Write result
    ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
    ws.update({
        "plan": {
            "slices": [
                {
                    "id": slice_id,
                    "status": "done",
                    "result": result,
                }
            ]
        }
    })
    print(f"Worker completed slice {slice_id}")


async def run_scout(llm, system_prompt, workspace_dir, config):
    """Scout: map codebase, write report."""
    print("Scout starting...")

    task_message = (
        "Map the codebase in src/. Use ls, find, grep, and read tools to explore. "
        "Report: project structure, key files, dependencies, conventions, and any notable patterns. "
        "When finished, write a concise markdown report summarizing your findings."
    )

    loop = AgentLoop(llm, system_prompt, "scout", workspace_dir)
    result = await loop.run(task_message)

    report_path = workspace_dir / ".pi" / "scout_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result)
    print(f"Scout report written: {report_path}")


async def run_planner(llm, system_prompt, workspace_dir, config):
    """Planner: read scout report, write PRD."""
    print("Planner starting...")

    report_path = workspace_dir / ".pi" / "scout_report.md"
    report = report_path.read_text() if report_path.exists() else "No scout report."
    goal = config.get("config", {}).get("goal", "Implement features")

    task_message = (
        f"Goal: {goal}\n\n"
        f"Scout report:\n{report[:4000]}\n\n"
        f"Write a detailed PRD (Product Requirements Document) to .pi/plans/project.prd.md. "
        "Use the write tool. Include: problem, goals, non-goals, user stories, acceptance criteria, open questions."
    )

    loop = AgentLoop(llm, system_prompt, "planner", workspace_dir)
    result = await loop.run(task_message)

    # Also save whatever the LLM said as a summary
    prd_path = workspace_dir / ".pi" / "plans" / "project.prd.md"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    if not prd_path.exists():
        prd_path.write_text(result)
    print(f"Planner completed. PRD at: {prd_path}")


async def run_slicer(llm, system_prompt, workspace_dir, config):
    """Slicer: read PRD, write slices."""
    print("Slicer starting...")

    prd_path = workspace_dir / ".pi" / "plans" / "project.prd.md"
    prd = prd_path.read_text() if prd_path.exists() else "No PRD."

    task_message = (
        f"PRD:\n{prd[:6000]}\n\n"
        "Break the PRD into independent, vertical slices. Each slice should be end-to-end demoable. "
        "Return a JSON object with a 'slices' array. Each slice must have: id, task, criteria (list), and blocked_by (list of slice ids). "
        "Use the write tool to save the JSON to .pi/plans/slices.json. "
        'Example: {"slices": [{"id": 1, "task": "...", "criteria": [...], "blocked_by": []}]}'
    )

    loop = AgentLoop(llm, system_prompt, "slicer", workspace_dir)
    result = await loop.run(task_message)

    # Try to parse slices from the result or from the written file
    slices_data = []
    slices_path = workspace_dir / ".pi" / "plans" / "slices.json"
    if slices_path.exists():
        try:
            slices_data = json.loads(slices_path.read_text()).get("slices", [])
        except Exception:
            pass

    if not slices_data:
        # Fallback: try to extract JSON from the LLM's text response
        try:
            import re
            match = re.search(r'\{.*"slices".*\}', result, re.DOTALL)
            if match:
                slices_data = json.loads(match.group(0)).get("slices", [])
        except Exception:
            pass

    ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
    ws.update({"plan": {"slices": slices_data}})
    print(f"Slicer wrote {len(slices_data)} slices")


async def run_reviewer(llm, system_prompt, workspace_dir, args, config):
    """Reviewer: check slice against criteria."""
    slice_id = int(args[0]) if args else 1
    print(f"Reviewer starting for slice {slice_id}...")

    slices = config.get("plan", {}).get("slices", [])
    task = next((s for s in slices if s.get("id") == slice_id), None)
    criteria = task.get("criteria", []) if task else []

    task_message = (
        f"Review slice {slice_id}.\n"
        f"Acceptance criteria: {criteria}\n\n"
        "Use read, grep, and ls tools to inspect the code. "
        "Return a JSON object with 'pass' (boolean) and 'findings' (list of strings). "
        "Be strict but constructive."
    )

    loop = AgentLoop(llm, system_prompt, "reviewer", workspace_dir)
    result = await loop.run(task_message)

    # Parse pass/fail from response
    passed = '"pass": true' in result.lower() or '"pass": true' in result.lower()

    ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
    ws.update({
        "plan": {
            "slices": [
                {
                    "id": slice_id,
                    "review": {"pass": passed, "findings": result},
                }
            ]
        }
    })
    print(f"Reviewer completed for slice {slice_id}: {'PASS' if passed else 'FAIL'}")


async def run_tester(llm, system_prompt, workspace_dir, args, config):
    """Tester: run tests, report pass/fail."""
    slice_id = int(args[0]) if args else 1
    print(f"Tester starting for slice {slice_id}...")

    task_message = (
        f"Run the test suite for slice {slice_id}. "
        "Use the bash tool to run tests (e.g., pytest, npm test, cargo test). "
        "Report: which tests passed/failed, coverage if available, and any errors. "
        "Return a JSON object with 'passed' (boolean) and 'output' (string)."
    )

    loop = AgentLoop(llm, system_prompt, "tester", workspace_dir)
    result = await loop.run(task_message)

    passed = '"passed": true' in result.lower() or '"passed": true' in result.lower()

    ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
    ws.update({
        "plan": {
            "slices": [
                {
                    "id": slice_id,
                    "test": {"passed": passed, "output": result},
                }
            ]
        }
    })
    print(f"Tester completed for slice {slice_id}: {'PASS' if passed else 'FAIL'}")


async def run_security_auditor(llm, system_prompt, workspace_dir, args, config):
    """Security-auditor: review slice for security issues."""
    slice_id = int(args[0]) if args else 1
    print(f"Security-auditor starting for slice {slice_id}...")

    slices = config.get("plan", {}).get("slices", [])
    task = next((s for s in slices if s.get("id") == slice_id), None)
    criteria = task.get("criteria", []) if task else []

    task_message = (
        f"Security audit for slice {slice_id}.\n"
        f"Acceptance criteria: {criteria}\n\n"
        "Use read, grep, and ls tools to inspect the code. "
        "Return a JSON object with 'pass' (boolean), 'blocking' (list), and 'advisory' (list). "
        "Be paranoid but precise."
    )

    loop = AgentLoop(llm, system_prompt, "security-auditor", workspace_dir)
    result = await loop.run(task_message)

    passed = '"pass": true' in result.lower() or '"pass": true' in result.lower()

    ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
    ws.update({
        "plan": {
            "slices": [
                {
                    "id": slice_id,
                    "audit": {"pass": passed, "findings": result},
                }
            ]
        }
    })
    print(f"Security-auditor completed for slice {slice_id}: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
