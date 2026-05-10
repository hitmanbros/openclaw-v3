import os
from pathlib import Path


SENSITIVE_PREFIXES = [
    os.path.expanduser("~/.ssh"),
    os.path.expanduser("~/.aws"),
]

SENSITIVE_SUFFIXES = (".pem", ".key")


def _is_sensitive(path: str) -> bool:
    expanded = os.path.expanduser(path)
    abs_path = os.path.abspath(expanded)

    for prefix in SENSITIVE_PREFIXES:
        if abs_path.startswith(prefix):
            return True

    if abs_path.endswith(SENSITIVE_SUFFIXES):
        return True

    return False


def _validate_workspace(path: str, workspace: str | None):
    if workspace is None:
        return
    abs_path = os.path.abspath(os.path.expanduser(path))
    abs_workspace = os.path.abspath(os.path.expanduser(workspace))
    if not abs_path.startswith(abs_workspace + os.sep) and abs_path != abs_workspace:
        raise ValueError(f"Path {path} is outside workspace {workspace}")


def read_tool(path, offset=None, limit=None, workspace=None):
    if _is_sensitive(path):
        raise PermissionError(f"Access to sensitive file {path} is blocked")

    _validate_workspace(path, workspace)

    expanded = os.path.expanduser(path)

    with open(expanded, "r") as f:
        lines = f.readlines()

    if offset is not None:
        start = offset - 1
        if start < 0:
            start = 0
        lines = lines[start:]

    if limit is not None:
        lines = lines[:limit]

    return "".join(lines)


def write_tool(path, content, workspace=None):
    _validate_workspace(path, workspace)

    expanded = os.path.expanduser(path)
    Path(expanded).parent.mkdir(parents=True, exist_ok=True)

    with open(expanded, "w") as f:
        f.write(content)


def edit_tool(path, oldText=None, newText=None, edits=None, workspace=None):
    _validate_workspace(path, workspace)

    expanded = os.path.expanduser(path)

    with open(expanded, "r") as f:
        content = f.read()

    if edits is not None:
        for edit in edits:
            ot = edit["oldText"]
            nt = edit["newText"]
            if ot not in content:
                raise ValueError(f"oldText not found in file: {ot!r}")
            content = content.replace(ot, nt, 1)
    else:
        if oldText is None or newText is None:
            raise ValueError("oldText and newText required when edits not provided")
        if oldText not in content:
            raise ValueError(f"oldText not found in file: {oldText!r}")
        content = content.replace(oldText, newText, 1)

    with open(expanded, "w") as f:
        f.write(content)
