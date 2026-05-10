import os
import re
from pathlib import Path
from typing import Any

import yaml


ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

DEFAULTS = {
    "defaults": {
        "worker_cap": 3,
        "daily_input_cap": 3_000_000,
        "hourly_input_cap": 1_000_000,
        "max_turns": 50,
    },
    "http": {
        "port": 8080,
        "host": "127.0.0.1",
    },
}


class ConfigLoader:
    def __init__(self, config_path: Any):
        self.config_path = Path(config_path)

    def load(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(self.config_path)

        with open(self.config_path, "r") as f:
            raw = yaml.safe_load(f) or {}

        substituted = self._substitute(raw)
        return self._merge_defaults(substituted)

    def _substitute(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._substitute(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._substitute(item) for item in value]
        if isinstance(value, str):
            return ENV_VAR_PATTERN.sub(self._replace_env, value)
        return value

    def _replace_env(self, match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    def _merge_defaults(self, config: dict) -> dict:
        merged = {}
        for key, value in DEFAULTS.items():
            if isinstance(value, dict):
                merged[key] = {**value, **config.get(key, {})}
            else:
                merged[key] = config.get(key, value)
        for key, value in config.items():
            if key not in merged:
                merged[key] = value
        return merged
