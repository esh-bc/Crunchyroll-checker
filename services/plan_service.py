"""Plan management service."""

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import config
import db.database as db


async def get_user_plan_info(telegram_id: int) -> dict[str, Any]:
    """Get enriched plan info for a user."""
    user = await db.get_user(telegram_id)
    if not user:
        return {"plan": "free", "label": config.PLANS["free"]["label"], "expires": None}

    plan = user.get("plan", "free")
    plan_cfg = config.PLANS.get(plan, config.PLANS["free"])
    expires_at = user.get("plan_expires_at")

    # Check if plan expired
    if plan != "free" and expires_at:
        try:
            if isinstance(expires_at, str):
                exp = datetime.fromisoformat(expires_at)
            else:
                exp = expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                # Plan expired, revert to free
                await db.update_user(telegram_id, {
                    "plan": "free",
                    "plan_set_at": None,
                    "plan_expires_at": None,
                })
                plan = "free"
                plan_cfg = config.PLANS["free"]
                expires_at = None
        except Exception:
            pass

    return {
        "plan": plan,
        "label": plan_cfg["label"],
        "expires": expires_at,
        "max_combo": plan_cfg["max_combo"],
        "max_concurrent_jobs": plan_cfg["max_concurrent_jobs"],
        "speed_limit": plan_cfg["speed_limit"],
    }


async def check_plan_limit(user_id: int, combo_count: int) -> tuple[bool, str]:
    """Check if the user can start a job with this many combos."""
    plan_info = await get_user_plan_info(user_id)
    max_combo = plan_info["max_combo"]

    if combo_count > max_combo:
        return False, (
            f"Cᴏᴍʙᴏ ᴄᴏᴜɴᴛ ({combo_count:,}) ᴇxᴄᴇᴇᴅs ʏᴏᴜʀ {plan_info['label']} "
            f"ʟɪᴍɪᴛ ({max_combo:,}). Uᴘɢʀᴀᴅᴇ ᴡɪᴛʜ /redeem."
        )
    return True, ""


async def check_concurrent_jobs(user_id: int) -> tuple[bool, str]:
    """Check if user can start another job."""
    plan_info = await get_user_plan_info(user_id)
    max_jobs = plan_info["max_concurrent_jobs"]
    active = await db.get_user_active_job(user_id)
    if active:
        return False, "Yᴏᴜ ᴀʟʀᴇᴀᴅʏ ʜᴀᴠᴇ ᴀ ʀᴜɴɴɪɴɢ ᴊᴏʙ. Usᴇ /cancel ᴛᴏ sᴛᴏᴘ ɪᴛ."
    return True, ""


async def set_user_plan(user_id: int, plan: str, days: int = 30) -> None:
    """Admin: directly set a user's plan."""
    if plan not in config.PLANS:
        plan = "free"
    if plan == "free":
        await db.update_user(user_id, {
            "plan": "free",
            "plan_set_at": None,
            "plan_expires_at": None,
        })
    else:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=days)
        await db.update_user(user_id, {
            "plan": plan,
            "plan_set_at": now,
            "plan_expires_at": expires,
        })
