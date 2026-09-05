"""
FastAPI webhook server.

Routes:
    GET  /                → health check
    GET  /verify          → Zarinpal callback (browser redirect from payment page)
    GET  /admin/stats     → simple JSON order stats (optional, for monitoring)

Run standalone:
    uvicorn webhook.app:app --host 0.0.0.0 --port 8443

Or launch together with the bot via bot.py (webhook mode).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse

from config import config
from database.db import init_db

logger = logging.getLogger("webhook")

# ─── Lifespan ────────────────────────────────────────────────────────
# We need the aiogram Bot instance available in the verify route.
# It is injected at startup via `set_bot()`.

_bot = None


def set_bot(bot) -> None:
    """Called from bot.py before the server starts."""
    global _bot
    _bot = bot


def get_bot():
    return _bot


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Ensure DB is ready when the webhook server boots."""
    await init_db()
    logger.info("Webhook server: database ready.")
    yield
    logger.info("Webhook server shutting down.")


app = FastAPI(title="Zarinpal Webhook", lifespan=lifespan)


# ─── Routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return "<h2>✅ Zarinpal webhook server is running.</h2>"


@app.get("/verify")
async def zarinpal_verify(
    Authority: str = Query(..., description="Zarinpal authority token"),
    Status: str = Query(..., description="Payment status from Zarinpal"),
):
    """
    Zarinpal redirects the user's browser here after payment.

    Query params (set by Zarinpal):
        Authority  – payment authority token
        Status     – "OK" if user approved, else "NOK"
    """
    import asyncio

    # ── Quick checks ──────────────────────────────────────────────
    if Status != "OK":
        return HTMLResponse(
            _error_page("Payment was cancelled or failed. You may close this window."),
            status_code=400,
        )

    bot = get_bot()
    if bot is None:
        logger.error("Bot instance not available in webhook")
        return HTMLResponse(
            _error_page("Server is restarting. Please return to the bot and click 'I paid'."),
            status_code=503,
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
    from utils.delivery import deliver_product

    payment = await get_payment_by_authority(Authority)
    if payment is None:
        logger.warning("No payment found for authority=%s", Authority)
        return HTMLResponse(
            _error_page("Payment record not found. Please return to the bot and click 'I paid'."),
            status_code=404,
        )

    if payment["status"] == "verified":
        # Already processed (e.g. user refreshed the page)
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
        return HTMLResponse(
            _success_page("Payment was already verified. You may close this window."),
        )

    logger.info("Webhook verified order #%s — ref_id=%s", order_id, result.ref_id)

    # ── Delivery (in background so the HTTP response is fast) ─
    order = await get_order(order_id)
    if order:
        asyncio.create_task(
            _background_delivery(bot, order_id, order["user_id"], order["product"], order["details"])
        )

    return HTMLResponse(
        _success_page(
            f"✅ Payment verified successfully!\n\n"
            f"Ref ID: {result.ref_id}\n\n"
            "Return to the Telegram bot — your product is being delivered."
        ),
    )


async def _background_delivery(bot, order_id: int, user_id: int, product: str, details: str) -> None:
    """Run delivery in the background without blocking the HTTP response."""
    from utils.delivery import deliver_product
    try:
        await deliver_product(bot, user_id, order_id, product, details)
    except Exception as exc:
        logger.exception("Background delivery failed for order #%s: %s", order_id, exc)


# ─── Admin stats endpoint (optional) ────────────────────────────────

@app.get("/admin/stats")
async def admin_stats():
    from database.db import get_pool
    pool = await get_pool()

    pending = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM orders WHERE status = $1", "pending",
    )
    paid = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM orders WHERE status = $1", "paid",
    )
    delivered = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM orders WHERE status = $1", "delivered",
    )
    total_revenue = await pool.fetchrow(
        "SELECT COALESCE(SUM(amount_irt), 0) AS total FROM orders WHERE status IN ($1, $2)",
        "paid", "delivered",
    )

    return JSONResponse({
        "pending_orders": pending["cnt"] if pending else 0,
        "paid_orders": paid["cnt"] if paid else 0,
        "delivered_orders": delivered["cnt"] if delivered else 0,
        "total_revenue_irr": total_revenue["total"] if total_revenue else 0,
    })


# ─── HTML pages ──────────────────────────────────────────────────────

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
