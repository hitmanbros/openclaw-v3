"""Agent tool loop — iterative LLM + tool execution."""

import json
import traceback
from pathlib import Path

from openclaw.tools import create_registry


class AgentLoop:
    """Runs an agent task with iterative tool use."""

    def __init__(self, llm, system_prompt, agent_name, workspace_dir, max_iterations=20):
        self.llm = llm
        self.system_prompt = system_prompt
        self.agent_name = agent_name
        self.workspace_dir = Path(workspace_dir)
        self.max_iterations = max_iterations
        self.tools = create_registry()
        self.src_dir = self.workspace_dir / "src"

    async def run(self, task_message):
        """Run the agent loop until completion or max iterations.

        Returns the final assistant content string.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task_message},
        ]

        tools = self.tools.get_tools_for_agent(self.agent_name)

        for i in range(self.max_iterations):
            response = await self.llm.chat(messages, tools=tools if tools else None)

            tool_calls = response.get("tool_calls")
            if not tool_calls:
                return response.get("content", "")

            messages.append(response)

            for tool_call in tool_calls:
                result = self._execute_tool(tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": self._stringify(result),
                })

        return "Maximum iterations reached without completion."

    def _execute_tool(self, tool_call):
        """Execute a single tool call and return the result."""
        name = tool_call["function"]["name"]
        try:
            kwargs = json.loads(tool_call["function"]["arguments"])
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON in tool arguments: {exc}"}

        # Inject workspace for path validation / cwd
        kwargs.setdefault("workspace", str(self.src_dir))

        try:
            return self.tools.execute(name, kwargs)
        except Exception as exc:
            return {"error": str(exc), "traceback": traceback.format_exc()}

    @staticmethod
    def _stringify(value):
        """Convert tool result to string for LLM message content."""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, indent=2)
        except (TypeError, ValueError):
            return str(value)
