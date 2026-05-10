"""Ops room integration."""


class OpsRoom:
    """Post updates to a Matrix ops room."""

    def __init__(self, matrix_client, ops_room):
        self.matrix_client = matrix_client
        self.ops_room = ops_room

    async def post_error(self, message, project=None, slice_id=None):
        body = message
        if project is not None:
            body += f" | project={project}"
        if slice_id is not None:
            body += f" slice_id={slice_id}"
        await self.matrix_client.room_send(
            room_id=self.ops_room,
            content={"body": body},
        )

    async def post_status(self, projects):
        lines = []
        for p in projects:
            line = f"{p['name']}: {p['status']} ({p['slices_done']}/{p['slices_total']})"
            lines.append(line)
        body = "\n".join(lines)
        await self.matrix_client.room_send(
            room_id=self.ops_room,
            content={"body": body},
        )

    async def post_alert(self, level, message):
        await self.matrix_client.room_send(
            room_id=self.ops_room,
            content={"body": f"[{level}] {message}"},
        )
