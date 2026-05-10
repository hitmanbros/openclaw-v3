"""Agent prompt loader — constructs system prompts from markdown files."""

import re
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "agents"


def load_prompt(agent_name: str, room_context: str = "") -> str:
    """Load and assemble an agent's system prompt.

    Reads BASE.md (shared context) + {agent}.md (specific identity).
    Optionally appends room/project context.
    """
    base_path = AGENTS_DIR / "BASE.md"
    agent_path = AGENTS_DIR / f"{agent_name}.md"

    parts = []

    # Load base context
    if base_path.exists():
        parts.append(_strip_frontmatter(base_path.read_text()))

    # Load agent-specific prompt
    if agent_path.exists():
        parts.append(_strip_frontmatter(agent_path.read_text()))
    else:
        parts.append(f"# {agent_name}\n\nYou are the {agent_name} agent.")

    # Append runtime context
    if room_context:
        parts.append(f"\n# Current Context\n\n{room_context}")

    return "\n\n---\n\n".join(parts)


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (---\nkey: value\n---)."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text.strip()


def build_messages(agent_name: str, user_message: str, room_context: str = "", history: list = None) -> list:
    """Build a full messages list for the LLM API.

    Returns: [{"role": "system", ...}, {"role": "user", ...}, ...]
    """
    system = load_prompt(agent_name, room_context)
    messages = [{"role": "system", "content": system}]

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_message})
    return messages
