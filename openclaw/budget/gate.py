"""Budget gate for token usage limits."""


class BudgetGate:
    """Enforces daily, hourly, and global token budgets."""

    def __init__(self, daily_cap, hourly_cap, global_cap):
        self.daily_cap = daily_cap
        self.hourly_cap = hourly_cap
        self.global_cap = global_cap
        self.daily_used = 0
        self.hourly_used = 0
        self.global_used = 0

    def check(self, tokens):
        """Return True if tokens fit within all remaining limits."""
        return (
            self.daily_used + tokens <= self.daily_cap
            and self.hourly_used + tokens <= self.hourly_cap
            and self.global_used + tokens <= self.global_cap
        )

    def record(self, tokens):
        """Add tokens to all used counters."""
        self.daily_used += tokens
        self.hourly_used += tokens
        self.global_used += tokens

    def estimate(self, tokens):
        """Return True if estimated usage fits without recording."""
        return self.check(tokens)

    def reset_hourly(self):
        """Reset hourly counter."""
        self.hourly_used = 0

    def reset_daily(self):
        """Reset daily and hourly counters."""
        self.daily_used = 0
        self.hourly_used = 0

    def get_status(self):
        """Return dict with used/cap/remaining for all limits."""
        return {
            "daily_used": self.daily_used,
            "daily_cap": self.daily_cap,
            "remaining_daily": self.daily_cap - self.daily_used,
            "hourly_used": self.hourly_used,
            "hourly_cap": self.hourly_cap,
            "remaining_hourly": self.hourly_cap - self.hourly_used,
            "global_used": self.global_used,
            "global_cap": self.global_cap,
            "remaining_global": self.global_cap - self.global_used,
        }
