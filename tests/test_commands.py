"""Tests for Matrix command parsing."""

import pytest

from openclaw.matrix.commands import parse_command, Command


class TestParseCommand:
    """Command parsing behavior."""

    def test_ping(self):
        """!ping returns a ping command."""
        result = parse_command("!ping")
        assert result == Command(name="ping", args=[])

    def test_plan_with_url(self):
        """!plan with a GitHub URL returns plan command with repo."""
        result = parse_command("!plan github.com/owner/repo")
        assert result == Command(name="plan", args=["github.com/owner/repo"])

    def test_plan_with_short_name(self):
        """!plan with a registered short name returns plan command."""
        result = parse_command("!plan alpha")
        assert result == Command(name="plan", args=["alpha"])

    def test_status_no_args(self):
        """!status with no args returns status command with empty args."""
        result = parse_command("!status")
        assert result == Command(name="status", args=[])

    def test_status_with_project(self):
        """!status with project name returns status command."""
        result = parse_command("!status Alpha")
        assert result == Command(name="status", args=["Alpha"])

    def test_approve_with_slice(self):
        """!approve with slice id returns approve command."""
        result = parse_command("!approve 3")
        assert result == Command(name="approve", args=["3"])

    def test_config_get(self):
        """!config get worker_cap returns config get command."""
        result = parse_command("!config get worker_cap")
        assert result == Command(name="config", args=["get", "worker_cap"])

    def test_config_set(self):
        """!config set worker_cap 5 returns config set command."""
        result = parse_command("!config set worker_cap 5")
        assert result == Command(name="config", args=["set", "worker_cap", "5"])

    def test_no_prefix_returns_none(self):
        """Messages without ! prefix return None (natural language)."""
        result = parse_command("hello bot")
        assert result is None

    def test_unknown_command(self):
        """Unknown commands return the command name anyway (validated later)."""
        result = parse_command("!unknown arg1 arg2")
        assert result == Command(name="unknown", args=["arg1", "arg2"])

    def test_extra_whitespace(self):
        """Extra whitespace between args is normalized."""
        result = parse_command("!plan   github.com/owner/repo")
        assert result == Command(name="plan", args=["github.com/owner/repo"])

    def test_empty_args(self):
        """Command with no args after name has empty args list."""
        result = parse_command("!help")
        assert result == Command(name="help", args=[])
