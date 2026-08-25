from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db.database as db
from services.plan_service import get_user_plan_info
from services.key_service import redeem_key_for_user
from utils.formatting import plan_info_msg, error_msg, success_msg, fancy, dev_footer
from utils.validators import sanitize_input


async def plan_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /plan – show plan info."""
    user = update.effective_user
    if not user:
        return
    plan_info = await get_user_plan_info(user.id)
    text = plan_info_msg(plan_info["plan"])
    await update.message.reply_text(text, parse_mode="HTML")


async def redeem_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /redeem <key> – redeem a premium key."""
    user = update.effective_user
    if not user:
        return

    args = ctx.args
    if not args:
        text = (
            f"╭─ ⟡ {fancy('Redeem')}\n"
            f"├─ Usᴀɢᴇ: /redeem <code>&lt;key&gt;</code>\n"
            f"├─ Exᴀᴍᴘʟᴇ: /redeem CR-ABCD1234EFGH5678\n"
            f"{dev_footer()}"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        return

    key_str = sanitize_input(" ".join(args), max_len=30)
    success, message = await redeem_key_for_user(key_str, user.id)

    if success:
        text = (
            f"╭─ ✓ {fancy('Redeemed')}\n"
            f"├─ {message}\n"
            f"{dev_footer()}"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(
            error_msg("Fᴀɪʟᴇᴅ", message), parse_mode="HTML"
        )


# Callback for plan info from menu
async def plan_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plan button callback."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    plan_info = await get_user_plan_info(user.id)
    text = plan_info_msg(plan_info["plan"])
    keyboard = [[InlineKeyboardButton("⟡ Back to Menu", callback_data="back_menu")]]
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def redeem_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle redeem button – prompt for key."""
    query = update.callback_query
    await query.answer()
    text = (
        f"╭─ ⟡ {fancy('Redeem Key')}\n"
        f"├─ Sᴇɴᴅ ᴛʜᴇ ᴋᴇʏ ᴜsɪɴɢ:\n"
        f"├─ /redeem <code>&lt;key&gt;</code>\n"
        f"{dev_footer()}"
    )
    keyboard = [[InlineKeyboardButton("⟡ Back to Menu", callback_data="back_menu")]]
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )
