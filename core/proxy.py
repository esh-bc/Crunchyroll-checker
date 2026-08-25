"""
Proxy Manager
Parse, validate, rotate, and health-track proxies.
Supports HTTP, HTTPS, SOCKS4, SOCKS5, IP:PORT, IP:PORT:USER:PASS.
"""

import re
import time
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

import config

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# PARSING
# ═══════════════════════════════════════════
_PROXY_RE = re.compile(
    r"^(?:(https?|socks[45])://)?"          # optional scheme
    r"([^:]+)"                                # host
    r":(\d{1,5})"                            # port
    r"(?::([^:]+):(.+))?$"                    # optional user:pass
)


def parse_proxy(line: str) -> Optional[dict[str, Any]]:
    """Parse a proxy string into a normalized dict. Returns None on failure."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Already has scheme
    if "://" in line:
        scheme_end = line.index("://")
        scheme = line[:scheme_end].lower()
        rest = line[scheme_end + 3:]

        # Extract user:pass if present
        user = ""
        pwd = ""
        if "@" in rest:
            auth_part, rest = rest.rsplit("@", 1)
            if ":" in auth_part:
                user, pwd = auth_part.split(":", 1)

        # Parse host:port from rest
        parts = rest.rsplit(":", 1)
        if len(parts) != 2:
            return None
        host = parts[0]
        try:
            port_int = int(parts[1])
        except ValueError:
            return None
        if not (1 <= port_int <= 65535):
            return None
        url = line
    else:
        m = _PROXY_RE.match(line)
        if not m:
            return None
        _, host, port, user, pwd = m.groups()
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            return None
        # Default to http if user:pass present, else http
        scheme = "http"
        if user and pwd:
            url = f"{scheme}://{user}:{pwd}@{host}:{port_int}"
        else:
            url = f"{scheme}://{host}:{port_int}"

    # Normalize socks to proper URL
    if line.startswith("socks4://") or line.startswith("socks5://"):
        url = line
        scheme = "socks5" if "socks5" in line[:10] else "socks4"

    return {
        "url": url,
        "scheme": scheme,
        "host": host,
        "port": port_int,
        "has_auth": bool(user and pwd),
        "raw": line,
        "alive": None,
        "latency_ms": None,
    }


def parse_proxy_file(text: str) -> list[dict[str, Any]]:
    """Parse a multi-line proxy file. Returns list of proxy dicts."""
    results = []
    for line in text.splitlines():
        p = parse_proxy(line)
        if p:
            results.append(p)
    return results


# ═══════════════════════════════════════════
# PROXY MANAGER
# ═══════════════════════════════════════════
@dataclass
class ProxyManager:
    """
    Thread-safe (asyncio-safe) proxy rotation with health tracking.
    """
    proxies: list[dict[str, Any]] = field(default_factory=list)
    _index: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def __len__(self) -> int:
        return len(self.proxies)

    @property
    def alive_count(self) -> int:
        return sum(1 for p in self.proxies if p.get("alive"))

    def load(self, proxy_list: list[dict[str, Any]]) -> None:
        self.proxies = proxy_list
        self._index = 0
        log.info("ProxyManager loaded %d proxies", len(proxy_list))

    def load_from_strings(self, lines: list[str]) -> int:
        parsed = parse_proxy_file("\n".join(lines))
        self.proxies = parsed
        self._index = 0
        return len(parsed)

    async def get_next(self) -> Optional[str]:
        """Round-robin rotation among alive proxies."""
        if not self.proxies:
            return None
        alive = [p for p in self.proxies if p.get("alive")]
        if not alive:
            return None
        async with self._lock:
            proxy = alive[self._index % len(alive)]
            self._index += 1
            return proxy["url"]

    async def get_random(self) -> Optional[str]:
        """Get a random alive proxy URL."""
        import random
        alive = [p for p in self.proxies if p.get("alive")]
        if not alive:
            return None
        return random.choice(alive)["url"]

    def mark_dead(self, url: str) -> None:
        for p in self.proxies:
            if p["url"] == url:
                p["alive"] = False
                p["fail_count"] = p.get("fail_count", 0) + 1
                break

    def clear(self) -> None:
        self.proxies.clear()
        self._index = 0


# ═══════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════
async def validate_proxy(
    proxy_url: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int = config.PROXY_TEST_TIMEOUT,
) -> dict[str, Any]:
    """
    Validate a single proxy against the Crunchyroll API endpoint.
    Returns {"url": ..., "alive": bool, "latency_ms": int|None, "error": str}
    """
    result: dict[str, Any] = {
        "url": proxy_url,
        "alive": False,
        "latency_ms": None,
        "error": "",
    }
    async with semaphore:
        start = time.monotonic()
        try:
            kw: dict[str, Any] = {}
            if proxy_url.startswith("socks"):
                from aiohttp_socks import ProxyConnector
                conn = ProxyConnector.from_url(proxy_url, limit=2)
                timeout_obj = aiohttp.ClientTimeout(total=timeout)
                async with aiohttp.ClientSession(connector=conn, timeout=timeout_obj) as s:
                    async with s.get(config.PROXY_TEST_URL) as resp:
                        elapsed_ms = int((time.monotonic() - start) * 1000)
                        result["alive"] = resp.status in (200, 401, 403)
                        result["latency_ms"] = elapsed_ms
                        if not result["alive"]:
                            result["error"] = f"HTTP {resp.status}"
            else:
                timeout_obj = aiohttp.ClientTimeout(total=timeout)
                async with session.get(
                    config.PROXY_TEST_URL,
                    proxy=proxy_url,
                    timeout=timeout_obj,
                ) as resp:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    result["alive"] = resp.status in (200, 401, 403)
                    result["latency_ms"] = elapsed_ms
                    if not result["alive"]:
                        result["error"] = f"HTTP {resp.status}"
        except asyncio.TimeoutError:
            result["error"] = "Timeout"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            result["error"] = str(exc)[:60]
    return result


async def validate_proxies_bulk(
    proxy_urls: list[str],
    on_progress: Optional[Any] = None,
    max_concurrent: int = config.MAX_PROXY_TEST_CONCURRENT,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Validate a list of proxies concurrently.
    Returns (results, alive_count, dead_count).
    on_progress(alive, dead, total, current) callback for live updates.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    connector = aiohttp.TCPConnector(limit=max_concurrent + 10, force_close=True)
    timeout = aiohttp.ClientTimeout(total=config.PROXY_TEST_TIMEOUT + 2)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        results = []
        alive_count = 0
        dead_count = 0
        total = len(proxy_urls)

        for i, url in enumerate(proxy_urls):
            r = await validate_proxy(url, session, semaphore)
            results.append(r)
            if r["alive"]:
                alive_count += 1
            else:
                dead_count += 1
            if on_progress:
                on_progress(alive_count, dead_count, total, i + 1)

    return results, alive_count, dead_count
