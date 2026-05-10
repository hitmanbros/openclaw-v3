"""Tests for tool registry and agent scoping."""

import pytest
from unittest.mock import MagicMock

from openclaw.tools.registry import ToolRegistry


class TestToolRegistry:
    """Tool registry behavior."""

    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()
        # Register some tools
        reg.register("read", MagicMock(), agents={"worker", "scout", "reviewer"})
        reg.register("edit", MagicMock(), agents={"worker"})
        reg.register("bash", MagicMock(), agents={"worker", "tester"})
        reg.register("grep", MagicMock(), agents={"scout", "reviewer"})
        reg.register("write_workspace", MagicMock(), agents={"orchestrator", "worker"})
        return reg

    def test_get_tools_for_worker(self, registry):
        """Worker gets read, edit, bash, write_workspace."""
        tools = registry.get_tools_for_agent("worker")
        names = {t["name"] for t in tools}
        assert names == {"read", "edit", "bash", "write_workspace"}

    def test_get_tools_for_scout(self, registry):
        """Scout gets read, grep."""
        tools = registry.get_tools_for_agent("scout")
        names = {t["name"] for t in tools}
        assert names == {"read", "grep"}

    def test_get_tools_for_reviewer(self, registry):
        """Reviewer gets read, grep."""
        tools = registry.get_tools_for_agent("reviewer")
        names = {t["name"] for t in tools}
        assert names == {"read", "grep"}

    def test_get_tools_for_orchestrator(self, registry):
        """Orchestrator gets write_workspace."""
        tools = registry.get_tools_for_agent("orchestrator")
        names = {t["name"] for t in tools}
        assert names == {"write_workspace"}

    def test_unknown_agent_gets_no_tools(self, registry):
        """Unknown agent gets empty tool list."""
        tools = registry.get_tools_for_agent("unknown")
        assert tools == []

    def test_tool_schema_includes_description(self, registry):
        """Tool schemas include description and parameters."""
        tools = registry.get_tools_for_agent("worker")
        read_tool = next(t for t in tools if t["name"] == "read")
        assert "description" in read_tool
        assert "parameters" in read_tool

    def test_execute_routes_to_correct_tool(self, registry):
        """execute calls the registered function for the tool."""
        mock_fn = MagicMock(return_value="result")
        registry.register("test_tool", mock_fn, agents={"worker"})
        
        result = registry.execute("test_tool", {"arg": "value"})
        mock_fn.assert_called_once_with(arg="value")
        assert result == "result"

    def test_execute_unknown_tool_raises(self, registry):
        """Executing unknown tool raises KeyError."""
        with pytest.raises(KeyError):
            registry.execute("unknown_tool", {})
