"""Tests for GitHub commit workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from openclaw.github.commit import CommitManager


class TestCommitManager:
    """GitHub commit workflow behavior."""

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            src = proj / "src"
            src.mkdir()
            (src / "main.py").write_text("def main(): pass")
            
            # Setup git repo
            import subprocess
            subprocess.run(["git", "init"], cwd=src, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=src, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=src, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=src, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=src, capture_output=True)
            
            yield proj

    @pytest.fixture
    def manager(self, temp_project):
        return CommitManager(
            workspace_dir=temp_project,
            src_dir=temp_project / "src",
        )

    def test_squash_commits(self, manager, temp_project):
        """Squash combines multiple commits into one."""
        src = temp_project / "src"
        (src / "new.py").write_text("def new(): pass")
        
        import subprocess
        subprocess.run(["git", "add", "."], cwd=src, capture_output=True)
        subprocess.run(["git", "commit", "-m", "slice-1: add new"], cwd=src, capture_output=True)
        
        (src / "other.py").write_text("def other(): pass")
        subprocess.run(["git", "add", "."], cwd=src, capture_output=True)
        subprocess.run(["git", "commit", "-m", "slice-2: add other"], cwd=src, capture_output=True)
        
        manager.squash(phase_name="phase-1", summary="Add features")
        
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=src, capture_output=True, text=True,
        )
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 1  # Squashed to single commit
        assert "phase-1" in lines[0]

    def test_squash_preserves_changes(self, manager, temp_project):
        """Squashed commit preserves all file changes."""
        src = temp_project / "src"
        (src / "a.py").write_text("a")
        (src / "b.py").write_text("b")
        
        import subprocess
        subprocess.run(["git", "add", "."], cwd=src, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add files"], cwd=src, capture_output=True)
        
        manager.squash(phase_name="phase-1", summary="Add files")
        
        assert (src / "a.py").exists()
        assert (src / "b.py").exists()
        assert (src / "main.py").exists()

    def test_push_to_remote(self, manager, temp_project):
        """Push sends commits to remote."""
        with patch.object(manager, "_run_git", return_value="") as mock_git:
            manager.push(branch="main")
            mock_git.assert_called_once()
            assert "push" in mock_git.call_args[0][0]

    def test_open_pr(self, manager, temp_project):
        """PR creation calls GitHub API."""
        with patch.object(manager, "_call_github_api", return_value={"html_url": "https://github.com/owner/repo/pull/1"}) as mock_api:
            url = manager.open_pr(
                owner="owner",
                repo="repo",
                title="Add features",
                body="PR description",
                head="phase-1",
                base="main",
            )
            assert url == "https://github.com/owner/repo/pull/1"
            mock_api.assert_called_once()
