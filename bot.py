"""
Telegram E-Commerce & Service Bot — main entry point.

Architecture (Webhook + FastAPI):
    • FastAPI binds to WEBHOOK_HOST:WEBHOOK_PORT.
    • Lifespan context manager:
        1.  Initializes PostgreSQL
        2.  Starts background rate-fetcher (BrsApi, every 5 min)
        3.  Sets the Telegram webhook on startup
        4.  Deletes the webhook on shutdown
    • A /webhook POST endpoint receives Telegram updates and feeds them
      into the aiogram dispatcher.
    • A /verify GET endpoint receives Zarinpal payment callbacks.
    • A /health, /ping, and / endpoint are available for uptime pings.

Usage:
    python bot.py   # starts FastAPI webhook server

Environment variables:
    BOT_TOKEN          — Telegram Bot API token
    ADMIN_IDS          — comma-separated Telegram user IDs
    DATABASE_URL       — PostgreSQL connection string (Neon.tech)
    WEBHOOK_HOST       — bind address (default 0.0.0.0)
    WEBHOOK_PORT       — bind port    (default 8443)
    WEBHOOK_BASE_URL   — public URL   (default https://hamrahsocial.ir)
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
from utils.emojis import get_pe

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
                    f"{get_pe('cross')} متاسفانه در پردازش درخواست شما مشکلی رخ داد.\n"
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


# ─── Webhook path constant ──────────────────────────────────────────
WEBHOOK_PATH = "/webhook"


# ─── Webhook registration helper ────────────────────────────────────

async def set_webhook_with_retry(
    bot: Bot,
    attempts: int = 5,
) -> None:
    """Register the Telegram webhook at ``WEBHOOK_BASE_URL`` + ``WEBHOOK_PATH``.

    Runs on every application startup. Retries transient network errors with
    exponential backoff and confirms registration via ``getWebhookInfo`` so
    the service never silently comes up with a missing/mismatched webhook.
    """
    url = f"{config.WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
    secret = config.WEBHOOK_SECRET or None
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            await bot.set_webhook(
                url=url,
                drop_pending_updates=False,  # keep updates that queued during downtime
                secret_token=secret,
            )
            info = await bot.get_webhook_info()
            if info.url != url:
                raise RuntimeError(
                    f"Telegram reports webhook {info.url!r}, expected {url!r}."
                )
            logger.info("Webhook set to: %s", url)
            return
        except Exception as exc:
            last_exc = exc
            logger.error(
                "Failed to set webhook %s (attempt %d/%d): %s",
                url, attempt, attempts, exc,
            )
            if attempt < attempts:
                await asyncio.sleep(2**attempt)

    raise RuntimeError(
        f"Could not set webhook {url} after {attempts} attempts. Last error: {last_exc}"
    )


# ─── FastAPI lifespan (webhook mode) ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start everything on startup and clean up on shutdown.

    Runs FastAPI for Telegram webhook, Zarinpal callbacks, and health checks.
    On startup: sets the webhook. On shutdown: deletes the webhook.
    """
    global bot, dp

    # ── 1. aiogram Bot ───────────────────────────────────────────────
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # ── 2. Register the webhook on Telegram ──────────────────────────
    # Done immediately after creating the bot, before DB/routers, so the
    # webhook is always (re)registered on every start — no more manual
    # curl after systemd restarts.
    await set_webhook_with_retry(bot)

    # ── 3. Background rate-fetcher ───────────────────────────────────
    from utils.cache import rate_cache
    rate_fetcher_task = asyncio.create_task(rate_cache.start(interval=300))
    logger.info(
        "Background rate-fetcher task started (PID-like: %s)",
        rate_fetcher_task.get_name(),
    )

    # ── 4. Non-blocking virtual-services prewarm ─────────────────────
    # Fetch the dynamic services map in the background so the first tap
    # on the virtual-number menu is instant. Runs as a task that never
    # blocks startup and can never crash the application lifecycle.
    from utils.shiznumber import warm_services_cache
    services_warm_task = asyncio.create_task(warm_services_cache())
    logger.info(
        "Virtual-services prewarm task started: %s",
        services_warm_task.get_name(),
    )

    # ── 5. Dispatcher + routers ──────────────────────────────────────
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Give the rate-cache background task a bot reference so it can alert
    # admins when the BrsApi rate fetch fails.
    rate_cache.set_bot(bot)

    dp.errors.register(global_error_handler)
    register_routers(dp)

    # ── 6. Database ──────────────────────────────────────────────────
    logger.info("Initializing database (PostgreSQL) …")
    await init_db()
    logger.info("Database ready.")

    yield  # ── FastAPI is now live, webhook is active ────────────────

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down …")

    # Delete the webhook (keep pending updates queued for the next start)
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook deleted.")

    # Cancel background tasks
    rate_cache.stop()
    rate_fetcher_task.cancel()
    services_warm_task.cancel()

    try:
        await rate_fetcher_task
    except asyncio.CancelledError:
        pass

    try:
        await services_warm_task
    except asyncio.CancelledError:
        pass

    await close_pool()
    await bot.session.close()
    logger.info("Shutdown complete.")


