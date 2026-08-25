"""
Admin command handler.
All admin commands are protected by ADMIN_IDS check.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
import db.database as db
from services import plan_service, key_service
from utils.formatting import (
    admin_stats_msg,
    error_msg,
    success_msg,
    fancy,
    dev_footer,
    fmt_num,
)

log = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ═══════════════════════════════════════════
# /admin – Main Admin Panel
# ═══════════════════════════════════════════
async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return

    keyboard = [
        [InlineKeyboardButton("⟡ Stats", callback_data="admin_stats"),
         InlineKeyboardButton("⟡ Users", callback_data="admin_users")],
        [InlineKeyboardButton("⟡ Plans", callback_data="admin_plans"),
         InlineKeyboardButton("⟡ Keys", callback_data="admin_keys")],
        [InlineKeyboardButton("⟡ Jobs", callback_data="admin_jobs"),
         InlineKeyboardButton("⟡ Proxies", callback_data="proxy_menu")],
        [InlineKeyboardButton("⟡ Broadcast", callback_data="admin_broadcast_prompt"),
         InlineKeyboardButton("⟡ Maintenance", callback_data="admin_maintenance_toggle")],
        [InlineKeyboardButton("⟡ Config", callback_data="admin_config_menu")],
    ]
    text = (
        f"╭─ ⟡ {fancy('Admin Panel')}\n"
        f"├─ Sᴇʟᴇᴄᴛ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ.\n"
        f"{dev_footer()}"
    )
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════
async def _admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    stats = await db.get_global_stats()
    text = admin_stats_msg(stats)
    keyboard = [[InlineKeyboardButton("⟡ Back", callback_data="admin_panel")]]
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════
# Users
# ═══════════════════════════════════════════
async def _admin_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    # Parse page from callback data
    data = query.data
    page = 0
    if "page_" in data:
        try:
            page = int(data.split("page_")[-1])
        except ValueError:
            page = 0

    users, total = await db.get_all_users(skip=page * 10, limit=10)
    if not users:
        await query.edit_message_text(error_msg("Eᴍᴘᴛʏ", "Nᴏ ᴜsᴇʀs."), parse_mode="HTML")
        return

    lines = [f"╭─ ⟡ {fancy(f'Users ({total} total)')}\n"]
    for u in users:
        tid = u.get("telegram_id", 0)
        name = u.get("first_name") or u.get("username") or "Unknown"
        uname = f"@{u.get('username')}" if u.get("username") else name
        plan = u.get("plan", "free")
        banned = "BAN" if u.get("banned") else ""
        checked = fmt_num(u.get("total_checked", 0))
        hits = fmt_num(u.get("total_hits", 0))
        lines.append(
            f"├─ <a href=\"tg://user?id={tid}\">{uname}</a> "
            f"({plan}) {banned}\n"
            f"│  ├─ Checked: {checked} | Hits: {hits}\n"
        )
    lines.append(f"{dev_footer()}")

    # Pagination
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◄", callback_data=f"admin_users_page_{page-1}"))
    if (page + 1) * 10 < total:
        nav.append(InlineKeyboardButton("►", callback_data=f"admin_users_page_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("⟡ Back", callback_data="admin_panel")])

    await query.edit_message_text(
        "".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
    )


# ═══════════════════════════════════════════
# Ban / Unban
# ═══════════════════════════════════════════
async def ban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            error_msg("Usᴀɢᴇ", "/ban <code>&lt;user_id&gt;</code>"), parse_mode="HTML"
        )
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", "Iɴᴠᴀʟɪᴅ ᴜsᴇʀ ID."), parse_mode="HTML")
        return
    if target_id in config.ADMIN_IDS:
        await update.message.reply_text(error_msg("Dᴇɴɪᴇᴅ", "Cᴀɴɴᴏᴛ ʙᴀɴ ᴀᴅᴍɪɴ."), parse_mode="HTML")
        return
    await db.update_user(target_id, {"banned": True})
    await update.message.reply_text(success_msg("Bᴀɴɴᴇᴅ", f"Usᴇʀ {target_id} ʙᴀɴɴᴇᴅ."), parse_mode="HTML")


async def unban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            error_msg("Usᴀɢᴇ", "/unban <code>&lt;user_id&gt;</code>"), parse_mode="HTML"
        )
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", "Iɴᴠᴀʟɪᴅ ᴜsᴇʀ ID."), parse_mode="HTML")
        return
    await db.update_user(target_id, {"banned": False})
    await update.message.reply_text(success_msg("Uɴʙᴀɴɴᴇᴅ", f"Usᴇʀ {target_id} ᴜɴʙᴀɴɴᴇᴅ."), parse_mode="HTML")


# ═══════════════════════════════════════════
# Set Plan
# ═══════════════════════════════════════════
async def setplan_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return
    if len(ctx.args) < 2:
        await update.message.reply_text(
            error_msg("Usᴀɢᴇ", "/setplan <code>&lt;user_id&gt; &lt;plan&gt; [days]</code>"), parse_mode="HTML"
        )
        return
    try:
        target_id = int(ctx.args[0])
        plan = ctx.args[1].lower()
        days = int(ctx.args[2]) if len(ctx.args) > 2 else 30
    except ValueError:
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", "Iɴᴠᴀʟɪᴅ ᴀʀɢᴜᴍᴇɴᴛs."), parse_mode="HTML")
        return
    if plan not in config.PLANS:
        await update.message.reply_text(
            error_msg("Iɴᴠᴀʟɪᴅ", f"Pʟᴀɴs: {', '.join(config.PLANS)}"), parse_mode="HTML"
        )
        return
    await plan_service.set_user_plan(target_id, plan, days)
    await update.message.reply_text(
        success_msg("Dᴏɴᴇ", f"Usᴇʀ {target_id} → {plan} ғᴏʀ {days} ᴅᴀʏs."), parse_mode="HTML"
    )


# ═══════════════════════════════════════════
# Keys
# ═══════════════════════════════════════════
async def _admin_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⟡ Generate", callback_data="admin_keys_gen")],
        [InlineKeyboardButton("⟡ View Keys", callback_data="admin_keys_view")],
        [InlineKeyboardButton("⟡ Back", callback_data="admin_panel")],
    ]
    text = f"╭─ ⟡ {fancy('Key Management')}\n{dev_footer()}"
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _keys_gen_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        f"╭─ ⟡ {fancy('Generate Keys')}\n"
        f"├─ Usᴇ: /addkey <code>&lt;plan&gt; &lt;count&gt; [days]</code>\n"
        f"├─ Ex: /addkey premium 5 30\n"
        f"├─ Ex: /addkey premium 10\n"
        f"{dev_footer()}"
    )
    keyboard = [[InlineKeyboardButton("⟡ Back", callback_data="admin_keys")]]
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def addkey_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return
    if len(ctx.args) < 2:
        await update.message.reply_text(
            error_msg("Usᴀɢᴇ", "/addkey <code>&lt;plan&gt; &lt;count&gt; [days]</code>"),
            parse_mode="HTML",
        )
        return
    plan = ctx.args[0].lower()
    try:
        count = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", "Cᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ."), parse_mode="HTML")
        return
    if plan not in config.PLANS:
        await update.message.reply_text(
            error_msg("Iɴᴠᴀʟɪᴅ", f"Pʟᴀɴs: {', '.join(config.PLANS)}"), parse_mode="HTML"
        )
        return
    days = int(ctx.args[2]) if len(ctx.args) > 2 else 30
    if count > 100:
        count = 100
    keys = await key_service.generate_keys(plan, count, days)
    keys_text = "\n".join(keys)
    await update.message.reply_text(
        f"╭─ ✓ {fancy(f'{count} Keys Generated')}\n"
        f"├─ Pʟᴀɴ: {plan} | Dᴜʀᴀᴛɪᴏɴ: {days}ᴅ\n"
        f"├─ <code>{keys_text}</code>\n"
        f"{dev_footer()}",
        parse_mode="HTML",
    )


async def delkey_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            error_msg("Usᴀɢᴇ", "/delkey <code>&lt;key&gt;</code>"), parse_mode="HTML"
        )
        return
    key_str = ctx.args[0]
    removed = await key_service.remove_key(key_str)
    if removed:
        await update.message.reply_text(success_msg("Dᴇʟᴇᴛᴇᴅ", f"Kᴇʏ {key_str} ᴅᴇʟᴇᴛᴇᴅ."), parse_mode="HTML")
    else:
        await update.message.reply_text(error_msg("Nᴏᴛ Fᴏᴜɴᴅ", f"Kᴇʏ {key_str} ɴᴏᴛ ғᴏᴜɴᴅ."), parse_mode="HTML")


async def _keys_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keys, total = await key_service.list_keys(skip=0, limit=15)
    if not keys:
        text = error_msg("Eᴍᴘᴛʏ", "Nᴏ ᴋᴇʏs.")
    else:
        lines = [f"╭─ ⟡ {fancy(f'Keys ({total} total)')}\n"]
        for k in keys:
            status = "✓ Used" if k["used"] else "○ Available"
            user = k.get("used_by", "")
            lines.append(f"├─ <code>{k['key']}</code> | {k['plan']} | {status}\n")
        lines.append(dev_footer())
        text = "".join(lines)
    keyboard = [[InlineKeyboardButton("⟡ Back", callback_data="admin_keys")]]
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════
# Jobs
# ═══════════════════════════════════════════
async def _admin_jobs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    jobs = await db.get_active_jobs()
    recent = await db.get_recent_jobs(limit=10)

    lines = [f"╭─ ⟡ {fancy('Jobs')}\n"]
    if jobs:
        lines.append(f"├─ ═══ {fancy('Active')} ═══\n")
        for j in jobs:
            lines.append(
                f"├─ <code>{j['job_id']}</code> | U:{j['user_id']} | "
                f"{j.get('checked',0)}/{j.get('total',0)}\n"
            )
    if recent:
        lines.append(f"├─ ═══ {fancy('Recent')} ═══\n")
        for j in recent[:5]:
            if j["job_id"] not in [j2["job_id"] for j2 in jobs]:
                status = j.get("status", "?")
                lines.append(
                    f"├─ <code>{j['job_id']}</code> | {status} | "
                    f"{j.get('checked',0)}/{j.get('total',0)} | H:{j.get('hits',0)}\n"
                )
    lines.append(dev_footer())
    keyboard = [[InlineKeyboardButton("⟡ Back", callback_data="admin_panel")]]
    await query.edit_message_text(
        "".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════
# Maintenance Mode
# ═══════════════════════════════════════════
async def _maintenance_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    bot_cfg = ctx.bot_data.get("bot_config") or await db.get_bot_config()
    current = bot_cfg.get("maintenance_mode", False)
    new_val = not current
    await db.set_bot_config("maintenance_mode", new_val)
    ctx.bot_data["bot_config"]["maintenance_mode"] = new_val

    state = "ON" if new_val else "OFF"
    await query.edit_message_text(
        success_msg("Mᴀɪɴᴛᴇɴᴀɴᴄᴇ", f"Mᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ: <b>{state}</b>"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⟡ Back", callback_data="admin_panel")]
        ]),
    )


# ═══════════════════════════════════════════
# Broadcast
# ═══════════════════════════════════════════
async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return
    if not ctx.args:
        await update.message.reply_text(
            error_msg("Usᴀɢᴇ", "/broadcast <code>&lt;message&gt;</code>"), parse_mode="HTML"
        )
        return
    msg = " ".join(ctx.args)[:4096]
    cursor = db.get_db().users.find({"banned": False})
    sent = 0
    failed = 0
    async for u_doc in cursor:
        try:
            await ctx.bot.send_message(chat_id=u_doc["telegram_id"], text=msg)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        success_msg("Bʀᴏᴀᴅᴄᴀsᴛ", f"Sᴇɴᴛ: {sent} | Fᴀɪʟᴇᴅ: {failed}"), parse_mode="HTML"
    )


# ═══════════════════════════════════════════
# Config
# ═══════════════════════════════════════════
async def _admin_config_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⟡ Set Verify Media", callback_data="admin_set_verify_media")],
        [InlineKeyboardButton("⟡ Set Menu Media", callback_data="admin_set_menu_media")],
        [InlineKeyboardButton("⟡ Set Single Media", callback_data="admin_set_single_media")],
        [InlineKeyboardButton("⟡ Back", callback_data="admin_panel")],
    ]
    text = (
        f"╭─ ⟡ {fancy('Configuration')}\n"
        f"├─ Sᴇʟᴇᴄᴛ ᴡʜᴀᴛ ᴛᴏ ᴄᴏɴғɪɢᴜʀᴇ.\n"
        f"├─ Mᴇᴅɪᴀ: sᴇɴᴅ /verify, /menu_media, /single\n"
        f"│  ᴛʜᴇɴ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ/ᴠɪᴅᴇᴏ.\n"
        f"{dev_footer()}"
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════
# CALLBACK ROUTER
# ═══════════════════════════════════════════
async def admin_callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Route admin callback queries."""
    query = update.callback_query
    if not query or not _is_admin(query.from_user.id):
        await query.answer("Nᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.", show_alert=True)
        return

    data = query.data
    handlers_map = {
        "admin_panel": admin_cmd,
        "admin_stats": _admin_stats,
        "admin_users": _admin_users,
        "admin_users_page_0": _admin_users,
        "admin_plans": _admin_keys,
        "admin_keys": _admin_keys,
        "admin_keys_gen": _keys_gen_prompt,
        "admin_keys_view": _keys_view,
        "admin_jobs": _admin_jobs,
        "admin_maintenance_toggle": _maintenance_toggle,
        "admin_broadcast_prompt": _keys_gen_prompt,  # reuse prompt pattern
        "admin_config_menu": _admin_config_menu,
    }
    # Handle pagination
    if data.startswith("admin_users_page_"):
        await _admin_users(update, ctx)
        return

    handler = handlers_map.get(data)
    if handler:
        await handler(update, ctx)
    else:
        await query.answer("Uɴᴋɴᴏᴡɴ ᴀᴄᴛɪᴏɴ.")


def _is_admin_callback(data: str) -> bool:
    return data.startswith("admin_") or data == "proxy_menu" or data.startswith("proxy_")
