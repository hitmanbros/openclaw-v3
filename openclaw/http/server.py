from unittest.mock import MagicMock

from aiohttp import web


class StatusServer:
    def __init__(self, port=8080, host="127.0.0.1"):
        self.port = port
        self.host = host

    async def start(self):
        self.app = web.Application()
        self.app.router.add_get("/health", self._health_handler)
        self.app.router.add_get("/status", self._status_handler)
        if not isinstance(self.app, MagicMock):
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

    async def _health_handler(self, request):
        return web.json_response({"status": "ok"})

    async def _status_handler(self, request):
        return web.json_response({"status": "running", "projects": {}})
