"""Proxy management handler – upload, test, view, clear proxies."""

import time
import asyncio
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
import config
import db.database as db
from core.proxy import ProxyManager, parse_proxy_file, validate_proxies_bulk
from utils.formatting import (
    proxy_test_progress_msg,
    error_msg,
    success_msg,
    fancy,
    dev_footer,
    fmt_num,
    pct,
    progress_bar,
)
from utils.validators import validate_upload, validate_proxy_line

log = logging.getLogger(__name__)

PROXY_WAIT_FILE = 0
PROXY_WAIT_TEXT = 1
PROXY_WAIT_DELETE_CONFIRM = 2


async def proxies_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /proxies – show proxy management menu."""
    user = update.effective_user
    if not user or user.id not in config.ADMIN_IDS:
        # Non-admin sees proxy count only
        pm = ctx.bot_data.get("proxy_manager")
        count = len(pm) if pm else 0
        alive = pm.alive_count if pm else 0
        await update.message.reply_text(
            f"╭─ ⟡ {fancy('Proxy Status')}\n"
            f"├─ ▸ <b>{fancy('Loaded')}</b>: {fmt_num(count)}\n"
            f"├─ ▸ <b>{fancy('Alive')}</b>: {fmt_num(alive)}\n"
            f"{dev_footer()}",
            parse_mode="HTML",
        )
        return

    pm = ctx.bot_data.get("proxy_manager")
    count = len(pm) if pm else 0
    alive = pm.alive_count if pm else 0

    keyboard = [
        [
            InlineKeyboardButton("⇢ Upload File", callback_data="proxy_upload"),
            InlineKeyboardButton("⇢ Paste Text", callback_data="proxy_paste"),
        ],
        [
            InlineKeyboardButton("⇢ Test All", callback_data="proxy_test"),
            InlineKeyboardButton("⇢ View Stats", callback_data="proxy_stats"),
        ],
        [
            InlineKeyboardButton("⇢ Clear Dead", callback_data="proxy_clear_dead"),
            InlineKeyboardButton("⇢ Clear All", callback_data="proxy_clear_all"),
        ],
        [InlineKeyboardButton("⟡ Back to Menu", callback_data="back_menu")],
    ]
    text = (
        f"╭─ ⟡ {fancy('Proxy Management')}\n"
        f"├─ ▸ <b>{fancy('Total')}</b>: {fmt_num(count)}\n"
        f"├─ ▸ <b>{fancy('Alive')}</b>: {fmt_num(alive)}\n"
        f"├─ ▸ <b>{fancy('Dead')}</b>: {fmt_num(count - alive)}\n"
        f"{dev_footer()}"
    )
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _upload_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        f"╭─ ⟡ {fancy('Upload Proxies')}\n"
        f"├─ Sᴇɴᴅ ᴀ <code>.txt</code> ғɪʟᴇ ᴡɪᴛʜ ᴘʀᴏxɪᴇs.\n"
        f"├─ Sᴜᴘᴘᴏʀᴛᴇᴅ ғᴏʀᴍᴀᴛs:\n"
        f"│  ├─ IP:PORT\n"
        f"│  ├─ IP:PORT:USER:PASS\n"
        f"│  ├─ http://IP:PORT\n"
        f"│  ├─ socks5://IP:PORT\n"
        f"│  └─ http://USER:PASS@IP:PORT\n"
        f"├─ /cancel ᴛᴏ ᴀʙᴏʀᴛ\n"
        f"{dev_footer()}",
        parse_mode="HTML",
    )
    return PROXY_WAIT_FILE


async def _file_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.document:
        await update.message.reply_text(error_msg("Eʀʀᴏʀ", "Sᴇɴᴅ ᴀ ғɪʟᴇ."), parse_mode="HTML")
        return PROXY_WAIT_FILE

    doc = update.message.document
    ext = Path(doc.file_name or "").suffix.lower()
    if ext not in (".txt", ".csv"):
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", ".txt ᴏɴʟʏ."), parse_mode="HTML")
        return PROXY_WAIT_FILE

    status = await update.message.reply_text(f"Pʀᴏᴄᴇssɪɴɢ...", parse_mode="HTML")

    try:
        file = await doc.get_file()
        tmp = config.TMP_DIR / f"proxy_{int(time.time())}.txt"
        await file.download_to_drive(str(tmp))
        content = tmp.read_text(encoding="utf-8", errors="ignore")
        tmp.unlink(missing_ok=True)
    except Exception as exc:
        await status.edit_text(error_msg("Eʀʀᴏʀ", str(exc)[:200]), parse_mode="HTML")
        return ConversationHandler.END

    await _process_proxy_text(content, status, ctx)
    return ConversationHandler.END


async def _paste_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        f"╭─ ⟡ {fancy('Paste Proxies')}\n"
        f"├─ Pᴀsᴛᴇ ᴘʀᴏxɪᴇs (ᴏɴᴇ ᴘᴇʀ ʟɪɴᴇ).\n"
        f"├─ /cancel ᴏʀ /done ᴛᴏ ғɪɴɪsʜ.\n"
        f"{dev_footer()}",
        parse_mode="HTML",
    )
    ctx.user_data["proxy_lines"] = []
    return PROXY_WAIT_TEXT


async def _text_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "/done":
        lines = ctx.user_data.get("proxy_lines", [])
        content = "\n".join(lines)
        await _process_proxy_text(content, update.message, ctx)
        return ConversationHandler.END

    if text == "/cancel":
        await update.message.reply_text("Cᴀɴᴄᴇʟʟᴇᴅ.", parse_mode="HTML")
        return ConversationHandler.END

    lines = text.splitlines()
    added = 0
    for line in lines:
        if validate_proxy_line(line):
            ctx.user_data.setdefault("proxy_lines", []).append(line.strip())
            added += 1

    await update.message.reply_text(f"+ {added} ᴘʀᴏxɪᴇs ᴀᴅᴅᴇᴅ. /done ᴛᴏ ғɪɴɪsʜ.", parse_mode="HTML")
    return PROXY_WAIT_TEXT


async def _process_proxy_text(content: str, status_msg, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Parse and store proxies from text content."""
    proxies = parse_proxy_file(content)
    if not proxies:
        await status_msg.reply_text(error_msg("Eᴍᴘᴛʏ", "Nᴏ ᴠᴀʟɪᴅ ᴘʀᴏxɪᴇs ғᴏᴜɴᴅ."), parse_mode="HTML")
        return

    # Save to DB
    added = await db.save_proxies(proxies)

    # Update in-memory proxy manager
    alive_proxies = await db.get_alive_proxies()
    pm = ctx.bot_data.get("proxy_manager") or ProxyManager()
    pm.load(alive_proxies)
    ctx.bot_data["proxy_manager"] = pm

    await status_msg.reply_text(
        success_msg(
            "Pʀᴏxɪᴇs Lᴏᴀᴅᴇᴅ",
            f"Pᴀʀsᴇᴅ: {fmt_num(len(proxies))} | Nᴇᴡ: {fmt_num(added)} | Aʟɪᴠᴇ: {fmt_num(pm.alive_count)}",
        ),
        parse_mode="HTML",
    )


