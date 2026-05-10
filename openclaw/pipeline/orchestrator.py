"""Pipeline orchestrator — runs the full agent pipeline for a project."""

import asyncio
import json
import time
from pathlib import Path

from openclaw.subagent.runner import SubagentRunner
from openclaw.subagent.workspace import WorkspaceClient
from openclaw.pipeline.dispatcher import Dispatcher
from openclaw.pipeline.hitl import HITLGate
from openclaw.pipeline.escalation import EscalationManager


class PipelineOrchestrator:
    """Orchestrates scout → planner → slicer → workers → reviewer → tester."""

    def __init__(self, workspace_dir, matrix_client, room_id, owner_id, nexus=None):
        self.workspace_dir = Path(workspace_dir)
        self.matrix_client = matrix_client
        self.room_id = room_id
        self.owner_id = owner_id
        self.nexus = nexus
        self.runner = SubagentRunner(workspace_dir)
        self.dispatcher = Dispatcher(worker_cap=3)
        self.hitl = HITLGate(workspace_dir)
        self.escalation = EscalationManager(nexus, room_id, workspace_dir) if nexus else None

    async def _send(self, body):
        """Send a message to the project room."""
        await self.matrix_client.room_send(
            room_id=self.room_id,
            message_type="m.room.message",
            content={"body": body, "msgtype": "m.text"},
        )

    def _read_workspace(self):
        """Read current workspace state."""
        ws = WorkspaceClient(self.workspace_dir / ".pi" / "workspace.json")
        return ws.read()

    async def run_full_pipeline(self, goal=None):
        """Run the complete pipeline end-to-end."""
        try:
            # Phase 1: Scout
            await self._send("🔍 **Phase 1/6: Scout** — mapping codebase...")
            await self._run_scout()
            await self._wait_for_agent("scout")
            report_path = self.workspace_dir / ".pi" / "scout_report.md"
            report = report_path.read_text() if report_path.exists() else "No report generated."
            await self._send("🔍 Scout complete. Report saved.")

            # Phase 2: Planner
            await self._send("📝 **Phase 2/6: Planner** — writing PRD...")
            await self._run_planner(goal)
            await self._wait_for_agent("planner")
            prd_path = self.workspace_dir / ".pi" / "plans" / "project.prd.md"
            prd = prd_path.read_text() if prd_path.exists() else "No PRD generated."
            await self._send(f"📝 PRD written. Awaiting owner approval...\n\nReply with `!approve` or `!reject`.")

            # Phase 3: HITL
            approved = await self._wait_for_hitl_approval()
            if not approved:
                await self._send("❌ PRD rejected. Project paused.")
                return
            await self._send("✅ PRD approved. Continuing...")

            # Phase 4: Slicer
            await self._send("🔪 **Phase 4/6: Slicer** — breaking into slices...")
            await self._run_slicer()
            await self._wait_for_agent("slicer")
            data = self._read_workspace()
            slices = data.get("plan", {}).get("slices", [])
            await self._send(f"🔪 Slicer complete. {len(slices)} slices created.")

            if not slices:
                await self._send("⚠️ No slices generated. Stopping.")
                return

            # Phase 5: Dispatch workers
            await self._send("⚒️ **Phase 5/6: Workers** — dispatching slices...")
            await self._dispatch_workers(slices)

            # Phase 6: Review & test
            await self._send("🔍 **Phase 6/6: Review & Test** — verifying slices...")
            await self._run_reviews_and_tests(slices)

            # Final: Git commit / PR
            await self._send("📦 Pipeline complete. Committing and opening PR...")
            await self._commit_and_pr(name=config.get("config", {}).get("name", "project"))

        except Exception as exc:
            await self._send(f"❌ Pipeline error: {exc}")
            if self.escalation:
                await self.escalation.escalate(
                    reason=str(exc),
                    project_name=self.workspace_dir.name,
                    priority="critical",
                )
            raise

    async def _commit_and_pr(self, project_name):
        """Squash commits, push, and open PR."""
        try:
            from openclaw.github.commit import CommitManager
            cm = CommitManager(
                workspace_dir=str(self.workspace_dir),
                src_dir=str(self.workspace_dir / "src"),
            )
            cm.squash(phase_name="v3", summary=f"OpenClaw automated changes for {project_name}")
            cm.push(branch="main")
            # TODO: extract owner/repo from fork_url and open PR
            await self._send("✅ Committed and pushed.")
        except Exception as exc:
            await self._send(f"⚠️ Git workflow failed: {exc}")

        except Exception as exc:
            await self._send(f"❌ Pipeline error: {exc}")
            if self.escalation:
                await self.escalation.escalate(
                    reason=str(exc),
                    project_name=self.workspace_dir.name,
                    priority="critical",
                )
            raise

    async def _run_scout(self):
        """Spawn scout subprocess."""
        self.runner.spawn_agent("scout")

    async def _run_planner(self, goal):
        """Spawn planner subprocess."""
        # Write goal to workspace so planner can read it
        ws = WorkspaceClient(self.workspace_dir / ".pi" / "workspace.json")
        data = ws.read()
        if goal:
            data["goal"] = goal
            ws.write(data)
        self.runner.spawn_agent("planner")

    async def _run_slicer(self):
        """Spawn slicer subprocess."""
        self.runner.spawn_agent("slicer")

    async def _wait_for_agent(self, agent_name, timeout_sec=300, poll_sec=5):
        """Poll workspace until agent subprocess finishes."""
        # Simple heuristic: wait for file writes or workspace changes
        # For MVP, we just sleep and poll for process completion via workspace state
        start = time.time()
        while time.time() - start < timeout_sec:
            # Check if any subprocess is still running — SubagentRunner doesn't track PIDs
            # So we just wait a reasonable amount and assume LLM call completes
            await asyncio.sleep(poll_sec)
            # In a real implementation, we'd track PIDs and check `ps -p <pid>`
            break  # MVP: fire-and-forget with generous sleep
        await asyncio.sleep(5)  # Extra buffer for file writes

    async def _wait_for_approval(self):
        """Backward-compatible alias for HITL approval."""
        return await self._wait_for_hitl_approval()

    async def _wait_for_hitl_approval(self, timeout_sec=3600, poll_sec=10):
        """Poll HITL gate until owner approves or rejects."""
        # For now, we use a simplified approach: wait for !approve/!reject in room
        # This is handled by Nexus which calls hitl.approve() / hitl.reject()
        # We poll the workspace for the HITL status
        start = time.time()
        while time.time() - start < timeout_sec:
            data = self._read_workspace()
            # Check if HITL state exists in workspace
            hitl = data.get("hitl", {})
            if hitl.get("status") == "approved":
                return True
            if hitl.get("status") == "rejected":
                return False
            await asyncio.sleep(poll_sec)
        return False

    async def _dispatch_workers(self, slices):
        """Dispatch workers for ready slices."""
        # Initialize slice statuses
        ws = WorkspaceClient(self.workspace_dir / ".pi" / "workspace.json")
        data = ws.read()
        for s in slices:
            if "status" not in s:
                s["status"] = "pending"
        data["plan"]["slices"] = slices
        ws.write(data)

        max_rounds = 20
        for round_num in range(max_rounds):
            data = self._read_workspace()
            current_slices = data.get("plan", {}).get("slices", [])

            ready = self.dispatcher.compute_ready_set(current_slices)
            if not ready:
                # Check if all done
                pending = [s for s in current_slices if s.get("status") not in ("done", "failed")]
                if not pending:
                    await self._send("✅ All slices completed.")
                    break
                await asyncio.sleep(5)
                continue

            await self._send(f"⚒️ Round {round_num + 1}: dispatching {len(ready)} worker(s)...")

            for s in ready:
                s["status"] = "in_progress"
            data["plan"]["slices"] = current_slices
            ws.write(data)

            # Spawn workers in parallel
            tasks = [
                asyncio.to_thread(self.runner.spawn_agent, "worker", s["id"])
                for s in ready
            ]
            await asyncio.gather(*tasks)

            # Wait for workers to finish (MVP: fixed sleep)
            await asyncio.sleep(30)

            # Run reviewer + tester for completed workers
            for s in ready:
                self.runner.spawn_agent("reviewer", s["id"])
                self.runner.spawn_agent("tester", s["id"])

            await asyncio.sleep(20)

            # Security audit for sensitive slices
            for s in current_slices:
                if s.get("status") == "in_progress" and s.get("result"):
                    if self._should_security_audit(s):
                        await self._send(f"🔒 Slice {s['id']} touches auth/secrets — spawning security audit...")
                        self.runner.spawn_agent("security-auditor", s["id"])
            await asyncio.sleep(20)

            # Update statuses based on workspace state
            data = self._read_workspace()
            current_slices = data.get("plan", {}).get("slices", [])
            for s in current_slices:
                if s.get("status") == "in_progress":
                    # Check if result exists
                    if s.get("result"):
                        review = s.get("review", {})
                        test = s.get("test", {})
                        audit = s.get("audit", {})
                        needs_audit = self._should_security_audit(s)
                        audit_pass = not needs_audit or audit.get("pass", False)

                        if review.get("pass") and test.get("passed") and audit_pass:
                            s["status"] = "done"
                        else:
                            # Retry once
                            if s.get("attempts", 0) < 1:
                                s["attempts"] = s.get("attempts", 0) + 1
                                s["status"] = "pending"
                                await self._send(f"🔄 Slice {s['id']} failed review/test/audit, retrying...")
                            else:
                                s["status"] = "failed"
                                if self.escalation:
                                    await self.escalation.escalate(
                                        reason="Slice failed after retry",
                                        project_name=self.workspace_dir.name,
                                        slice_id=s["id"],
                                    )
            data["plan"]["slices"] = current_slices
            ws.write(data)

    async def run_phase(self, phase, goal=None):
        """Run a single phase (backward-compatible API)."""
        if goal is None:
            goal_path = self.workspace_dir / ".pi" / "workspace.json"
            if goal_path.exists():
                data = json.loads(goal_path.read_text())
                goal = data.get("goal", "Build an app")
            else:
                goal = "Build an app"

        if phase == "scout":
            report = await self._run_scout()
            await self._wait_for_agent("scout")
            report_path = self.workspace_dir / ".pi" / "scout_report.md"
            if report_path.exists():
                report = report_path.read_text()
            await self._send(report)
            return report
        elif phase == "planner":
            await self._run_planner(goal)
            await self._wait_for_agent("planner")
            prd_path = self.workspace_dir / ".pi" / "plans" / "project.prd.md"
            await self._send(f"PRD written to {prd_path}")
            approved = await self._wait_for_approval()
            return approved
        return None

    @staticmethod
    def _should_security_audit(slice_data):
        """Check if a slice touches auth, secrets, input parsing, or dependencies."""
        task = (slice_data.get("task") or "").lower()
        result = (slice_data.get("result") or "").lower()
        combined = task + " " + result
        keywords = [
            "auth", "secret", "password", "token", "login", "credential",
            "input", "parse", "validate", "sanitize", "inject",
            "dependency", "requirements", "package", "npm install", "pip install",
            "sql", "query", "eval", "exec", "innerhtml", "xss",
        ]
        return any(kw in combined for kw in keywords)

    async def _run_reviews_and_tests(self, slices):
        """Run final review and test pass for all slices."""
        # This is mostly handled during dispatch, but we do a final summary
        data = self._read_workspace()
        current_slices = data.get("plan", {}).get("slices", [])
        done = sum(1 for s in current_slices if s.get("status") == "done")
        failed = sum(1 for s in current_slices if s.get("status") == "failed")
        await self._send(f"📊 Final: {done} done, {failed} failed, {len(current_slices) - done - failed} pending.")
