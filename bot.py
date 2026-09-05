"""
Telegram E-Commerce & Service Bot — main entry point.

Architecture (Render.com Web Service):
    • FastAPI binds to the required $PORT and keeps the dyno alive.
    • Lifespan context manager starts three concurrent tasks:
        1.  PostgreSQL init
        2.  Background rate-fetcher (BrsApi, every 5 min)
        3.  aiogram long-polling
    • A /health endpoint is available for external uptime pings.

Usage:
    python bot.py           # starts FastAPI + polling

Environment variables:
    BOT_TOKEN, ADMIN_IDS, DATABASE_URL, WEBHOOK_MODE, WEBHOOK_HOST,
    WEBHOOK_PORT, WEBHOOK_BASE_URL
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, ErrorEvent

from config import config
from database.db import init_db, close_pool

# ─── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("bot")


# ─── Global Error Handler ────────────────────────────────────────────

async def global_error_handler(event: ErrorEvent) -> None:
    """Catch ALL unhandled exceptions.

    • Logs the real error to the console for debugging.
    • Sends a polite Persian message to the user (never exposes tracebacks).
    """
    update: Update = event.update
    exception = event.exception

    logger.error(
        "Unhandled exception in handler %s: %s",
        getattr(update, "handler", "unknown"),
        exception,
        exc_info=True,
    )

    user_id: int | None = None
    if update.message and update.message.from_user:
        user_id = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        user_id = update.callback_query.from_user.id

    if user_id is not None:
        try:
            bot: Bot = event.bot
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ متاسفانه در پردازش درخواست شما مشکلی رخ داد.\n"
                    "لطفاً لحظاتی بعد مجدداً تلاش کنید یا با پشتیبانی تماس بگیرید."
                ),
            )
        except Exception as send_exc:
            logger.error("Failed to send error message to user %s: %s", user_id, send_exc)


# ─── Router registration ─────────────────────────────────────────────
def register_routers(dp: Dispatcher) -> None:
    """Import and include every feature router in the dispatcher."""
    from handlers.user import router as user_router
    from handlers.rate import router as rate_router
    from handlers.premium import router as premium_router
    from handlers.stars import router as stars_router
    from handlers.virtual_numbers import router as vn_router
    from handlers.ai_accounts import router as ai_router
    from handlers.design import router as design_router
    from handlers.page_security import router as security_router
    from handlers.admin import router as admin_router
    from handlers.payment import router as payment_router
    from handlers.ticket import router as ticket_router

    # Attach admin security middleware to the admin router
    from middleware.admin_security import AdminSecurityMiddleware
    admin_router.message.middleware(AdminSecurityMiddleware())
    admin_router.callback_query.middleware(AdminSecurityMiddleware())

    dp.include_routers(
        user_router,       # Must be first to catch /start and reply keyboard buttons
        rate_router,       # Exchange-rate cached response
        ticket_router,     # Ticket system (reply keyboard triggers)
        premium_router,
        stars_router,
        vn_router,
        ai_router,
        design_router,
        security_router,
        admin_router,
        payment_router,
    )


# ─── FastAPI lifespan (the heart of Render deployment) ───────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start everything concurrently and clean up on shutdown.

    Runs inside FastAPI so Render's $PORT binding is satisfied while
    the bot polls Telegram in the background.
    """
    # 1. Database
    logger.info("Initializing database (PostgreSQL) …")
    await init_db()
    logger.info("Database ready.")

    # 2. Background rate-fetcher
    from utils.cache import rate_cache
    rate_fetcher_task = asyncio.create_task(rate_cache.start(interval=300))
    logger.info("Background rate-fetcher task started (PID-like: %s)", rate_fetcher_task.get_name())

    # 3. aiogram Bot + Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.errors.register(global_error_handler)
    register_routers(dp)

    polling_task = asyncio.create_task(dp.start_polling(bot))
    logger.info("aiogram polling started.")

    yield  # ── FastAPI is now live, Render's health checks can pass ──

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("Shutting down …")
    rate_cache.stop()
    rate_fetcher_task.cancel()
    polling_task.cancel()

    # Wait for tasks to finish cancelling
    for task in (rate_fetcher_task, polling_task):
        try:
            await task
        except asyncio.CancelledError:
            pass

    await close_pool()
    await bot.session.close()
    logger.info("Shutdown complete.")


# ─── FastAPI application ─────────────────────────────────────────────
app = FastAPI(title="Telegram Bot Server", lifespan=lifespan)


@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Health endpoint — ping this to keep the Render service alive."""
    from utils.cache import rate_cache
    return JSONResponse({
        "status": "ok",
        "rate_cache_ready": rate_cache.is_ready(),
        "rate_last_update": rate_cache.last_updated_str(),
    })


# ─── Entry point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bot:app",
        host=config.WEBHOOK_HOST,
        port=config.WEBHOOK_PORT,
        log_level="info",
    )