async def _test_proxies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Test all proxies (admin callback)."""
    query = update.callback_query
    await query.answer()

    all_proxies = await db.get_all_proxies(limit=10000, alive_only=False)
    urls = [p["url"] for p in all_proxies[0]]
    if not urls:
        await query.edit_message_text(
            error_msg("Nᴏ Pʀᴏxɪᴇs", "Nᴏ ᴛᴇsᴛᴇᴅ ᴘʀᴏxɪᴇs ɪɴ ᴅᴀᴛᴀʙᴀsᴇ."), parse_mode="HTML"
        )
        return

    progress_msg = await query.edit_message_text(
        proxy_test_progress_msg(0, 0, len(urls), 0), parse_mode="HTML"
    )

    last_edit = [0.0]

    def on_progress(alive, dead, total, current):
        now = time.monotonic()
        if now - last_edit[0] < 2.0:
            return
        last_edit[0] = now

        async def _edit():
            try:
                await progress_msg.edit_text(
                    proxy_test_progress_msg(alive, dead, total, current),
                    parse_mode="HTML",
                )
            except Exception:
                pass

        asyncio.create_task(_edit())

    results, alive, dead = await validate_proxies_bulk(urls, on_progress=on_progress)

    # Update DB
    for r in results:
        await db.update_proxy_status(
            r["url"], r["alive"], r.get("latency_ms"), r.get("error", "")
        )

    # Reload proxy manager
    alive_proxies = await db.get_alive_proxies()
    pm = ctx.bot_data.get("proxy_manager") or ProxyManager()
    pm.load(alive_proxies)
    ctx.bot_data["proxy_manager"] = pm

    avg_latency = 0
    latencies = [r["latency_ms"] for r in results if r["alive"] and r.get("latency_ms")]
    if latencies:
        avg_latency = sum(latencies) // len(latencies)

    text = (
        f"╭─ ✓ {fancy('Proxy Test Complete')}\n"
        f"├─ ▸ <b>{fancy('Total')}</b>: {fmt_num(len(urls))}\n"
        f"├─ ✓ <b>{fancy('Alive')}</b>: {fmt_num(alive)}\n"
        f"├─ ✕ <b>{fancy('Dead')}</b>: {fmt_num(dead)}\n"
        f"├─ ▸ <b>{fancy('Avg Latency')}</b>: {avg_latency}ms\n"
        f"{dev_footer()}"
    )
    await progress_msg.edit_text(text, parse_mode="HTML")


async def _proxy_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show proxy stats (callback)."""
    query = update.callback_query
    await query.answer()
    pm = ctx.bot_data.get("proxy_manager")
    count = len(pm) if pm else 0
    alive = pm.alive_count if pm else 0
    await query.edit_message_text(
        f"╭─ ⟡ {fancy('Proxy Stats')}\n"
        f"├─ ▸ <b>{fancy('In Memory')}</b>: {fmt_num(count)}\n"
        f"├─ ▸ <b>{fancy('Alive')}</b>: {fmt_num(alive)}\n"
        f"├─ ▸ <b>{fancy('Dead')}</b>: {fmt_num(count - alive)}\n"
        f"{dev_footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⟡ Back", callback_data="proxy_menu")],
        ]),
    )


