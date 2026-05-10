"""Tool registry initialization."""

from openclaw.tools.registry import ToolRegistry
from openclaw.tools.fs import read_tool, write_tool, edit_tool
from openclaw.tools.bash import bash_tool
from openclaw.tools.search import grep_tool, find_tool, ls_tool


def create_registry() -> ToolRegistry:
    """Create and populate a ToolRegistry with all available tools."""
    registry = ToolRegistry()

    registry.register(
        "read",
        read_tool,
        agents={"nexus", "scout", "planner", "slicer", "orchestrator", "worker", "reviewer", "tester", "communicator", "security-auditor"},
        description="Read the contents of a file. Supports text files and images (jpg, png, gif, webp). Images are sent as attachments. For text files, output is truncated to 2000 lines or 50KB (whichever is hit first). Use offset/limit for large files. When you need the full file, continue with offset until complete.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read (relative or absolute)"},
                "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)"},
                "limit": {"type": "integer", "description": "Maximum number of lines to read"},
                "workspace": {"type": "string", "description": "Workspace root for path validation"},
            },
            "required": ["path"],
        },
    )

    registry.register(
        "write",
        write_tool,
        agents={"nexus", "scout", "planner", "slicer", "orchestrator", "worker", "reviewer", "tester", "communicator", "security-auditor"},
        description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Automatically creates parent directories.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write (relative or absolute)"},
                "content": {"type": "string", "description": "Content to write to the file"},
                "workspace": {"type": "string", "description": "Workspace root for path validation"},
            },
            "required": ["path", "content"],
        },
    )

    registry.register(
        "edit",
        edit_tool,
        agents={"nexus", "scout", "planner", "slicer", "orchestrator", "worker", "reviewer", "tester", "communicator", "security-auditor"},
        description="Edit a single file using exact text replacement. oldText must match a unique, non-overlapping region of the original file. Multiple disjoint edits go in one call via edits array.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit (relative or absolute)"},
                "oldText": {"type": "string", "description": "Exact text for one targeted replacement"},
                "newText": {"type": "string", "description": "Replacement text"},
                "edits": {
                    "type": "array",
                    "description": "Array of {oldText, newText} edits for multiple changes in one file",
                    "items": {
                        "type": "object",
                        "properties": {
                            "oldText": {"type": "string"},
                            "newText": {"type": "string"},
                        },
                        "required": ["oldText", "newText"],
                    },
                },
                "workspace": {"type": "string", "description": "Workspace root for path validation"},
            },
            "required": ["path"],
        },
    )

    registry.register(
        "bash",
        bash_tool,
        agents={"nexus", "scout", "planner", "slicer", "orchestrator", "worker", "reviewer", "tester", "communicator", "security-auditor"},
        description="Execute a bash command in the current working directory. Returns stdout and stderr. Output is truncated to last 2000 lines or 50KB. Optionally provide a timeout in seconds.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"},
                "workspace": {"type": "string", "description": "Working directory for the command"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (optional)"},
            },
            "required": ["command", "workspace"],
        },
    )

    registry.register(
        "grep",
        grep_tool,
        agents={"nexus", "scout", "planner", "slicer", "orchestrator", "worker", "reviewer", "tester", "communicator", "security-auditor"},
        description="Search file contents for patterns. Respects .gitignore.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory or file path to search"},
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "workspace": {"type": "string", "description": "Workspace root for path validation"},
            },
            "required": ["path", "pattern"],
        },
    )

    registry.register(
        "find",
        find_tool,
        agents={"nexus", "scout", "planner", "slicer", "orchestrator", "worker", "reviewer", "tester", "communicator", "security-auditor"},
        description="Find files by glob pattern. Respects .gitignore.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to search"},
                "pattern": {"type": "string", "description": "Glob pattern to match"},
                "workspace": {"type": "string", "description": "Workspace root for path validation"},
            },
            "required": ["path", "pattern"],
        },
    )

    registry.register(
        "ls",
        ls_tool,
        agents={"nexus", "scout", "planner", "slicer", "orchestrator", "worker", "reviewer", "tester", "communicator", "security-auditor"},
        description="List directory contents.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list"},
                "workspace": {"type": "string", "description": "Workspace root for path validation"},
            },
            "required": ["path"],
        },
    )

    return registry
