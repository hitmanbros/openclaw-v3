import json
from pathlib import Path


class ProjectManager:
    def __init__(self, matrix_client, data_dir, owner_id, github_token, project_registry=None):
        self.matrix_client = matrix_client
        self.data_dir = Path(data_dir)
        self.owner_id = owner_id
        self.github_token = github_token
        self.project_registry = project_registry or {}

    async def create_project(self, repo_url, name):
        response = await self.matrix_client.room_create()
        room_id = response["room_id"]

        await self.matrix_client.invite(room_id, self.owner_id)

        workspace = self.data_dir / room_id
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".pi").mkdir(exist_ok=True)
        (workspace / "src").mkdir(exist_ok=True)

        workspace_json = workspace / ".pi" / "workspace.json"
        data = {
            "config": {
                "repo_url": repo_url,
                "name": name,
                "status": "running",
            }
        }
        workspace_json.write_text(json.dumps(data, indent=2))

        await self.matrix_client.room_send(
            room_id,
            "com.openclaw.project",
            content={"name": name, "repo_url": repo_url},
        )

        return room_id

    async def close_project(self, room_id):
        workspace_json = self.data_dir / room_id / ".pi" / "workspace.json"
        data = json.loads(workspace_json.read_text())
        data["config"]["status"] = "archived"
        workspace_json.write_text(json.dumps(data, indent=2))

    def resolve_repo(self, name):
        entry = self.project_registry.get(name)
        if entry:
            return entry.get("repo")
        return None
