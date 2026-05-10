"""Tests for GitHub fork/clone workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from pathlib import Path
import tempfile
import json

from openclaw.project import ProjectManager


class TestGitHubWorkflow:
    """GitHub integration behavior."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def manager(self, temp_dir):
        client = MagicMock()
        client.room_create = AsyncMock(return_value={"room_id": "!project:example.com"})
        client.invite = AsyncMock()
        client.room_send = AsyncMock()
        return ProjectManager(
            matrix_client=client,
            data_dir=temp_dir,
            owner_id="@owner:example.com",
            github_token="ghp_test_token",
        )

    @pytest.mark.asyncio
    async def test_create_project_forks_repo(self, manager, temp_dir):
        """!plan forks the GitHub repo to owner account."""
        with patch("openclaw.project._fork_repo", return_value="github.com/owner/repo-fork") as mock_fork:
            room_id = await manager.create_project(
                repo_url="github.com/original/repo",
                name="alpha",
            )
            assert room_id is not None
            mock_fork.assert_called_once_with(
                "original", "repo",
                "ghp_test_token",
            )

    @pytest.mark.asyncio
    async def test_create_project_clones_fork(self, manager, temp_dir):
        """!plan clones the fork to workspace/src/."""
        with patch("openclaw.project._fork_repo", return_value="github.com/owner/repo-fork"):
            with patch("openclaw.project._clone_repo") as mock_clone:
                await manager.create_project(
                    repo_url="github.com/original/repo",
                    name="alpha",
                )
                mock_clone.assert_called_once()
                args = mock_clone.call_args[0]
                assert "github.com/owner/repo-fork" in args

    @pytest.mark.asyncio
    async def test_create_project_sets_upstream(self, manager, temp_dir):
        """Clone has upstream pointing to original repo."""
        with patch("openclaw.project._fork_repo", return_value="github.com/owner/repo-fork"):
            with patch("openclaw.project._clone_repo"):
                with patch("openclaw.project._set_upstream") as mock_upstream:
                    await manager.create_project(
                        repo_url="github.com/original/repo",
                        name="alpha",
                    )
                    mock_upstream.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_project_without_token_skips_fork(self, manager, temp_dir):
        """Without GitHub token, project creates but no fork."""
        manager.github_token = ""
        with patch("openclaw.project._fork_repo") as mock_fork:
            room_id = await manager.create_project(
                repo_url="github.com/original/repo",
                name="alpha",
            )
            mock_fork.assert_not_called()

    def test_parse_repo_url(self, manager):
        """Various GitHub URL formats parsed correctly."""
        assert manager._parse_repo("github.com/owner/repo") == ("owner", "repo")
        assert manager._parse_repo("https://github.com/owner/repo") == ("owner", "repo")
        assert manager._parse_repo("git@github.com:owner/repo.git") == ("owner", "repo")
        assert manager._parse_repo("owner/repo") == ("owner", "repo")
