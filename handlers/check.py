"""Single account check handler."""

import asyncio
import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import config
import db.database as db
from core import checker
from core.proxy import ProxyManager
from services.plan_service import check_concurrent_jobs
from utils.formatting import hit_message, error_msg, success_msg, fancy, dev_footer
from utils.validators import is_valid_email

log = logging.getLogger(__name__)

WAITING_EMAIL = 0
WAITING_PASS = 1


async def check_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /check – start single check flow."""
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    user_doc = await db.get_user(user.id)
    if not user_doc or user_doc.get("banned"):
        return ConversationHandler.END

    # Check active job
    ok, msg = await check_concurrent_jobs(user.id)
    if not ok:
        await update.message.reply_text(error_msg("Jᴏʙ Aᴄᴛɪᴠᴇ", msg), parse_mode="HTML")
        return ConversationHandler.END

    # Check if user passed email:pass directly
    text = update.message.text.strip()
    if "/check " in text:
        text = text.replace("/check", "", 1).strip()

    if ":" in text and is_valid_email(text.split(":")[0]):
        parts = text.split(":", 1)
        ctx.user_data["check_email"] = parts[0]
        ctx.user_data["check_pass"] = parts[1]
        return await _do_single_check(update, ctx)

    text = (
        f"╭─ ⟡ {fancy('Single Check')}\n"
        f"├─ Sᴇɴᴅ ᴛʜᴇ ᴇᴍᴀɪʟ ᴀᴅᴅʀᴇss ᴛᴏ ᴄʜᴇᴄᴋ:\n"
        f"├─ /cancel ᴛᴏ ᴀʙᴏʀᴛ\n"
        f"{dev_footer()}"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    return WAITING_EMAIL


async def _email_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if not is_valid_email(email):
        await update.message.reply_text(
            error_msg("Iɴᴠᴀʟɪᴅ", "Pʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ᴇᴍᴀɪʟ."),
            parse_mode="HTML",
        )
        return WAITING_EMAIL

    ctx.user_data["check_email"] = email
    text = (
        f"╭─ ⟡ {fancy('Password')}\n"
        f"├─ Nᴏᴡ sᴇɴᴅ ᴛʜᴇ ᴘᴀssᴡᴏʀᴅ:\n"
        f"├─ /cancel ᴛᴏ ᴀʙᴏʀᴛ\n"
        f"{dev_footer()}"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    return WAITING_PASS


async def _pass_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["check_pass"] = update.message.text.strip()
    return await _do_single_check(update, ctx)


async def _do_single_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute the single check."""
    email = ctx.user_data.get("check_email", "")
    password = ctx.user_data.get("check_pass", "")
    if not email or not password:
        await update.message.reply_text(error_msg("Mɪssɪɴɢ", "Nᴏ ᴇᴍᴀɪʟ ᴏʀ ᴘᴀssᴡᴏʀᴅ."), parse_mode="HTML")
        return ConversationHandler.END

    user = update.effective_user
    text = (
        f"╭─ ⟡ {fancy('Checking')}\n"
        f"├─ ▸ <code>{email}</code>\n"
        f"├─ Pʟᴇᴀsᴇ ᴡᴀɪᴛ...\n"
        f"{dev_footer()}"
    )
    status_msg = await update.message.reply_text(text, parse_mode="HTML")

    # Get proxy
    proxy_url = None
    proxy_mgr = ctx.bot_data.get("proxy_manager")
    if proxy_mgr and len(proxy_mgr) > 0:
        proxy_url = await proxy_mgr.get_random()

    try:
        result_status, detail, info = await checker.crunchy_check(email, password, proxy_url)
    except Exception as exc:
        await status_msg.edit_text(error_msg("Eʀʀᴏʀ", str(exc)[:200]), parse_mode="HTML")
        return ConversationHandler.END

    # Update stats
    plan = (await db.get_user(user.id) or {}).get("plan", "free")
    checker_name = user.first_name or user.username or "Unknown"

    if result_status == "HIT":
        text = hit_message(email, password, info, checker_name, user.id, plan)
        await db.increment_user_stats(user.id, checked=1, hits=1, sessions=1, jobs=1)

        bot_cfg = ctx.bot_data.get("bot_config") or await db.get_bot_config()
        single_media = bot_cfg.get("single_media")

        if single_media and single_media.get("type") == "photo" and single_media.get("file_id"):
            await status_msg.delete()
            await update.message.reply_photo(
                photo=single_media["file_id"], caption=text, parse_mode="HTML"
            )
        elif single_media and single_media.get("type") == "video" and single_media.get("file_id"):
            await status_msg.delete()
            await update.message.reply_video(
                video=single_media["file_id"], caption=text, parse_mode="HTML"
            )
        else:
            await status_msg.edit_text(text, parse_mode="HTML")

    elif result_status == "FREE":
        uname = info.get("user", "?")
        await db.increment_user_stats(user.id, checked=1, free=1, sessions=1, jobs=1)
        text = (
            f"╭─ ○ {fancy('Free Account')}\n"
            f"├─ ▸ <b>{fancy('Email')}</b>: <code>{email}</code>\n"
            f"├─ ▸ <b>{fancy('User')}</b>: {uname}\n"
            f"├─ ▸ <b>{fancy('Verified')}</b>: {info.get('verified', '?')}\n"
            f"{dev_footer()}"
        )
        await status_msg.edit_text(text, parse_mode="HTML")
    elif result_status == "BAD":
        await db.increment_user_stats(user.id, checked=1, bad=1, sessions=1, jobs=1)
        await status_msg.edit_text(
            error_msg("Bᴀᴅ", f"<code>{email}</code> – ɪɴᴠᴀʟɪᴅ ᴄʀᴇᴅᴇɴᴛɪᴀʟs."),
            parse_mode="HTML",
        )
    else:
        await db.increment_user_stats(user.id, checked=1, sessions=1, jobs=1)
        await status_msg.edit_text(
            error_msg("Rᴇᴛʀʏ", f"<code>{email}</code> – {detail or 'ᴜɴᴋɴᴏᴡɴ ᴇʀʀᴏʀ'}"),
            parse_mode="HTML",
        )

    return ConversationHandler.END


async def _cancel_conv(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cᴀɴᴄᴇʟʟᴇᴅ.", parse_mode="HTML")
    return ConversationHandler.END


# Conversation handler for single check
single_check_conv = ConversationHandler(
    entry_points=[check_cmd],
    states={
        WAITING_EMAIL: [_email_received],
        WAITING_PASS: [_pass_received],
    },
    fallbacks=[_cancel_conv],
)
