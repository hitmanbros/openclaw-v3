"""Custom Matrix event builder for OpenClaw."""

from datetime import datetime, timezone


class EventBuilder:
    """Builds custom Matrix events for OpenClaw."""

    @staticmethod
    def _base_content(data=None, fallback_html="", render_as=None):
        content = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fallback_html": fallback_html,
        }
        if data is not None:
            content["data"] = data
        if render_as is not None:
            content["render_as"] = render_as
        return content

    @staticmethod
    def slice_update(project_id, slice_id, status, agent=None, percent=0):
        data = {"percent": percent}
        if agent is not None:
            data["agent"] = agent

        return {
            "type": "com.openclaw.slice_update",
            "content": {
                "project_id": project_id,
                "slice_id": slice_id,
                "status": status,
                "render_as": "progress_bar",
                "data": data,
                "fallback_html": f"Slice {slice_id}: {status}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    @staticmethod
    def status(projects):
        return {
            "type": "com.openclaw.status",
            "content": {
                "data": {"projects": projects},
                "fallback_html": "OpenClaw status update",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    @staticmethod
    def dashboard(metric, value):
        return {
            "type": "com.openclaw.dashboard",
            "content": {
                "data": {"metric": metric, "value": value},
                "fallback_html": f"Dashboard metric: {metric} = {value}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
