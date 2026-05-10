import inspect
from typing import Any, Callable, Set


class ToolRegistry:
    """Registry for tools scoped to agent names."""

    def __init__(self):
        self._tools: dict[str, dict[str, Any]] = {}

    def register(self, name: str, fn: Callable, agents: Set[str]):
        """Register a tool with metadata and allowed agent set."""
        description = ""
        parameters = {"type": "object", "properties": {}}
        try:
            sig = inspect.signature(fn)
            for param_name, param in sig.parameters.items():
                param_schema = {"type": "string"}
                if param.default is not inspect.Parameter.empty:
                    param_schema["default"] = param.default
                parameters["properties"][param_name] = param_schema
        except (ValueError, TypeError):
            pass
        self._tools[name] = {
            "fn": fn,
            "agents": agents,
            "description": description,
            "parameters": parameters,
        }

    def get_tools_for_agent(self, agent_name: str) -> list[dict[str, Any]]:
        """Return list of tool schemas for the given agent."""
        tools = []
        for name, meta in self._tools.items():
            if agent_name in meta["agents"]:
                tools.append({
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["parameters"],
                })
        return tools

    def execute(self, name: str, kwargs: dict[str, Any]) -> Any:
        """Call the registered function with kwargs."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")
        return self._tools[name]["fn"](**kwargs)
