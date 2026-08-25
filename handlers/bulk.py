import time
import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

import config
import db.database as db
from core.worker import (
    JobContext,
    parse_combos,
    run_bulk_job,
    get_active_job,
    cancel_user_job,
    cleanup_old_jobs,
)
from core.proxy import ProxyManager
from services.plan_service import get_user_plan_info, check_plan_limit, check_concurrent_jobs
from utils.formatting import (
    checking_progress_msg,
    hit_message,
    job_summary_msg,
    error_msg,
    success_msg,
    fancy,
    dev_footer,
    fmt_num,
)
from utils.validators import validate_upload, sanitize_input

log = logging.getLogger(__name__)

BULK_WAIT_FILE = 0


async def bulk_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    user_doc = await db.get_user(user.id)
    if not user_doc or user_doc.get("banned"):
        return ConversationHandler.END

    ok, msg = await check_concurrent_jobs(user.id)
    if not ok:
        await update.message.reply_text(error_msg("Jᴏʙ Aᴄᴛɪᴠᴇ", msg), parse_mode="HTML")
        return ConversationHandler.END

    plan_info = await get_user_plan_info(user.id)
    proxy_count = len(ctx.bot_data.get("proxy_manager") or [])

    text = (
        f"╭─ ⟡ {fancy('Bulk Check')}\n"
        f"├─ ▸ <b>{fancy('Plan')}</b>: {plan_info['label']}\n"
        f"├─ ▸ <b>{fancy('Max Combos')}</b>: {fmt_num(plan_info['max_combo'])}\n"
        f"├─ ▸ <b>{fancy('Speed Limit')}</b>: {plan_info['speed_limit']} concurrent\n"
        f"├─ ▸ <b>{fancy('Proxies')}</b>: {proxy_count} loaded\n"
        f"├─ ════════════════════════\n"
        f"├─ Sᴇɴᴅ ᴀ <code>.txt</code> ғɪʟᴇ ᴡɪᴛʜ <code>email:pass</code> ᴄᴏᴍʙᴏs.\n"
        f"├─ Mᴀx ғɪʟᴇ sɪᴢᴇ: {config.MAX_FILE_SIZE // (1024*1024)}MB\n"
        f"├─ /cancel ᴛᴏ ᴀʙᴏʀᴛ\n"
        f"{dev_footer()}"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    return BULK_WAIT_FILE


async def _file_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not user or not update.message.document:
        await update.message.reply_text(error_msg("Eʀʀᴏʀ", "Pʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ғɪʟᴇ."), parse_mode="HTML")
        return BULK_WAIT_FILE

    doc = update.message.document
    ext = Path(doc.file_name or "").suffix.lower()
    if ext not in (".txt", ".csv"):
        await update.message.reply_text(
            error_msg("Iɴᴠᴀʟɪᴅ", "Oɴʟʏ .txt ᴀɴᴅ .csv ғɪʟᴇs ᴀʀᴇ ᴀᴄᴄᴇᴘᴛᴇᴅ."),
            parse_mode="HTML",
        )
        return BULK_WAIT_FILE

    if doc.file_size and doc.file_size > config.MAX_FILE_SIZE:
        await update.message.reply_text(
            error_msg("Tᴏᴏ Lᴀʀɢᴇ", f"Mᴀx {config.MAX_FILE_SIZE // (1024*1024)}MB."),
            parse_mode="HTML",
        )
        return BULK_WAIT_FILE

    status_msg = await update.message.reply_text(
        f"╭─ ⟡ {fancy('Processing')}\n"
        f"├─ Dᴏᴡɴʟᴏᴀᴅɪɴɢ ғɪʟᴇ...\n"
        f"{dev_footer()}",
        parse_mode="HTML",
    )

    try:
        file = await doc.get_file()
        tmp_path = config.TMP_DIR / f"bulk_{user.id}_{int(time.time())}.txt"
        await file.download_to_drive(str(tmp_path))
    except Exception as exc:
        await status_msg.edit_text(error_msg("Dᴏᴡɴʟᴏᴀᴅ Fᴀɪʟᴇᴅ", str(exc)[:200]), parse_mode="HTML")
        return BULK_WAIT_FILE

    valid, err = validate_upload(str(tmp_path))
    if not valid:
        tmp_path.unlink(missing_ok=True)
        await status_msg.edit_text(error_msg("Iɴᴠᴀʟɪᴅ Fɪʟᴇ", err), parse_mode="HTML")
        return BULK_WAIT_FILE

    try:
        content = tmp_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        await status_msg.edit_text(error_msg("Rᴇᴅ Eʀʀᴏʀ", str(exc)[:200]), parse_mode="HTML")
        return BULK_WAIT_FILE

    tmp_path.unlink(missing_ok=True)

    combos = parse_combos(content)
    if not combos:
        await status_msg.edit_text(error_msg("Eᴍᴘᴛʏ", "Nᴏ ᴠᴀʟɪᴅ ᴄᴏᴍʙᴏs ғᴏᴜɴᴅ ɪɴ ғɪʟᴇ."), parse_mode="HTML")
        return BULK_WAIT_FILE

    ok, msg = await check_plan_limit(user.id, len(combos))
    if not ok:
        await status_msg.edit_text(error_msg("Lɪᴍɪᴛ Exᴄᴇᴇᴅᴇᴅ", msg), parse_mode="HTML")
        return ConversationHandler.END

    plan_info = await get_user_plan_info(user.id)
    proxy_mgr = ctx.bot_data.get("proxy_manager")
    user_doc = await db.get_user(user.id)
    checker_name = user_doc.get("first_name") or user_doc.get("username") or "User"
    checker_plan = user_doc.get("plan", "free")

    await status_msg.edit_text(
        f"╭─ ⟡ {fancy('Starting')}\n"
        f"├─ Lᴏᴀᴅɪɴɢ {fmt_num(len(combos))} ᴄᴏᴍʙᴏs...\n"
        f"{dev_footer()}",
        parse_mode="HTML",
    )

    job_task = asyncio.create_task(
        _run_job(
            combos=combos,
            user_id=user.id,
            plan=plan_info["plan"],
            proxy_mgr=proxy_mgr,
            status_msg=status_msg,
            checker_name=checker_name,
            checker_id=user.id,
            checker_plan=checker_plan,
            ctx=ctx,
        )
    )
    ctx.user_data["bulk_task"] = job_task

    return ConversationHandler.END


async def _run_job(
    combos: list,
    user_id: int,
    plan: str,
    proxy_mgr: ProxyManager | None,
    status_msg,
    checker_name: str,
    checker_id: int,
    checker_plan: str,
    ctx: ContextTypes.DEFAULT_TYPE,
) -> None:
    from telegram.error import BadRequest

    last_edit_time = 0.0
    edit_interval = 3.0

    async def on_hit(email: str, password: str, info: dict) -> None:
        nonlocal last_edit_time
        try:
            text = hit_message(email, password, info, checker_name, checker_id, checker_plan)
            bot_cfg = ctx.bot_data.get("bot_config") or await db.get_bot_config()
            single_media = bot_cfg.get("single_media")

            if single_media and single_media.get("type") == "photo" and single_media.get("file_id"):
                await status_msg._bot.send_message(
                    chat_id=user_id, photo=single_media["file_id"],
                    caption=text, parse_mode="HTML",
                )
            elif single_media and single_media.get("type") == "video" and single_media.get("file_id"):
                await status_msg._bot.send_message(
                    chat_id=user_id, video=single_media["file_id"],
                    caption=text, parse_mode="HTML",
                )
            else:
                await status_msg._bot.send_message(
                    chat_id=user_id, text=text, parse_mode="HTML"
                )
        except Exception as exc:
            log.warning("Failed to send hit notification: %s", exc)

    async def on_progress(job_ctx: JobContext) -> None:
        nonlocal last_edit_time
        now = time.monotonic()
        if now - last_edit_time < edit_interval:
            return
        last_edit_time = now
        try:
            text = checking_progress_msg(
                checked=job_ctx.checked,
                total=job_ctx.total,
                hits=job_ctx.hits,
                free=job_ctx.free,
                bad=job_ctx.bad,
                retry=job_ctx.retry,
                proxy_errors=job_ctx.proxy_errors,
                cps=job_ctx.cps(),
                eta=job_ctx.eta(),
            )
            await status_msg.edit_text(text, parse_mode="HTML")
        except BadRequest:
            pass
        except Exception as exc:
            log.debug("Progress edit failed: %s", exc)

    try:
        result_ctx = await run_bulk_job(
            combos=combos,
            user_id=user_id,
            plan=plan,
            proxy_mgr=proxy_mgr,
            on_hit=on_hit,
            on_progress=on_progress,
        )

        summary_text = job_summary_msg(result_ctx)
        try:
            await status_msg.edit_text(summary_text, parse_mode="HTML")
        except BadRequest:
            await status_msg.reply_text(summary_text, parse_mode="HTML")

        if result_ctx.out_dir:
            hits_file = result_ctx.out_dir / "hits.txt"
            if hits_file.exists() and hits_file.stat().st_size > 0:
                count = sum(1 for _ in open(hits_file))
                await status_msg.reply_document(
                    document=open(hits_file, "rb"),
                    caption=f"☆ {fmt_num(count)} Hɪᴛs – {result_ctx.job_id}",
                    parse_mode="HTML",
                )

            free_file = result_ctx.out_dir / "free.txt"
            if free_file.exists() and free_file.stat().st_size > 0:
                await status_msg.reply_document(
                    document=open(free_file, "rb"),
                    caption=f"○ {fmt_num(result_ctx.free)} Fʀᴇᴇ – {result_ctx.job_id}",
                    parse_mode="HTML",
                )

            bad_file = result_ctx.out_dir / "bad.txt"
            if bad_file.exists() and bad_file.stat().st_size > 0:
                await status_msg.reply_document(
                    document=open(bad_file, "rb"),
                    caption=f"✕ {fmt_num(result_ctx.bad)} Bᴀᴅ – {result_ctx.job_id}",
                    parse_mode="HTML",
                )

    except asyncio.CancelledError:
        await status_msg.edit_text(
            error_msg("Cᴀɴᴄᴇʟʟᴇᴅ", "Jᴏʙ ᴡᴀs sᴛᴏᴘᴘᴇᴅ."), parse_mode="HTML"
        )
    except Exception as exc:
        log.exception("Bulk job error for user %d", user_id)
        try:
            await status_msg.edit_text(
                error_msg("Eʀʀᴏʀ", str(exc)[:300]), parse_mode="HTML"
            )
        except Exception:
            pass


async def _cancel_bulk(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cᴀɴᴄᴇʟʟᴇᴅ.", parse_mode="HTML")
    return ConversationHandler.END


bulk_conv = ConversationHandler(
    entry_points=[CommandHandler("bulk", bulk_cmd)],
    states={
        BULK_WAIT_FILE: [MessageHandler(filters.Document.ALL, _file_received)],
    },
    fallbacks=[CommandHandler("cancel", _cancel_bulk)],
                )
