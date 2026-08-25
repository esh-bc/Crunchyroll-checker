from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
import db.database as db
from utils.formatting import fancy, dev_footer

log = logging.getLogger(__name__)


async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start – verify channel join, then show menu."""
    user = update.effective_user
    if not user:
        return

    # Check maintenance
    bot_cfg = ctx.bot_data.get("bot_config") or await db.get_bot_config()
    if bot_cfg.get("maintenance_mode") and user.id not in config.ADMIN_IDS:
        text = (
            f"╭─ ⚠ {fancy('Maintenance')}\n"
            f"├─ Bᴏᴛ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.\n"
            f"├─ Pʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.\n"
            f"{dev_footer()}"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        return

    # Check ban
    user_doc = await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        is_bot=user.is_bot,
        language_code=user.language_code or "",
    )
    if user_doc.get("banned"):
        return

    # Channel verification
    channels = config.REQUIRED_CHANNELS
    if channels and user.id not in config.ADMIN_IDS:
        not_joined = []
        for ch_id in channels:
            try:
                member = await ctx.bot.get_chat_member(chat_id=int(ch_id), user_id=user.id)
                if member.status not in ("member", "administrator", "creator"):
                    not_joined.append(ch_id)
            except Exception:
                not_joined.append(ch_id)

        if not_joined:
            await _show_verification(update, ctx, not_joined)
            return

    # User is verified
    if not user_doc.get("verified"):
        await db.update_user(user.id, {"verified": True})

    # Show menu
    from handlers.menu import show_menu
    await show_menu(update, ctx, user_doc)


async def verify_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Verify button press."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    channels = config.REQUIRED_CHANNELS
    not_joined = []

    for ch_id in channels:
        try:
            member = await ctx.bot.get_chat_member(chat_id=int(ch_id), user_id=user.id)
            if member.status not in ("member", "administrator", "creator"):
                not_joined.append(ch_id)
        except Exception:
            not_joined.append(ch_id)

    if not_joined:
        text = (
            f"╭─ ✕ {fancy('Verification Failed')}\n"
            f"├─ Yᴏᴜ ʜᴀᴠᴇ ɴᴏᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs.\n"
            f"├─ Pʟᴇᴀsᴇ ᴊᴏɪɴ ᴛʜᴇᴍ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.\n"
            f"{dev_footer()}"
        )
        await query.edit_message_text(text, parse_mode="HTML")
    else:
        await db.update_user(user.id, {"verified": True})
        user_doc = await db.get_user(user.id)
        from handlers.menu import show_menu
        await show_menu(update, ctx, user_doc)


async def _show_verification(update: Update, ctx: ContextTypes.DEFAULT_TYPE, channels: list[str]) -> None:
    """Show channel join buttons + verify button."""
    buttons = []
    for ch_id in channels:
        try:
            chat = await ctx.bot.get_chat(int(ch_id))
            name = chat.title or ch_id
            link = ""
            if chat.username:
                link = f"https://t.me/{chat.username}"
            elif chat.invite_link:
                link = chat.invite_link
            if link:
                buttons.append([InlineKeyboardButton(f"⇢ {name}", url=link)])
            else:
                buttons.append([InlineKeyboardButton(f"⇢ Channel {ch_id}", url=f"https://t.me/c/{ch_id[4:]}")])
        except Exception:
            buttons.append([InlineKeyboardButton(f"⇢ Channel {ch_id}", url=f"https://t.me/c/{ch_id[4:]}")])

    buttons.append([InlineKeyboardButton("✓ Verify", callback_data="verify_join")])

    bot_cfg = ctx.bot_data.get("bot_config") or await db.get_bot_config()
    verify_media = bot_cfg.get("verify_media")

    text = (
        f"╭─ ⟡ {fancy('Access Required')}\n"
        f"├─ Jᴏɪɴ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟ(s) ʙᴇʟᴏᴡ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ.\n"
        f"├─ Tʜᴇɴ ᴘʀᴇss ✓ Vᴇʀɪғʏ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.\n"
        f"{dev_footer()}"
    )
    reply_markup = InlineKeyboardMarkup(buttons)

    if verify_media and verify_media.get("type") == "photo" and verify_media.get("file_id"):
        await update.message.reply_photo(
            photo=verify_media["file_id"],
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    elif verify_media and verify_media.get("type") == "video" and verify_media.get("file_id"):
        await update.message.reply_video(
            video=verify_media["file_id"],
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )
