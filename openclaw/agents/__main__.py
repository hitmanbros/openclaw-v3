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

    # Build messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Your task: {task.get('task')}\n\nAcceptance criteria: {task.get('criteria', [])}\n\nBegin implementing. Use your tools to edit files and run tests."}
    ]

    # Call LLM (single-shot for MVP; tool loop comes later)
    if llm:
        response = await llm.chat(messages)
        print(f"Worker result: {response[:200]}...")
    else:
        response = "No LLM configured"

    # Write result
    ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
    ws.update({"plan": {"slices": [{"id": slice_id, "status": "done", "result": response}]}})


async def run_scout(llm, system_prompt, workspace_dir, config):
    """Scout: map codebase, write report."""
    print("Scout starting...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Map the codebase in src/. Report files, structure, and key patterns."}
    ]
    if llm:
        response = await llm.chat(messages)
        report_path = workspace_dir / ".pi" / "scout_report.md"
        report_path.write_text(response)
        print(f"Scout report written: {report_path}")
    else:
        print("No LLM configured")


async def run_planner(llm, system_prompt, workspace_dir, config):
    """Planner: read scout report, write PRD."""
    print("Planner starting...")
    report_path = workspace_dir / ".pi" / "scout_report.md"
    report = report_path.read_text() if report_path.exists() else "No scout report."
    goal = config.get("config", {}).get("goal", "Implement features")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Goal: {goal}\n\nScout report:\n{report[:2000]}\n\nWrite a PRD to .pi/plans/project.prd.md"}
    ]
    if llm:
        response = await llm.chat(messages)
        prd_path = workspace_dir / ".pi" / "plans" / "project.prd.md"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(response)
        print(f"PRD written: {prd_path}")
    else:
        print("No LLM configured")


async def run_slicer(llm, system_prompt, workspace_dir, config):
    """Slicer: read PRD, write slices."""
    print("Slicer starting...")
    prd_path = workspace_dir / ".pi" / "plans" / "project.prd.md"
    prd = prd_path.read_text() if prd_path.exists() else "No PRD."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"PRD:\n{prd[:3000]}\n\nBreak into slices. Return JSON with 'slices' array."}
    ]
    if llm:
        response = await llm.chat(messages)
        # Parse JSON from response
        try:
            import re
            match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            json_str = match.group(1) if match else response
            data = json.loads(json_str)
            ws = WorkspaceClient(workspace_dir / ".pi" / "workspace.json")
            ws.update({"plan": {"slices": data.get("slices", [])}})
            print(f"Slicer wrote {len(data.get('slices', []))} slices")
        except Exception as exc:
            print(f"Slicer parse error: {exc}")
    else:
        print("No LLM configured")


async def run_reviewer(llm, system_prompt, workspace_dir, args, config):
    """Reviewer: check slice against criteria."""
    slice_id = int(args[0]) if args else 1
    print(f"Reviewer starting for slice {slice_id}...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Review slice {slice_id}. Check acceptance criteria and code quality. Return JSON with 'pass' and 'findings'."}
    ]
    if llm:
        response = await llm.chat(messages)
        print(f"Reviewer: {response[:200]}")
    else:
        print("No LLM configured")


async def run_tester(llm, system_prompt, workspace_dir, args, config):
    """Tester: run tests, report pass/fail."""
    slice_id = int(args[0]) if args else 1
    print(f"Tester starting for slice {slice_id}...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Run tests for slice {slice_id}. Use bash tool. Report results."}
    ]
    if llm:
        response = await llm.chat(messages)
        print(f"Tester: {response[:200]}")
    else:
        print("No LLM configured")


if __name__ == "__main__":
    asyncio.run(main())
