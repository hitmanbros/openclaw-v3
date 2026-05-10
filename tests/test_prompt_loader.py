"""Tests for agent prompt loader."""

import pytest
from pathlib import Path

from openclaw.llm.prompts import load_prompt, build_messages


class TestPromptLoader:
    """Prompt loading behavior."""

    def test_load_base_plus_agent(self):
        """Prompt includes BASE.md + agent-specific content."""
        prompt = load_prompt("worker")
        assert "OpenClaw v3" in prompt
        assert "Worker" in prompt

    def test_load_unknown_agent_uses_default(self):
        """Unknown agent gets a default prompt."""
        prompt = load_prompt("unknown-agent")
        assert "unknown-agent" in prompt

    def test_room_context_appended(self):
        """Room context is appended to prompt."""
        prompt = load_prompt("worker", room_context="Project: Alpha")
        assert "Project: Alpha" in prompt

    def test_build_messages_structure(self):
        """build_messages returns OpenAI-style message list."""
        messages = build_messages("worker", "Do task", room_context="Project: Alpha")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "Worker" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Do task"

    def test_frontmatter_stripped(self):
        """YAML frontmatter is removed from prompt."""
        prompt = load_prompt("planner")
        assert "---" not in prompt[:50]  # frontmatter removed
        assert "Planner" in prompt
