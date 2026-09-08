"""
Telegram E-Commerce & Service Bot — main entry point.

Architecture (Hybrid: Long Polling + FastAPI):
    • FastAPI binds to the required $PORT and keeps the instance alive.
    • Lifespan context manager:
        1.  Initializes PostgreSQL
        2.  Starts background rate-fetcher (BrsApi, every 5 min)
        3.  Clears any old webhook from Telegram
        4.  Starts Telegram polling as a background asyncio task
    • A /verify GET endpoint receives Zarinpal payment callbacks.
    • A /health, /ping, and / endpoint are available for uptime pings.
    • On shutdown, polling is cancelled and resources are cleaned up.

Usage:
    python bot.py   # starts FastAPI + polling hybrid server

Environment variables:
    BOT_TOKEN          — Telegram Bot API token
    ADMIN_IDS          — comma-separated Telegram user IDs
    DATABASE_URL       — PostgreSQL connection string (Neon.tech)
    WEBHOOK_HOST       — bind address (default 0.0.0.0)
    WEBHOOK_PORT       — bind port    (default 8443, Render sets $PORT)
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse

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


# ─── Module-level Bot & Dispatcher (lazy-initialized in lifespan) ───
# These are set during startup so they can be accessed by the
# FastAPI verify endpoint and background tasks without creating
# redundant bot sessions.
bot: Bot = None  # type: ignore[assignment]
dp: Dispatcher = None  # type: ignore[assignment]


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
        # Use the module-level bot (initialized in lifespan) which is the most
        # reliable reference. `event.bot` can be None when the error is raised
        # before a bot is bound to the update (e.g. in middleware), which
        # previously caused `'NoneType' object has no attribute 'send_message'`.
        bot_instance: Bot | None = event.bot or bot
        if bot_instance is None:
            logger.error(
                "Could not notify user %s about an error: no bot instance available.",
                user_id,
            )
            return
        try:
            await bot_instance.send_message(
                chat_id=user_id,
                text=(
                    "❌ متاسفانه در پردازش درخواست شما مشکلی رخ داد.\n"
                    "لطفاً لحظاتی بعد مجدداً تلاش کنید یا با پشتیبانی تماس بگیرید."
                ),
            )
        except Exception as send_exc:
            logger.error("Failed to send error message to user %s: %s", user_id, send_exc)


# ─── Router registration ─────────────────────────────────────────────
def register_routers(dispatcher: Dispatcher) -> None:
    """Import and include every feature router in the dispatcher."""
    from handlers.user import router as user_router
    from handlers.rate import router as rate_router
    from handlers.premium import router as premium_router
    from handlers.stars import router as stars_router
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

    dispatcher.include_routers(
        user_router,       # Must be first to catch /start and reply keyboard buttons
        rate_router,       # Exchange-rate cached response
        ticket_router,     # Ticket system (reply keyboard triggers)
        premium_router,
        stars_router,
        ai_router,
        design_router,
        security_router,
        admin_router,
        payment_router,
    )


# ─── FastAPI lifespan (hybrid: polling + FastAPI for payments) ───────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start everything concurrently and clean up on shutdown.

    Runs FastAPI for Zarinpal callbacks and health checks, while
    Telegram polling runs as a background asyncio task.
    """
    global bot, dp

    # ── 1. Database ──────────────────────────────────────────────────
    logger.info("Initializing database (PostgreSQL) …")
    await init_db()
    logger.info("Database ready.")

    # ── 2. Background rate-fetcher ───────────────────────────────────
    from utils.cache import rate_cache
    rate_fetcher_task = asyncio.create_task(rate_cache.start(interval=300))
    logger.info(
        "Background rate-fetcher task started (PID-like: %s)",
        rate_fetcher_task.get_name(),
    )

    # ── 3. aiogram Bot + Dispatcher ──────────────────────────────────
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Give the rate-cache background task a bot reference so it can alert
    # admins when the BrsApi rate fetch fails.
    rate_cache.set_bot(bot)

    dp.errors.register(global_error_handler)
    register_routers(dp)

    # ── 4. Clear old webhook (from previous Render/webhook deployments) ─
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Old webhook cleared (if any).")

    # ── 5. Start Telegram polling as a background task ───────────────
    polling_task = asyncio.create_task(dp.start_polling(bot))
    logger.info(
        "Telegram long-polling started (task: %s)",
        polling_task.get_name(),
    )

    # ── 6. Monitor polling task for unexpected crashes ───────────────
    async def _polling_monitor(task: asyncio.Task) -> None:
        """Log if the polling task terminates unexpectedly."""
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected during shutdown
        except Exception:
            logger.exception(
                "Telegram polling task crashed unexpectedly! "
                "The bot will stop receiving updates."
            )

    polling_monitor_task = asyncio.create_task(_polling_monitor(polling_task))

    yield  # ── FastAPI is now live, health checks and /verify work ──

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down …")

    # Stop polling
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    polling_monitor_task.cancel()
    try:
        await polling_monitor_task
    except asyncio.CancelledError:
        pass
    logger.info("Polling stopped.")

    # Cancel background tasks
    rate_cache.stop()
    rate_fetcher_task.cancel()

    try:
        await rate_fetcher_task
    except asyncio.CancelledError:
        pass

    await close_pool()
    await bot.session.close()
    logger.info("Shutdown complete.")


# ─── FastAPI application ─────────────────────────────────────────────
app = FastAPI(title="Telegram Bot Server", lifespan=lifespan)


# ─── Zarinpal /verify endpoint (merged from webhook/app.py) ─────────

