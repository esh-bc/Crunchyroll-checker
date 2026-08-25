from telegram import Update
from telegram.ext import ContextTypes
from core.worker import cancel_user_job
from utils.formatting import success_msg, error_msg, fancy, dev_footer

async def cancel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel – cancel user's active job."""
    user = update.effective_user
    if not user:
        return

    cancelled = await cancel_user_job(user.id)
    if cancelled:
        await update.message.reply_text(
            success_msg("Cᴀɴᴄᴇʟʟᴇᴅ", "Yᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴊᴏʙ ɪs ʙᴇɪɴɢ sᴛᴏᴘᴘᴇᴅ."),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            error_msg("Nᴏ Jᴏʙ", "Nᴏ ᴀᴄᴛɪᴠᴇ ᴊᴏʙ ᴛᴏ ᴄᴀɴᴄᴇʟ."),
            parse_mode="HTML",
        )

async def cancel_bulk_conv(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the bulk conversation."""
    await update.message.reply_text("Cᴀɴᴄᴇʟʟᴇᴅ.", parse_mode="HTML")
    return ConversationHandler.END
