"""GitHub commit workflow manager."""

import json
import os
import subprocess
from pathlib import Path
from urllib import request


class CommitManager:
    def __init__(self, workspace_dir, src_dir):
        self.workspace_dir = Path(workspace_dir)
        self.src_dir = Path(src_dir)
        if not self.src_dir.resolve().is_relative_to(self.workspace_dir.resolve()):
            raise ValueError(f"src_dir {src_dir} must be inside workspace_dir {workspace_dir}")
        self._base_commit = self._run_git(["rev-parse", "HEAD"]).strip()

    def squash(self, phase_name, summary):
        self._run_git(["reset", "--soft", self._base_commit])
        self._run_git(["commit", "--amend", "-m", f"phase-{phase_name}: {summary}"])

    def push(self, branch):
        self._run_git(["push", "origin", branch])

    def open_pr(self, owner, repo, title, body, head, base):
        endpoint = f"repos/{owner}/{repo}/pulls"
        data = {"title": title, "body": body, "head": head, "base": base}
        result = self._call_github_api(endpoint, data)
        return result["html_url"]

    def _run_git(self, args):
        result = subprocess.run(
            ["git"] + args,
            cwd=self.src_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout

    def _call_github_api(self, endpoint, data):
        token = os.environ.get("GITHUB_TOKEN")
        url = f"https://api.github.com/{endpoint}"
        req = request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={
                "Authorization": f"token {token}" if token else "",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github.v3+json",
            },
            method="POST",
        )
        with request.urlopen(req) as resp:
            return json.loads(resp.read())
