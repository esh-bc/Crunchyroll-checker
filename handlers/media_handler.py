"""Media configuration handler – set verify, menu, and single-hit media."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

import config
import db.database as db
from utils.formatting import success_msg, error_msg, fancy, dev_footer

log = logging.getLogger(__name__)


async def _save_media(media_type: str, file_id: str, mime_type: str) -> None:
    """Save a media config to DB."""
    media_obj = {"type": "", "file_id": ""}
    if mime_type.startswith("video"):
        media_obj["type"] = "video"
        media_obj["file_id"] = file_id
    elif mime_type.startswith("image"):
        media_obj["type"] = "photo"
        media_obj["file_id"] = file_id
    else:
        return
    await db.set_bot_config(media_type, media_obj)


async def set_verify_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /verify – reply to a photo/video to set as verification media."""
    user = update.effective_user
    if not user or user.id not in config.ADMIN_IDS:
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(
            error_msg("Uᴤᴇʀ", "Rᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ ᴠɪᴅᴇᴏ ᴛᴏ sᴇᴛ ɪᴛ ᴀs ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ᴍᴇᴅɪᴀ."),
            parse_mode="HTML",
        )
        return

    file_id = ""
    mime = ""
    if reply.photo:
        file_id = reply.photo[-1].file_id
        mime = "image/jpeg"
    elif reply.video:
        file_id = reply.video.file_id
        mime = reply.video.mime_type or "video/mp4"
    else:
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", "Rᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ ᴠɪᴅᴇᴏ."), parse_mode="HTML")
        return

    await _save_media("verify_media", file_id, mime)
    ctx.bot_data["bot_config"]["verify_media"] = {"type": "photo" if "image" in mime else "video", "file_id": file_id}
    await update.message.reply_text(success_msg("Sᴇᴛ", "Vᴇʀɪғɪᴄᴀᴛɪᴏɴ ᴍᴇᴅɪᴀ ᴜᴘᴅᴀᴛᴇᴅ."), parse_mode="HTML")


async def set_menu_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu_media – reply to a photo/video to set as menu media."""
    user = update.effective_user
    if not user or user.id not in config.ADMIN_IDS:
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(
            error_msg("Uᴤᴇʀ", "Rᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ ᴠɪᴅᴇᴏ ᴛᴏ sᴇᴛ ɪᴛ ᴀs ᴍᴇɴᴜ ᴍᴇᴅɪᴀ."), parse_mode="HTML"
        )
        return

    file_id = ""
    mime = ""
    if reply.photo:
        file_id = reply.photo[-1].file_id
        mime = "image/jpeg"
    elif reply.video:
        file_id = reply.video.file_id
        mime = reply.video.mime_type or "video/mp4"
    else:
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", "Rᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ ᴠɪᴅᴇᴏ."), parse_mode="HTML")
        return

    await _save_media("menu_media", file_id, mime)
    ctx.bot_data["bot_config"]["menu_media"] = {"type": "photo" if "image" in mime else "video", "file_id": file_id}
    await update.message.reply_text(success_msg("Sᴇᴛ", "Mᴇɴᴜ ᴍᴇᴅɪᴀ ᴜᴘᴅᴀᴛᴇᴅ."), parse_mode="HTML")


async def set_single_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /single – reply to a photo/video to set as single-hit media."""
    user = update.effective_user
    if not user or user.id not in config.ADMIN_IDS:
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(
            error_msg("Uᴤᴇʀ", "Rᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ ᴠɪᴅᴇᴏ ᴛᴏ sᴇᴛ ɪᴛ ᴀs sɪɴɢʟᴇ ʜɪᴛ ᴍᴇᴅɪᴀ."), parse_mode="HTML"
        )
        return

    file_id = ""
    mime = ""
    if reply.photo:
        file_id = reply.photo[-1].file_id
        mime = "image/jpeg"
    elif reply.video:
        file_id = reply.video.file_id
        mime = reply.video.mime_type or "video/mp4"
    else:
        await update.message.reply_text(error_msg("Iɴᴠᴀʟɪᴅ", "Rᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ ᴠɪᴅᴇᴏ."), parse_mode="HTML")
        return

    await _save_media("single_media", file_id, mime)
    ctx.bot_data["bot_config"]["single_media"] = {"type": "photo" if "image" in mime else "video", "file_id": file_id}
    await update.message.reply_text(success_msg("Sᴇᴛ", "Sɪɴɢʟᴇ ʜɪᴛ ᴍᴇᴅɪᴀ ᴜᴘᴅᴀᴛᴇᴅ."), parse_mode="HTML")
