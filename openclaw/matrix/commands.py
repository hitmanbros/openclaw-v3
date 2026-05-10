"""Matrix command parser."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Command:
    """A parsed Matrix command."""

    name: str
    args: list[str]


def parse_command(body: str) -> Optional[Command]:
    """Parse a command from a message body.

    Commands start with '!' followed by the command name and optional arguments.
    Returns None if the message is not a command (natural language).

    Examples:
        >>> parse_command("!ping")
        Command(name='ping', args=[])
        >>> parse_command("!plan github.com/owner/repo")
        Command(name='plan', args=['github.com/owner/repo'])
        >>> parse_command("hello bot")
        None
    """
    body = body.strip()
    if not body.startswith("!"):
        return None

    # Remove '!' prefix and split on whitespace
    parts = body[1:].split()
    if not parts:
        return None

    name = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []

    return Command(name=name, args=args)
