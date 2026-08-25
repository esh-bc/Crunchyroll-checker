"""
MongoDB Database Layer
Async operations via Motor. All collections and indexes defined here.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

import config

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# CONNECTION
# ═══════════════════════════════════════════
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect() -> AsyncIOMotorDatabase:
    """Connect to MongoDB and ensure indexes. Call once at startup."""
    global _client, _db
    _client = AsyncIOMotorClient(
        config.MONGO_URI,
        maxPoolSize=20,
        minPoolSize=3,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    _db = _client[config.MONGO_DB_NAME]
    await _ensure_indexes()
    log.info("MongoDB connected: %s", config.MONGO_DB_NAME)
    return _db


async def disconnect() -> None:
    """Gracefully close MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        log.info("MongoDB disconnected")


def get_db() -> AsyncIOMotorDatabase:
    """Return the database instance. Must call connect() first."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call db.connect() first.")
    return _db


# ═══════════════════════════════════════════
# INDEX HELPERS
# ═══════════════════════════════════════════
async def _ensure_indexes() -> None:
    db = get_db()

    # Users
    await db.users.create_index("telegram_id", unique=True)
    await db.users.create_index("plan")
    await db.users.create_index("banned")
    await db.users.create_index("joined_at")

    # Redeem keys
    await db.redeem_keys.create_index("key", unique=True)
    await db.redeem_keys.create_index("plan")
    await db.redeem_keys.create_index([("used_by", ASCENDING), ("used_at", ASCENDING)])
    await db.redeem_keys.create_index("expires_at")

    # Proxies
    await db.proxies.create_index("url", unique=True)
    await db.proxies.create_index("alive")
    await db.proxies.create_index("last_checked")

    # Jobs
    await db.jobs.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    await db.jobs.create_index("status")
    await db.jobs.create_index("created_at")

    # Bot config
    await db.bot_config.create_index("key", unique=True)

    # Stats
    await db.stats.create_index("date")
    await db.stats.create_index([("date", DESCENDING), ("user_id", ASCENDING)])

    log.info("Database indexes ensured")


# ═══════════════════════════════════════════
# USER OPERATIONS
# ═══════════════════════════════════════════
async def get_or_create_user(
    telegram_id: int,
    username: str = "",
    first_name: str = "",
    last_name: str = "",
    is_bot: bool = False,
    language_code: str = "",
) -> dict[str, Any]:
    db = get_db()
    existing = await db.users.find_one({"telegram_id": telegram_id})
    if existing:
        # Update mutable fields
        update = {"last_seen": datetime.now(timezone.utc)}
        if username:
            update["username"] = username
        if first_name:
            update["first_name"] = first_name
        if last_name:
            update["last_name"] = last_name
        await db.users.update_one({"telegram_id": telegram_id}, {"$set": update})
        return existing

    user_doc = {
        "telegram_id": telegram_id,
        "username": username or "",
        "first_name": first_name or "",
        "last_name": last_name or "",
        "is_bot": is_bot,
        "language_code": language_code or "",
        "plan": "free",
        "verified": False,
        "banned": False,
        "total_checked": 0,
        "total_hits": 0,
        "total_free": 0,
        "total_bad": 0,
        "total_sessions": 0,
        "session_checked": 0,
        "session_hits": 0,
        "session_free": 0,
        "session_bad": 0,
        "jobs_completed": 0,
        "joined_at": datetime.now(timezone.utc),
        "last_seen": datetime.now(timezone.utc),
        "plan_set_at": None,
        "plan_expires_at": None,
    }
    await db.users.insert_one(user_doc)
    log.info("New user: %s (%s)", telegram_id, username or first_name)
    return user_doc


async def get_user(telegram_id: int) -> Optional[dict[str, Any]]:
    return await get_db().users.find_one({"telegram_id": telegram_id})


async def update_user(telegram_id: int, update: dict[str, Any]) -> bool:
    result = await get_db().users.update_one(
        {"telegram_id": telegram_id}, {"$set": update}
    )
    return result.modified_count > 0


async def increment_user_stats(
    telegram_id: int,
    checked: int = 0,
    hits: int = 0,
    free: int = 0,
    bad: int = 0,
    sessions: int = 0,
    jobs: int = 0,
    session_mode: bool = False,
) -> None:
    db = get_db()
    inc: dict[str, int] = {}
    if checked:
        inc["total_checked"] = checked
        inc["session_checked"] = checked
    if hits:
        inc["total_hits"] = hits
        inc["session_hits"] = hits
    if free:
        inc["total_free"] = free
        inc["session_free"] = free
    if bad:
        inc["total_bad"] = bad
        inc["session_bad"] = bad
    if sessions:
        inc["total_sessions"] = sessions
    if jobs:
        inc["jobs_completed"] = jobs
    if inc:
        await db.users.update_one({"telegram_id": telegram_id}, {"$inc": inc})


async def reset_session_stats(telegram_id: int) -> None:
    await get_db().users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"session_checked": 0, "session_hits": 0, "session_free": 0, "session_bad": 0}},
    )


async def get_all_users(
    skip: int = 0, limit: int = 50, plan: str = "", banned: Optional[bool] = None
) -> tuple[list[dict[str, Any]], int]:
    query: dict[str, Any] = {}
    if plan:
        query["plan"] = plan
    if banned is not None:
        query["banned"] = banned
    db = get_db()
    total = await db.users.count_documents(query)
    cursor = db.users.find(query).sort("joined_at", DESCENDING).skip(skip).limit(limit)
    users = await cursor.to_list(length=limit)
    return users, total


async def get_user_count(plan: str = "") -> int:
    query: dict[str, Any] = {}
    if plan:
        query["plan"] = plan
    return await get_db().users.count_documents(query)


# ═══════════════════════════════════════════
# REDEEM KEY OPERATIONS
# ═══════════════════════════════════════════
async def create_redeem_keys(
    plan: str, count: int, days: int = 30
) -> list[str]:
    import secrets
    import string

    db = get_db()
    now = datetime.now(timezone.utc)
    keys = []
    docs = []
    for _ in range(count):
        key = "CR-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        keys.append(key)
        docs.append({
            "key": key,
            "plan": plan,
            "duration_days": days,
            "created_at": now,
            "expires_at": None,  # key itself doesn't expire unless set
            "used_by": None,
            "used_at": None,
            "used": False,
        })
    await db.redeem_keys.insert_many(docs)
    log.info("Created %d %s keys", count, plan)
    return keys


async def redeem_key(
    key_str: str, user_id: int
) -> tuple[bool, str]:
    """Attempt to redeem a key. Returns (success, message)."""
    db = get_db()
    key_doc = await db.redeem_keys.find_one({"key": key_str.strip().upper()})

    if not key_doc:
        return False, "Iɴᴠᴀʟɪᴅ ᴋᴇʏ. Pʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ."

    if key_doc["used"]:
        return False, "ᴋᴇʏ ᴀʟʀᴇᴀᴅʏ ʀᴇᴅᴇᴇᴍᴇᴅ ʙʏ ᴀɴᴏᴛʜᴇʀ ᴜsᴇʀ."

    if key_doc.get("used_by") == user_id:
        return False, "Yᴏᴜ ᴀʟʀᴇᴀᴅʏ ʀᴇᴅᴇᴇᴍᴇᴅ ᴛʜɪs ᴋᴇʏ."

    plan = key_doc["plan"]
    duration = key_doc["duration_days"]
    now = datetime.now(timezone.utc)
    expires = now + __import__("datetime").timedelta(days=duration)

    # Mark key as used
    await db.redeem_keys.update_one(
        {"key": key_doc["key"]},
        {"$set": {"used": True, "used_by": user_id, "used_at": now}},
    )

    # Update user plan
    await db.users.update_one(
        {"telegram_id": user_id},
        {"$set": {"plan": plan, "plan_set_at": now, "plan_expires_at": expires}},
    )

    log.info("User %d redeemed %s key, plan=%s, expires=%s", user_id, key_str, plan, expires)
    return True, f"Sᴜᴄᴄᴇss! Yᴏᴜ ɴᴏᴡ ʜᴀᴠᴇ <b>{config.PLANS[plan]['label']}</b> ᴘʟᴀɴ ғᴏʀ {duration} ᴅᴀʏs."


async def get_redeem_keys(
    skip: int = 0, limit: int = 50, plan: str = "", used: Optional[bool] = None
) -> tuple[list[dict[str, Any]], int]:
    query: dict[str, Any] = {}
    if plan:
        query["plan"] = plan
    if used is not None:
        query["used"] = used
    db = get_db()
    total = await db.redeem_keys.count_documents(query)
    cursor = db.redeem_keys.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
    return await cursor.to_list(length=limit), total


async def delete_redeem_key(key_str: str) -> bool:
    result = await get_db().redeem_keys.delete_one({"key": key_str.strip().upper()})
    return result.deleted_count > 0


# ═══════════════════════════════════════════
# PROXY OPERATIONS
# ═══════════════════════════════════════════
async def save_proxies(proxies: list[dict[str, Any]]) -> int:
    """Bulk upsert proxies. Returns count of new proxies added."""
    db = get_db()
    added = 0
    for p in proxies:
        result = await db.proxies.update_one(
            {"url": p["url"]},
            {"$set": p, "$setOnInsert": {"added_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        if result.upserted_id:
            added += 1
    return added


async def get_alive_proxies(limit: int = 0) -> list[dict[str, Any]]:
    query = {"alive": True}
    cursor = get_db().proxies.find(query).sort("latency_ms", ASCENDING)
    if limit:
        cursor = cursor.limit(limit)
    return await cursor.to_list(length=limit or 10000)


async def get_all_proxies(
    skip: int = 0, limit: int = 50, alive_only: bool = False
) -> tuple[list[dict[str, Any]], int]:
    query: dict[str, Any] = {}
    if alive_only:
        query["alive"] = True
    db = get_db()
    total = await db.proxies.count_documents(query)
    cursor = db.proxies.find(query).sort("last_checked", DESCENDING).skip(skip).limit(limit)
    return await cursor.to_list(length=limit), total


async def update_proxy_status(
    url: str,
    alive: bool,
    latency_ms: Optional[int] = None,
    error: str = "",
) -> None:
    update: dict[str, Any] = {
        "alive": alive,
        "last_checked": datetime.now(timezone.utc),
    }
    if latency_ms is not None:
        update["latency_ms"] = latency_ms
    if error:
        update["last_error"] = error
    if alive:
        update["fail_count"] = 0
    else:
        update["$inc"] = {"fail_count": 1}
    await get_db().proxies.update_one({"url": url}, {"$set": update, "$inc": {"fail_count": 1}})


async def get_proxy_count(alive_only: bool = False) -> int:
    query = {"alive": True} if alive_only else {}
    return await get_db().proxies.count_documents(query)


async def delete_all_proxies() -> int:
    result = await get_db().proxies.delete_many({})
    return result.deleted_count


async def delete_dead_proxies() -> int:
    result = await get_db().proxies.delete_many({"alive": False})
    return result.deleted_count


# ═══════════════════════════════════════════
# JOB OPERATIONS
# ═══════════════════════════════════════════
async def create_job(
    user_id: int,
    job_type: str,  # "single" | "bulk"
    total: int = 0,
) -> str:
    """Create a new job. Returns job_id."""
    import uuid
    db = get_db()
    job_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    await db.jobs.insert_one({
        "job_id": job_id,
        "user_id": user_id,
        "type": job_type,
        "status": "running",  # running | completed | cancelled | failed
        "total": total,
        "checked": 0,
        "hits": 0,
        "free": 0,
        "bad": 0,
        "retry": 0,
        "proxy_errors": 0,
        "speed": 0.0,
        "created_at": now,
        "started_at": now,
        "completed_at": None,
        "result_file": "",
    })
    return job_id


async def update_job(job_id: str, update: dict[str, Any]) -> bool:
    result = await get_db().jobs.update_one({"job_id": job_id}, {"$set": update})
    return result.modified_count > 0


async def increment_job_stats(
    job_id: str,
    checked: int = 0,
    hits: int = 0,
    free: int = 0,
    bad: int = 0,
    retry: int = 0,
    proxy_errors: int = 0,
) -> None:
    inc: dict[str, int] = {}
    if checked:
        inc["checked"] = checked
    if hits:
        inc["hits"] = hits
    if free:
        inc["free"] = free
    if bad:
        inc["bad"] = bad
    if retry:
        inc["retry"] = retry
    if proxy_errors:
        inc["proxy_errors"] = proxy_errors
    if inc:
        await get_db().jobs.update_one({"job_id": job_id}, {"$inc": inc})


async def get_job(job_id: str) -> Optional[dict[str, Any]]:
    return await get_db().jobs.find_one({"job_id": job_id})


async def get_user_active_job(user_id: int) -> Optional[dict[str, Any]]:
    return await get_db().jobs.find_one(
        {"user_id": user_id, "status": "running"}
    )


async def get_active_jobs() -> list[dict[str, Any]]:
    cursor = get_db().jobs.find({"status": "running"}).sort("created_at", ASCENDING)
    return await cursor.to_list(length=100)


async def get_recent_jobs(limit: int = 20) -> list[dict[str, Any]]:
    cursor = get_db().jobs.find({}).sort("created_at", DESCENDING).limit(limit)
    return await cursor.to_list(length=limit)


# ═══════════════════════════════════════════
# BOT CONFIG OPERATIONS
# ═══════════════════════════════════════════
CONFIG_DEFAULTS: dict[str, Any] = {
    "maintenance_mode": False,
    "verify_media": None,       # {"type": "photo"|"video", "file_id": "..."}
    "menu_media": None,
    "single_media": None,
    "welcome_message": "",
    "channels": [],
}


async def get_bot_config() -> dict[str, Any]:
    db = get_db()
    configs = {}
    cursor = db.bot_config.find({})
    async for doc in cursor:
        configs[doc["key"]] = doc.get("value")
    # Merge defaults
    for k, v in CONFIG_DEFAULTS.items():
        if k not in configs:
            configs[k] = v
    return configs


async def set_bot_config(key: str, value: Any) -> None:
    await get_db().bot_config.update_one(
        {"key": key},
        {"$set": {"value": value, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


# ═══════════════════════════════════════════
# STATS OPERATIONS
# ═══════════════════════════════════════════
async def record_daily_stats(
    date_str: str,
    user_id: int,
    checked: int = 0,
    hits: int = 0,
    free: int = 0,
    bad: int = 0,
) -> None:
    db = get_db()
    await db.stats.update_one(
        {"date": date_str, "user_id": user_id},
        {
            "$inc": {"checked": checked, "hits": hits, "free": free, "bad": bad},
            "$setOnInsert": {"updated_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )


async def get_global_stats() -> dict[str, Any]:
    db = get_db()
    total_users = await db.users.count_documents({"banned": False})
    banned_users = await db.users.count_documents({"banned": True})
    premium_users = await db.users.count_documents({"plan": "premium"})
    free_users = await db.users.count_documents({"plan": "free"})
    total_proxies = await db.proxies.count_documents({})
    alive_proxies = await db.proxies.count_documents({"alive": True})
    active_jobs = await db.jobs.count_documents({"status": "running"})
    total_jobs = await db.jobs.count_documents({})
    total_keys = await db.redeem_keys.count_documents({})
    used_keys = await db.redeem_keys.count_documents({"used": True})

    # Aggregate totals from users
    agg = await db.users.aggregate([
        {"$group": {
            "_id": None,
            "total_checked": {"$sum": "$total_checked"},
            "total_hits": {"$sum": "$total_hits"},
            "total_free": {"$sum": "$total_free"},
            "total_bad": {"$sum": "$total_bad"},
        }}
    ]).to_list(length=1)
    agg = agg[0] if agg else {}

    return {
        "total_users": total_users,
        "banned_users": banned_users,
        "premium_users": premium_users,
        "free_users": free_users,
        "total_proxies": total_proxies,
        "alive_proxies": alive_proxies,
        "active_jobs": active_jobs,
        "total_jobs": total_jobs,
        "total_keys": total_keys,
        "used_keys": used_keys,
        "available_keys": total_keys - used_keys,
        "total_checked": agg.get("total_checked", 0),
        "total_hits": agg.get("total_hits", 0),
        "total_free": agg.get("total_free", 0),
        "total_bad": agg.get("total_bad", 0),
    }
