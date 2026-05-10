import json
import os
import fcntl
from pathlib import Path


class InboxClient:
    def __init__(self, inbox_path):
        self.inbox_path = Path(inbox_path)

    def _load(self):
        if not self.inbox_path.exists():
            return []
        with open(self.inbox_path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _save(self, messages):
        self.inbox_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.inbox_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(messages, f)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, self.inbox_path)

    def send(self, from_agent, to_agent, content):
        messages = self._load()
        messages.append({
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "read": False,
        })
        self._save(messages)

    def read_all(self):
        return self._load()

    def read_for(self, agent_name):
        messages = self._load()
        result = [m for m in messages if m["to"] == agent_name]
        for m in messages:
            if m["to"] == agent_name:
                m["read"] = True
        self._save(messages)
        return result

    def read_unread_for(self, agent_name):
        messages = self._load()
        result = [m for m in messages if m["to"] == agent_name and not m["read"]]
        for m in messages:
            if m["to"] == agent_name and not m["read"]:
                m["read"] = True
        self._save(messages)
        return result
