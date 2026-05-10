"""Config validation."""

from typing import Any


class ConfigValidationError(ValueError):
    """Raised when a config value fails validation."""

    pass


# Validation rules: (type, min, max, allowed_values)
_CONFIG_RULES = {
    "worker_cap": (int, 1, 10, None),
    "daily_input_cap": (int, 100_000, None, None),
    "hourly_input_cap": (int, 10_000, None, None),
    "model": (str, None, None, {"kimi-2.6", "kimi-2.5"}),
    "max_turns": (int, 1, 200, None),
    "bash_timeout": (int, 5, 300, None),
    "snapshot_keep": (int, 1, 20, None),
    "pulse_interval_sec": (int, 60, 3600, None),
    "escalation_timeout_sec": (int, 300, 86400, None),
    "hitl_timeout_sec": (int, 300, 86400, None),
    "auto_approve_prd": (bool, None, None, None),
    "commit_message_template": (str, None, None, None),
}

_SENSITIVE_KEYS = {
    "matrix.access_token",
    "llm.api_key",
    "github.token",
    "github.webhook_secret",
}


def validate_config_key(key: str, value: Any) -> Any:
    """Validate a config key/value pair.

    Args:
        key: The config key name
        value: The proposed value

    Returns:
        The validated (and possibly converted) value

    Raises:
        ConfigValidationError: If the key is unknown, sensitive, or value is invalid
    """
    # Check sensitive keys
    if key in _SENSITIVE_KEYS or any(key.endswith(k.split(".")[-1]) for k in _SENSITIVE_KEYS):
        raise ConfigValidationError(
            f"'{key}' is a sensitive key and cannot be changed via command. "
            "Edit config.yaml directly and restart."
        )

    # Check if key is known
    if key not in _CONFIG_RULES:
        raise ConfigValidationError(
            f"Unknown config key '{key}'. Use !config help to see available keys."
        )

    expected_type, min_val, max_val, allowed = _CONFIG_RULES[key]

    # Convert string to expected type
    if expected_type is bool and isinstance(value, str):
        value = value.lower() in ("true", "1", "yes", "on")
    elif expected_type is int and isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            raise ConfigValidationError(
                f"'{key}' must be an integer, got '{value}'"
            )

    # Type check
    if not isinstance(value, expected_type):
        raise ConfigValidationError(
            f"'{key}' must be of type {expected_type.__name__}, got {type(value).__name__}"
        )

    # Range check
    if min_val is not None and max_val is not None and (value < min_val or value > max_val):
        raise ConfigValidationError(
            f"'{key}' must be between {min_val} and {max_val}, got {value}"
        )
    if min_val is not None and value < min_val:
        raise ConfigValidationError(
            f"'{key}' must be >= {min_val}, got {value}"
        )
    if max_val is not None and value > max_val:
        raise ConfigValidationError(
            f"'{key}' must be <= {max_val}, got {value}"
        )

    # Allowed values check
    if allowed is not None and value not in allowed:
        raise ConfigValidationError(
            f"'{key}' must be one of {sorted(allowed)}, got '{value}'"
        )

    return value
