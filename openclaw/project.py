"""Project room lifecycle with GitHub fork/clone."""

import asyncio
import json
import re
import subprocess
from pathlib import Path

import aiohttp


class ProjectManager:
    def __init__(self, matrix_client, data_dir, owner_id, github_token, project_registry=None):
        self.matrix_client = matrix_client
        self.data_dir = Path(data_dir)
        self.owner_id = owner_id
        self.github_token = github_token
        self.project_registry = project_registry or {}

    @staticmethod
    def _parse_repo(repo_url):
        """Extract owner/repo from various GitHub URL formats."""
        # Remove protocol and git suffix
        cleaned = repo_url.strip()
        cleaned = re.sub(r'^https?://', '', cleaned)
        cleaned = re.sub(r'^git@github\.com:', '', cleaned)
        cleaned = re.sub(r'\.git$', '', cleaned)
        cleaned = cleaned.replace('github.com/', '')

        parts = cleaned.split('/')
        if len(parts) >= 2:
            return parts[0], parts[1]
        return None, None

    async def create_project(self, repo_url, name):
        """Create project room, fork repo, clone to workspace."""
        # Create Matrix room
        response = await self.matrix_client.room_create()
        room_id = response["room_id"]

        await self.matrix_client.invite(room_id, self.owner_id)

        # Setup workspace
        workspace = self.data_dir / room_id
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".pi").mkdir(exist_ok=True)
        src_dir = workspace / "src"
        src_dir.mkdir(exist_ok=True)

        # GitHub fork + clone
        fork_url = None
        if self.github_token and repo_url:
            owner, repo = self._parse_repo(repo_url)
            if owner and repo:
                try:
                    fork_url = await _fork_repo(owner, repo, self.github_token)
                    await _clone_repo(fork_url, str(src_dir))
                    await _set_upstream(str(src_dir), f"https://github.com/{owner}/{repo}.git")
                except Exception as exc:
                    # Log but don't fail — project room still useful
                    print(f"GitHub setup failed: {exc}")

        # Write workspace config
        workspace_json = workspace / ".pi" / "workspace.json"
        data = {
            "config": {
                "repo_url": repo_url,
                "fork_url": fork_url,
                "name": name,
                "status": "running",
            }
        }
        workspace_json.write_text(json.dumps(data, indent=2))

        # Set room state
        await self.matrix_client.room_send(
            room_id,
            "com.openclaw.project",
            content={"name": name, "repo_url": repo_url, "fork_url": fork_url or ""},
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


async def _fork_repo(owner, repo, token):
    """Fork a GitHub repo to the authenticated user's account."""
    url = f"https://api.github.com/repos/{owner}/{repo}/forks"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers) as resp:
            if resp.status not in (200, 202):
                text = await resp.text()
                raise RuntimeError(f"Fork failed: {resp.status} {text}")
            data = await resp.json()
            return data["clone_url"]


async def _clone_repo(clone_url, dest_dir):
    """Clone a git repo to dest_dir."""
    proc = await asyncio.create_subprocess_exec(
        "git", "clone", clone_url, dest_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Clone failed: {stderr.decode()}")


async def _set_upstream(repo_dir, upstream_url):
    """Add upstream remote pointing to original repo."""
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", repo_dir, "remote", "add", "upstream", upstream_url,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 and b"already exists" not in stderr:
        raise RuntimeError(f"Set upstream failed: {stderr.decode()}")


