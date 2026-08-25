"""Lightweight HTTP health-check server."""

import asyncio
import logging
from typing import Optional  # ← this line was missing
from aiohttp import web

import config

log = logging.getLogger(__name__)
_runner: Optional[web.AppRunner] = None


async def start_health_server() -> None:
    """Start the health-check HTTP server on config.HEALTH_PORT."""
    global _runner
    app = web.Application()
    app.add_routes([web.get("/health", _health_handler)])
    _runner = web.AppRunner(app)
    await _runner.setup()
    site = web.TCPSite(_runner, "0.0.0.0", config.HEALTH_PORT)
    await site.start()
    log.info("Health-check server on :%d/health", config.HEALTH_PORT)


async def stop_health_server() -> None:
    """Stop the health-check server."""
    global _runner
    if _runner:
        await _runner.cleanup()
        _runner = None
        log.info("Health-check server stopped")


async def _health_handler(request: web.Request) -> web.Response:
    return web.Response(
        text='{"status": "ok", "service": "crunchybot"}',
        content_type="application/json",
        status=200,
    )
