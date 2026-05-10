"""Tests for budget gate."""

import pytest
from unittest.mock import MagicMock

from openclaw.budget.gate import BudgetGate


class TestBudgetGate:
    """Budget gate behavior."""

    @pytest.fixture
    def gate(self):
        return BudgetGate(
            daily_cap=1000,
            hourly_cap=500,
            global_cap=5000,
        )

    def test_check_within_limits_passes(self, gate):
        """Usage within limits passes."""
        result = gate.check(tokens=100)
        assert result is True

    def test_check_exceeds_daily_fails(self, gate):
        """Usage exceeding daily cap fails."""
        gate.daily_used = 950
        result = gate.check(tokens=100)
        assert result is False

    def test_check_exceeds_hourly_fails(self, gate):
        """Usage exceeding hourly cap fails."""
        gate.hourly_used = 450
        result = gate.check(tokens=100)
        assert result is False

    def test_check_exceeds_global_fails(self, gate):
        """Usage exceeding global cap fails."""
        gate.global_used = 4950
        result = gate.check(tokens=100)
        assert result is False

    def test_record_adds_to_counters(self, gate):
        """Recording usage updates all counters."""
        gate.record(tokens=100)
        assert gate.daily_used == 100
        assert gate.hourly_used == 100
        assert gate.global_used == 100

    def test_estimate_within_budget_passes(self, gate):
        """Estimate within budget passes."""
        result = gate.estimate(tokens=100)
        assert result is True

    def test_estimate_exceeds_budget_fails(self, gate):
        """Estimate exceeding budget fails with details."""
        gate.daily_used = 900
        result = gate.estimate(tokens=200)
        assert result is False

    def test_reset_hourly_clears_hourly_only(self, gate):
        """Hourly reset clears hourly but not daily."""
        gate.daily_used = 300
        gate.hourly_used = 400
        gate.reset_hourly()
        assert gate.hourly_used == 0
        assert gate.daily_used == 300

    def test_reset_daily_clears_daily_and_hourly(self, gate):
        """Daily reset clears both daily and hourly."""
        gate.daily_used = 800
        gate.hourly_used = 200
        gate.reset_daily()
        assert gate.daily_used == 0
        assert gate.hourly_used == 0

    def test_get_status_returns_current_usage(self, gate):
        """Status shows current usage and limits."""
        gate.record(tokens=250)
        status = gate.get_status()
        assert status["daily_used"] == 250
        assert status["daily_cap"] == 1000
        assert status["hourly_used"] == 250
        assert status["hourly_cap"] == 500
        assert status["remaining_daily"] == 750
