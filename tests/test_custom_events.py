"""Tests for custom Matrix events."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from openclaw.matrix.events import EventBuilder


class TestEventBuilder:
    """Custom event building behavior."""

    def test_slice_update_event(self):
        """Slice update event has correct schema."""
        event = EventBuilder.slice_update(
            project_id="alpha",
            slice_id=3,
            status="done",
            agent="worker",
            percent=60,
        )
        
        assert event["type"] == "com.openclaw.slice_update"
        assert event["content"]["project_id"] == "alpha"
        assert event["content"]["slice_id"] == 3
        assert event["content"]["status"] == "done"
        assert event["content"]["render_as"] == "progress_bar"
        assert event["content"]["data"]["percent"] == 60

    def test_status_event(self):
        """Status event has correct schema."""
        event = EventBuilder.status(
            projects=[{"name": "alpha", "status": "running"}],
        )
        
        assert event["type"] == "com.openclaw.status"
        assert "projects" in event["content"]["data"]

    def test_dashboard_event(self):
        """Dashboard event has metrics data."""
        event = EventBuilder.dashboard(
            metric="tokens_used",
            value=1500,
        )
        
        assert event["type"] == "com.openclaw.dashboard"
        assert event["content"]["data"]["metric"] == "tokens_used"

    def test_fallback_html_included(self):
        """Events include fallback HTML for unknown clients."""
        event = EventBuilder.slice_update(
            project_id="alpha",
            slice_id=3,
            status="done",
        )
        
        assert "fallback_html" in event["content"]
        assert "Slice 3" in event["content"]["fallback_html"]

    def test_event_includes_timestamp(self):
        """Events include ISO timestamp."""
        event = EventBuilder.slice_update(
            project_id="alpha",
            slice_id=1,
            status="running",
        )
        
        assert "timestamp" in event["content"]
        assert "T" in event["content"]["timestamp"]

    def test_render_as_hint(self):
        """Events include render_as hint for clients."""
        event = EventBuilder.slice_update(
            project_id="alpha",
            slice_id=1,
            status="running",
        )
        
        assert event["content"]["render_as"] == "progress_bar"
