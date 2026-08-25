"""Main menu handler."""

import logging
from typing import TYPE_CHECKING

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
import db.database as db
from utils.formatting import main_menu_msg, dev_footer, fancy

log = logging.getLogger(__name__)


async def show_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_doc: dict) -> None:
    """Display the main menu. Works for both messages and callback queries."""
    bot_cfg = ctx.bot_data.get("bot_config") or await db.get_bot_config()
    text = main_menu_msg(user_doc, bot_cfg)

    keyboard = [
        [
            InlineKeyboardButton("⟡ Check Single", callback_data="do_check"),
            InlineKeyboardButton("⟡ Bulk Check", callback_data="do_bulk"),
        ],
        [
            InlineKeyboardButton("⟡ My Plan", callback_data="do_plan"),
            InlineKeyboardButton("⟡ Redeem Key", callback_data="do_redeem"),
        ],
        [
            InlineKeyboardButton("⟡ Proxies", callback_data="do_proxies"),
            InlineKeyboardButton("⟡ Cancel Job", callback_data="do_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_media = bot_cfg.get("menu_media")

    # Determine if we're replying to a message or editing a callback query
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )
        return

    if update.message and menu_media:
        if menu_media.get("type") == "photo" and menu_media.get("file_id"):
            await update.message.reply_photo(
                photo=menu_media["file_id"],
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return
        elif menu_media.get("type") == "video" and menu_media.get("file_id"):
            await update.message.reply_video(
                video=menu_media["file_id"],
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return

    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


async def menu_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command."""
    user = update.effective_user
    if not user:
        return

    # Ensure user exists
    user_doc = await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
    )
    if user_doc.get("banned"):
        return
    if not user_doc.get("verified") and user.id not in config.ADMIN_IDS:
        from handlers.start import start_cmd
        await start_cmd(update, ctx)
        return

    await show_menu(update, ctx, user_doc)
