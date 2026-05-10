from pathlib import Path

from openclaw.agents.scout import ScoutAgent
from openclaw.agents.planner import PlannerAgent


class PipelineOrchestrator:
    def __init__(self, workspace_dir, matrix_client, room_id):
        self.workspace_dir = Path(workspace_dir)
        self.matrix_client = matrix_client
        self.room_id = room_id

    def _run_scout(self):
        scout = ScoutAgent(self.workspace_dir)
        return scout.run()

    def _run_planner(self, goal):
        planner = PlannerAgent(self.workspace_dir)
        return planner.run(goal=goal)

    async def _wait_for_approval(self):
        return True

    async def run_phase(self, phase, goal=None):
        if goal is None:
            goal_path = self.workspace_dir / ".pi" / "workspace.json"
            if goal_path.exists():
                import json
                data = json.loads(goal_path.read_text())
                goal = data.get("goal", "Build an app")
            else:
                goal = "Build an app"

        if phase == "scout":
            report = self._run_scout()
            await self.matrix_client.room_send(
                room_id=self.room_id,
                message_type="m.room.message",
                content={"body": report, "msgtype": "m.text"},
            )
            return report
        elif phase == "planner":
            prd_path = self._run_planner(goal=goal)
            await self.matrix_client.room_send(
                room_id=self.room_id,
                message_type="m.room.message",
                content={"body": f"PRD written to {prd_path}", "msgtype": "m.text"},
            )
            approved = await self._wait_for_approval()
            return approved
        return None