@app.get("/verify")
async def zarinpal_verify(
    Authority: str = Query(..., description="Zarinpal authority token"),
    Status: str = Query(..., description="Payment status from Zarinpal"),
):
    """
    Zarinpal redirects the user's browser here after payment.

    Query params (set by Zarinpal):
        Authority  – payment authority token
        Status     - \"OK\" if user approved, else \"NOK\"
    """
    if Status != "OK":
        return HTMLResponse(
            _error_page("Payment was cancelled or failed. You may close this window."),
            status_code=400,
        )

    # ── Look up the payment record by authority ───────────────────
    from database.db import (
        get_payment_by_authority,
        get_payment,
        complete_payment,
        fail_payment,
        get_order,
    )
    from utils.zarinpal import verify_payment

    payment = await get_payment_by_authority(Authority)
    if payment is None:
        logger.warning("No payment found for authority=%s", Authority)
        return HTMLResponse(
            _error_page("Payment record not found. Please return to the bot and click 'I paid'."),
            status_code=404,
        )

    if payment["status"] == "verified":
        return HTMLResponse(
            _success_page("Payment was already verified. You may close this window and return to the bot."),
        )

    full_payment = await get_payment(payment["payment_id"])
    if full_payment is None:
        return HTMLResponse(
            _error_page("Payment record is incomplete. Please return to the bot."),
            status_code=409,
        )

    order_id = full_payment["order_id"]
    amount_irt = full_payment["order_amount_irt"]

    if (
        full_payment["authority"] != Authority
        or full_payment["payment_status"] != "init"
        or full_payment["order_status"] != "pending"
        or full_payment["payment_amount_irt"] != full_payment["order_amount_irt"]
    ):
        await fail_payment(full_payment["payment_id"])
        return HTMLResponse(
            _error_page("Payment data is invalid or has already been processed."),
            status_code=409,
        )

    # ── Verify with Zarinpal API ──────────────────────────────────
    result = await verify_payment(Authority, amount_irt)
    amount_matches = result.amount_irt == full_payment["order_amount_irt"]

    if not (
        result.success
        and result.code in (100, 101)
        and result.ref_id
        and amount_matches
    ):
        await fail_payment(full_payment["payment_id"])
        reason = result.message or "The gateway amount does not match the order amount."
        logger.warning("Webhook verify failed for order #%s: %s", order_id, reason)
        return HTMLResponse(
            _error_page(
                f"❌ Payment verification failed.\n\n"
                f"Reason: {reason}\n\n"
                "Please return to the bot and try again."
            ),
            status_code=400,
        )

    completed = await complete_payment(
        payment_id=full_payment["payment_id"],
        order_id=order_id,
        ref_id=result.ref_id,
    )
    if not completed:
        return HTMLResponse(_success_page("Payment was already verified. You may close this window."))

    logger.info("Webhook verified order #%s — ref_id=%s", order_id, result.ref_id)

    # ── Delivery (in background so the HTTP response is fast) ─────
    order = await get_order(order_id)
    if order:
        asyncio.create_task(
            _background_delivery(order_id, order["user_id"], order["product"], order["details"])
        )

    return HTMLResponse(
        _success_page(
            f"✅ Payment verified successfully!\n\n"
            f"Ref ID: {result.ref_id}\n\n"
            "Return to the Telegram bot — your product is being delivered."
        ),
    )


async def _background_delivery(order_id: int, user_id: int, product: str, details: str) -> None:
    """Run delivery in the background without blocking the HTTP response.

    Uses the shared module-level bot instance instead of creating a new
    session for each background delivery.
    """
    from utils.delivery import deliver_product
    try:
        if bot is None:
            logger.error("Bot instance not available for background delivery of order #%s", order_id)
            return
        await deliver_product(bot, user_id, order_id, product, details)
    except Exception as exc:
        logger.exception("Background delivery failed for order #%s: %s", order_id, exc)


# ─── Health & root endpoints ─────────────────────────────────────────

@app.get("/", response_class=JSONResponse)
async def root():
    """Root endpoint — confirms the service is alive."""
    return JSONResponse({"status": "ok", "mode": "polling"})


@app.get("/ping", response_class=JSONResponse)
async def ping():
    """Keep-alive endpoint for cron-job.org / UptimeRobot."""
    from utils.cache import rate_cache
    return JSONResponse({
        "status": "alive",
        "cached_price": rate_cache.get_data() is not None,
        "last_update": rate_cache.last_updated_str(),
    })


@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Health endpoint — detailed status for monitoring."""
    from utils.cache import rate_cache
    return JSONResponse({
        "status": "ok",
        "mode": "polling",
        "rate_cache_ready": rate_cache.is_ready(),
        "rate_last_update": rate_cache.last_updated_str(),
    })


# ─── HTML pages for /verify ──────────────────────────────────────────

def _success_page(message: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Verified</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                display: flex; justify-content: center; align-items: center;
                min-height: 100vh; margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .card {{
                background: rgba(255,255,255,0.15); backdrop-filter: blur(10px);
                border-radius: 16px; padding: 40px; max-width: 480px;
                text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            }}
            h1 {{ font-size: 2.5em; margin-bottom: 0.5em; }}
            p {{ font-size: 1.1em; line-height: 1.6; white-space: pre-line; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>✅</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """


def _error_page(message: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Issue</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                display: flex; justify-content: center; align-items: center;
                min-height: 100vh; margin: 0;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
            }}
            .card {{
                background: rgba(255,255,255,0.15); backdrop-filter: blur(10px);
                border-radius: 16px; padding: 40px; max-width: 480px;
                text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            }}
            h1 {{ font-size: 2.5em; margin-bottom: 0.5em; }}
            p {{ font-size: 1.1em; line-height: 1.6; white-space: pre-line; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>⚠️</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """


# ─── Entry point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bot:app",
        host=config.WEBHOOK_HOST,
        port=config.WEBHOOK_PORT,
        log_level="info",
    )
