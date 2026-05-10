import os
import subprocess


DISALLOWED_STARTS = (
    "curl ",
    "wget ",
    "ssh ",
    "sudo ",
    "mkfs ",
    "dd ",
    "iptables ",
    "systemctl stop",
    "userdel ",
    "chmod -R ",
    "eval ",
    "npm install",
    "pip install",
    "git push",
)


def _is_allowed(command: str) -> bool:
    lowered = command.strip().lower()
    if lowered.startswith("rm ") and "-rf" in lowered:
        return False
    for blocked in DISALLOWED_STARTS:
        if lowered.startswith(blocked):
            return False
    return True


def bash_tool(command, workspace, timeout=30):
    if not _is_allowed(command):
        raise PermissionError(f"Command blocked: {command}")

    abs_workspace = os.path.abspath(os.path.expanduser(workspace))

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=abs_workspace,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout} seconds")