# ─── FastAPI application ─────────────────────────────────────────────
app = FastAPI(title="Telegram Bot Server", lifespan=lifespan)


# ─── Telegram Webhook endpoint ──────────────────────────────────────

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> JSONResponse:
    """Receive Telegram updates and feed them to the aiogram dispatcher."""
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})

    # Feed the update into the aiogram dispatcher
    await dp.feed_update(bot, update)

    return JSONResponse({"ok": True})


# ─── Zarinpal /verify endpoint ──────────────────────────────────────

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
    from utils.zarinpal import verify_payment, amounts_match

    payment = await get_payment_by_authority(Authority)
    if payment is None:
        logger.warning("No payment found for authority=%s", Authority)
        return HTMLResponse(
            _error_page("Payment record not found. Please return to the bot and click 'I paid'."),
            status_code=404,
        )

    if payment["status"] == "verified":
        return HTMLResponse(_success_page("Payment was already verified. You may close this window and return to the bot."))

    full_payment = await get_payment(payment["payment_id"])
    if full_payment is None:
        return HTMLResponse(
            _error_page("Payment record is incomplete. Please return to the bot."),
            status_code=409,
        )

    order_id = full_payment["order_id"]
    gateway_amount_irt = int(full_payment["payment_amount_irt"])

    if (
        full_payment["authority"] != Authority
        or full_payment["payment_status"] != "init"
        or full_payment["order_status"] != "pending"
        or gateway_amount_irt < 1
        or gateway_amount_irt > int(full_payment["order_amount_irt"])
    ):
        await fail_payment(full_payment["payment_id"])
        return HTMLResponse(
            _error_page("Payment data is invalid or has already been processed."),
            status_code=409,
        )

    # ── Verify with Zarinpal API ──────────────────────────────────
    # The amount sent to Zarinpal was the gateway amount frozen in the
    # payment record (an int). When the wallet covered part of the order,
    # this amount is SMALLER than the order total and must never be
    # recalculated from a live exchange rate or the order row.
    expected_amount = gateway_amount_irt
    logger.info(
        "Verifying authority=%s with frozen amount=%s (order #%s)",
        Authority, expected_amount, order_id,
    )
    result = await verify_payment(Authority, expected_amount)

    # Compare the gateway's returned amount against the DB-frozen int.
    # ``amounts_match`` also tolerates a 10x (Toman vs Rial) echo.
    # If Zarinpal did not return an amount, rely on the API code alone.
    if result.amount_irt is not None:
        amount_matches = amounts_match(expected_amount, int(result.amount_irt))
        if amount_matches and int(result.amount_irt) != expected_amount:
            logger.warning(
                "Amount unit drift for order #%s: DB=%s gateway=%s (treating 10x as match)",
                order_id, expected_amount, result.amount_irt,
            )
    else:
        amount_matches = True

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
    return JSONResponse({"status": "ok", "mode": "webhook"})


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
        "mode": "webhook",
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
