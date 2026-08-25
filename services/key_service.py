import logging
from typing import Any, Optional

import db.database as db

log = logging.getLogger(__name__)


async def generate_keys(plan: str, count: int, days: int = 30) -> list[str]:
    """Generate redeem keys and store in DB."""
    return await db.create_redeem_keys(plan, count, days)


async def redeem_key_for_user(key_str: str, user_id: int) -> tuple[bool, str]:
    """Redeem a key for a user. Returns (success, message)."""
    return await db.redeem_key(key_str, user_id)


async def list_keys(
    skip: int = 0, limit: int = 20, plan: str = "", used: Optional[bool] = None
) -> tuple[list[dict[str, Any]], int]:
    return await db.get_redeem_keys(skip, limit, plan, used)


async def remove_key(key_str: str) -> bool:
    return await db.delete_redeem_key(key_str)
