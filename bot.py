"""
Telegram E-Commerce & Service Bot — main entry point.

Usage:
    # Polling mode (default)
    python bot.py

    # Webhook mode (runs FastAPI + polling in parallel)
    WEBHOOK_MODE=true python bot.py

Environment variables (or edit config.py):
    BOT_TOKEN, ADMIN_IDS, ZARINPAL_MERCHANT_ID, ZARINPAL_SANDBOX,
    WEBHOOK_MODE, WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_BASE_URL
"""

import asyncio
import logging
import multiprocessing

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database.db import init_db

# ─── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("bot")


# ─── Router registration ─────────────────────────────────────────────
def register_routers(dp: Dispatcher) -> None:
    """Import and include every feature router in the dispatcher."""
    from handlers.user import router as user_router
    from handlers.premium import router as premium_router
    from handlers.stars import router as stars_router
    from handlers.virtual_numbers import router as vn_router
    from handlers.ai_accounts import router as ai_router
    from handlers.design import router as design_router
    from handlers.page_security import router as security_router
    from handlers.admin import router as admin_router
    from handlers.payment import router as payment_router

    # Attach admin security middleware to the admin router
    from middleware.admin_security import AdminSecurityMiddleware
    admin_router.message.middleware(AdminSecurityMiddleware())
    admin_router.callback_query.middleware(AdminSecurityMiddleware())

    dp.include_routers(
        user_router,
        premium_router,
        stars_router,
        vn_router,
        ai_router,
        design_router,
        security_router,
        admin_router,
        payment_router,
    )

# ─── Startup / Shutdown ─────────────────────────────────────────────
# تغییر انجام شده در این خط است: _bot به bot تبدیل شد
async def on_startup(bot: Bot) -> None:
    logger.info("Initializing database …")
    await init_db()
    logger.info("Database ready.")


async def on_shutdown(bot: Bot) -> None:
    logger.info("Shutting down bot …")
    await bot.session.close()


# ─── Webhook server (runs in a separate process) ────────────────────

def _run_webhook_server(bot_token: str) -> None:
    """Start the FastAPI webhook server in a child process.

    This function creates its own Bot instance for sending messages
    (webhook handler needs an aiogram Bot, not just the HTTP server).
    """
    import uvicorn
    from webhook.app import app, set_bot

    async def _startup():
        # Create a lightweight Bot for message delivery
        bot = Bot(token=bot_token)
        set_bot(bot)

    # We can't easily mix asyncio event loops across processes,
    # so we create the bot inside the lifespan.
    # Override lifespan to inject the bot.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def webhook_lifespan(application):
        from database.db import init_db as db_init
        from aiogram import Bot as AiogramBot
        bot = AiogramBot(token=bot_token)
        set_bot(bot)
        await db_init()
        logger.info("Webhook server: database & bot ready.")
        yield
        await bot.session.close()
        logger.info("Webhook server: bot session closed.")

    app.router.lifespan_context = webhook_lifespan

    uvicorn.run(
        app,
        host=config.WEBHOOK_HOST,
        port=config.WEBHOOK_PORT,
        log_level="info",
    )

# ─── Main ────────────────────────────────────────────────────────────
async def main() -> None:
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Routers
    register_routers(dp)

    # ── Webhook mode: run FastAPI in a parallel process ────────────
    if config.WEBHOOK_MODE:
        logger.info("Webhook mode enabled — starting FastAPI server on %s:%s",
                     config.WEBHOOK_HOST, config.WEBHOOK_PORT)

        webhook_process = multiprocessing.Process(
            target=_run_webhook_server,
            args=(config.BOT_TOKEN,),
            daemon=True,
        )
        webhook_process.start()
        logger.info("Webhook server PID: %s", webhook_process.pid)

    # ── Telegram polling (always runs) ────────────────────────────
    logger.info("Starting Telegram polling …")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())