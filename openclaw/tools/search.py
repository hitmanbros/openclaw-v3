import os
import re
from pathlib import Path


def _validate_workspace(path: str, workspace: str | None):
    if workspace is None:
        return
    abs_path = os.path.abspath(os.path.expanduser(path))
    abs_workspace = os.path.abspath(os.path.expanduser(workspace))
    if not abs_path.startswith(abs_workspace + os.sep) and abs_path != abs_workspace:
        raise ValueError(f"Path {path} is outside workspace {workspace}")


def grep_tool(path, pattern, workspace=None):
    _validate_workspace(path, workspace)

    expanded = os.path.expanduser(path)
    p = Path(expanded)
    regex = re.compile(pattern)
    matches = []

    if p.is_file():
        files = [p]
    else:
        files = [f for f in p.rglob("*") if f.is_file()]

    for f in files:
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if regex.search(line):
                        matches.append(line.rstrip("\n"))
        except (PermissionError, IsADirectoryError, OSError):
            continue

    return "\n".join(matches)


def find_tool(path, pattern, workspace=None):
    _validate_workspace(path, workspace)

    expanded = os.path.expanduser(path)
    p = Path(expanded)

    results = []
    for f in p.rglob(pattern):
        results.append(str(f))

    return "\n".join(results)


def ls_tool(path, workspace=None):
    _validate_workspace(path, workspace)

    expanded = os.path.expanduser(path)
    p = Path(expanded)

    entries = []
    for entry in p.iterdir():
        entries.append(entry.name)

    return "\n".join(sorted(entries))