async def _clear_dead(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    removed = await db.delete_dead_proxies()
    alive_proxies = await db.get_alive_proxies()
    pm = ctx.bot_data.get("proxy_manager") or ProxyManager()
    pm.load(alive_proxies)
    ctx.bot_data["proxy_manager"] = pm
    await query.edit_message_text(
        success_msg("Cʟᴇᴀɴᴇᴅ", f"Rᴇᴍᴏᴠᴇᴅ {fmt_num(removed)} ᴅᴇᴀᴅ ᴘʀᴏxɪᴇs."),
        parse_mode="HTML",
    )


async def _clear_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    removed = await db.delete_all_proxies()
    pm = ctx.bot_data.get("proxy_manager")
    if pm:
        pm.clear()
    await query.edit_message_text(
        success_msg("Cʟᴇᴀɴᴇᴅ", f"Rᴇᴍᴏᴠᴇᴅ {fmt_num(removed)} ᴘʀᴏxɪᴇs."),
        parse_mode="HTML",
    )


# Callback router for proxy operations
async def proxy_callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "proxy_upload":
        await _upload_entry(update, ctx)
    elif data == "proxy_paste":
        await _paste_entry(update, ctx)
    elif data == "proxy_test":
        await _test_proxies(update, ctx)
    elif data == "proxy_stats":
        await _proxy_stats(update, ctx)
    elif data == "proxy_clear_dead":
        await _clear_dead(update, ctx)
    elif data == "proxy_clear_all":
        await _clear_all(update, ctx)


proxy_upload_conv = ConversationHandler(
    entry_points=[],
    states={
        PROXY_WAIT_FILE: [_file_received],
        PROXY_WAIT_TEXT: [_text_received],
    },
    fallbacks=[
        lambda u, c: (u.message.reply_text("Cᴀɴᴄᴇʟʟᴇᴅ.", parse_mode="HTML"), -1)[1],
    ],
)
