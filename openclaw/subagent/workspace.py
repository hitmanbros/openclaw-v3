import json
import os
import fcntl
from pathlib import Path


class WorkspaceClient:
    def __init__(self, workspace_path):
        self.workspace_path = Path(workspace_path)

    def read(self, defaults=None):
        if not self.workspace_path.exists():
            return dict(defaults) if defaults else {}

        with open(self.workspace_path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        if defaults:
            merged = dict(defaults)
            merged.update(data)
            return merged
        return data

    def write(self, data):
        self.workspace_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.workspace_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, self.workspace_path)

    def update(self, patch):
        data = self.read()
        data.update(patch)
        self.write(data)
