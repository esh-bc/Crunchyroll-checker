import sys
import signal
import asyncio
import logging
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import db.database as db
from core.proxy import ProxyManager
from core.worker import cleanup_old_jobs
from utils.health import start_health_server, stop_health_server
from core.checker import close_shared_session

from handlers.start import start_cmd, verify_callback
from handlers.menu import menu_cmd, show_menu
from handlers.check import check_cmd, single_check_conv
from handlers.bulk import bulk_cmd, bulk_conv
from handlers.cancel import cancel_cmd
from handlers.plans import plan_cmd, redeem_cmd, plan_callback, redeem_callback
from handlers.proxy_handler import (
    proxies_cmd,
    proxy_callback_router,
    proxy_upload_conv,
)
from handlers.media_handler import set_verify_media, set_menu_media, set_single_media
from handlers.admin import (
    admin_cmd,
    admin_callback_router,
    ban_cmd,
    unban_cmd,
    setplan_cmd,
    addkey_cmd,
    delkey_cmd,
    broadcast_cmd,
    _is_admin_callback,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# POST-INIT: load data into bot_data
# ═══════════════════════════════════════════
async def post_init(application) -> None:
    """Run after the Application is initialized."""
    log.info("Connecting to MongoDB...")
    await db.connect()

    # Load bot config into memory
    bot_cfg = await db.get_bot_config()
    application.bot_data["bot_config"] = bot_cfg

    # Load alive proxies into memory
    alive = await db.get_alive_proxies()
    pm = ProxyManager()
    pm.load(alive)
    application.bot_data["proxy_manager"] = pm
    log.info("Loaded %d proxies (%d alive)", len(pm), pm.alive_count)

    # Start health-check server
    await start_health_server()

    # Cleanup old job directories
    await cleanup_old_jobs()
    log.info("Bot initialized successfully")


# ═══════════════════════════════════════════
# POST-SHUTDOWN
# ═══════════════════════════════════════════
async def post_shutdown(application) -> None:
    """Run when the Application stops."""
    log.info("Shutting down...")
    await close_shared_session()
    await stop_health_server()
    await db.disconnect()
    log.info("Shutdown complete")


# ═══════════════════════════════════════════
# CALLBACK QUERY ROUTER
# ═══════════════════════════════════════════
async def callback_router(update, ctx):
    """Route all callback queries to the right handler."""
    query = update.callback_query
    if not query:
        return
    data = query.data or ""

    # Verification
    if data == "verify_join":
        await verify_callback(update, ctx)
        return

    # Menu navigation
    if data == "back_menu":
        user_doc = await db.get_user(query.from_user.id)
        if user_doc:
            await show_menu(update, ctx, user_doc)
        else:
            await query.answer("Eʀʀᴏʀ.", show_alert=True)
        return

    # Check/bulk from menu
    if data == "do_check":
        from handlers.check import check_cmd
        await check_cmd(update, ctx)
        return
    if data == "do_bulk":
        from handlers.bulk import bulk_cmd
        await bulk_cmd(update, ctx)
        return
    if data == "do_plan":
        await plan_callback(update, ctx)
        return
    if data == "do_redeem":
        await redeem_callback(update, ctx)
        return
    if data == "do_proxies":
        from handlers.proxy_handler import proxies_cmd
        msg = type('Obj', (), {
            'effective_user': query.from_user,
            'reply_text': lambda t, **kw: query.edit_message_text(t, **kw),
            'message': None,
        })()
        await proxies_cmd(msg, ctx)
        return
    if data == "do_cancel":
        from handlers.cancel import cancel_cmd
        msg = type('Obj', (), {
            'effective_user': query.from_user,
            'message': type('M', (), {'reply_text': lambda t, **kw: query.answer(t, show_alert=True)})(),
        })()
        await cancel_cmd(msg, ctx)
        return

    # Admin callbacks
    if _is_admin_callback(data):
        await admin_callback_router(update, ctx)
        return

    await query.answer("Uɴᴋɴᴏᴡɴ ᴀᴄᴛɪᴏɴ.")


# ═══════════════════════════════════════════
# BUILD APPLICATION
# ═══════════════════════════════════════════
def build_app() -> "Application":
    if not config.BOT_TOKEN:
        print("ERROR: BOT_TOKEN is not set.")
        sys.exit(1)

    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    # ── Commands ──
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("plan", plan_cmd))
    app.add_handler(CommandHandler("redeem", redeem_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("proxies", proxies_cmd))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("setplan", setplan_cmd))
    app.add_handler(CommandHandler("addkey", addkey_cmd))
    app.add_handler(CommandHandler("delkey", delkey_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("verify", set_verify_media))
    app.add_handler(CommandHandler("menu_media", set_menu_media))
    app.add_handler(CommandHandler("single", set_single_media))

    # ── Conversation Handlers ──
    app.add_handler(single_check_conv)
    app.add_handler(bulk_conv)

    # ── Callback Queries ──
    app.add_handler(CallbackQueryHandler(callback_router))

    return app


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
if __name__ == "__main__":
    app = build_app()
    log.info("Starting CrunchyBot...")

    # Graceful shutdown on SIGINT/SIGTERM
    def _signal_handler(sig, frame):
        log.info("Received signal %s, shutting down...", sig)
        asyncio.create_task(app.shutdown())

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Run with idle shutdown to allow background tasks to complete
    app.run_polling(drop_pending_updates=True, close_loop=False)
