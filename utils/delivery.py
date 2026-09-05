"""
Shared product delivery logic.

Called by:
  • handlers/payment.py   (manual "پرداخت کردم" button flow)
  • webhook/verify.py     (automatic Zarinpal callback flow)

Both paths converge here so the delivery logic is never duplicated.
All user-facing text in Persian (فارسی).
"""

import logging
import random
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import config
from database.db import get_order
from utils.virtual_api import fetch_virtual_number
from keyboards.inline import back_to_menu_kb

logger = logging.getLogger(__name__)


# ─── Public API ──────────────────────────────────────────────────────

async def deliver_product(
    bot: Bot,
    user_id: int,
    order_id: int,
    product: str,
    details: str = "",
    extra: Optional[dict] = None,
) -> None:
    """Deliver the purchased product to *user_id*."""
    extra = extra or {}

    try:
        if "ChatGPT" in product or "Gemini" in product:
            await _deliver_ai_account(bot, user_id, order_id, product)
        elif "شماره مجازی" in product or "Virtual Number" in product:
            await _deliver_virtual_number(bot, user_id, order_id, product, extra)
        elif "طراحی" in product or "Design" in product:
            await _deliver_design(bot, user_id, order_id, product, details)
        else:
            await _deliver_generic(bot, user_id, order_id, product)
    except Exception as exc:
        logger.exception("Delivery failed for order #%s: %s", order_id, exc)
        await _safe_send(
            bot,
            user_id,
            "⚠️ خطایی در تحویل خودکار رخ داد.\n"
            "مدیر ما به زودی سفارش شما را پردازش خواهد کرد.",
        )


# ─── Delivery strategies ────────────────────────────────────────────

async def _deliver_ai_account(bot: Bot, user_id: int, order_id: int, product: str) -> None:
    platform = "chatgpt" if "ChatGPT" in product else "gemini"
    accounts = config.AI_ACCOUNTS.get(platform, [])

    if accounts:
        acc = random.choice(accounts)
        await _safe_send(
            bot,
            user_id,
            f"🎉 <b>پرداخت موفق!</b>\n\n"
            f"🤖 <b>اطلاعات ورود {product}:</b>\n\n"
            f"📧 ایمیل: <code>{acc['email']}</code>\n"
            f"🔑 رمز عبور: <code>{acc['password']}</code>\n\n"
            "⚠️ لطفاً پس از ورود رمز عبور را تغییر دهید.\n"
            "برای پشتیبانی با @admin تماس بگیرید.",
        )
    else:
        await _safe_send(
            bot,
            user_id,
            f"✅ پرداخت موفق!\n\n"
            f"⚠️ در حال حاضر اطلاعات ورود موجود نیست. "
            f"مدیر ما {product} شما را به زودی تحویل خواهد داد.",
        )


async def _deliver_virtual_number(
    bot: Bot, user_id: int, order_id: int, product: str, extra: dict
) -> None:
    country = extra.get("country", "iran")
    result = await fetch_virtual_number(country)

    if result.success:
        await _safe_send(
            bot,
            user_id,
            f"🎉 <b>پرداخت موفق!</b>\n\n"
            f"📱 شماره مجازی شما ({result.country}):\n"
            f"<code>{result.number}</code>\n\n"
            "از این شماره برای تأیید هویت استفاده کنید.",
        )
    else:
        await _safe_send(
            bot,
            user_id,
            f"✅ پرداخت موفق!\n\n"
            f"⚠️ دریافت شماره در حال حاضر ممکن نیست: {result.message}\n"
            "مدیر ما آن را به زودی تحویل خواهد داد.",
        )


async def _deliver_design(
    bot: Bot, user_id: int, order_id: int, product: str, details: str
) -> None:
    await _safe_send(
        bot,
        user_id,
        "🎉 <b>پرداخت موفق!</b>\n\n"
        "🎨 درخواست طراحی شما ثبت شد!\n"
        "تیم طراحی ما درخواست شما را بررسی کرده و به زودی با شما تماس خواهد گرفت.",
    )

    # Notify admins
    order = await get_order(order_id)
    if order:
        admin_msg = (
            f"🎨 <b>سفارش طراحی جدید #{order['order_id']}</b>\n\n"
            f"👤 کاربر: <code>{order['user_id']}</code>\n"
            f"📝 جزئیات:\n{order['details']}\n\n"
            f"💰 مبلغ: {order['amount_irt']:,} تومان\n"
            "لطفاً این سفارش را پردازش کنید."
        )
        await _notify_admins(bot, admin_msg)


async def _deliver_generic(bot: Bot, user_id: int, order_id: int, product: str) -> None:
    await _safe_send(
        bot,
        user_id,
        f"🎉 <b>پرداخت موفق!</b>\n\n"
        f"سفارش <b>{product}</b> شما تأیید شد.\n\n"
        "فعال‌سازی اشتراک‌های پرمیوم به زودی انجام خواهد شد.\n"
        "برای پشتیبانی با @admin تماس بگیرید.",
    )

    order = await get_order(order_id)
    if order:
        admin_msg = (
            f"💰 <b>سفارش پرداخت شده #{order['order_id']}</b>\n\n"
            f"محصول: {order['product']}\n"
            f"جزئیات: {order['details']}\n"
            f"مبلغ: {order['amount_irt']:,} تومان\n"
            f"کاربر: <code>{order['user_id']}</code>\n\n"
            "لطفاً این سفارش را پردازش کنید."
        )
        await _notify_admins(bot, admin_msg)


# ─── Helpers ─────────────────────────────────────────────────────────

async def _safe_send(bot: Bot, user_id: int, text: str) -> None:
    """Send a message, silently swallowing Telegram API errors."""
    try:
        await bot.send_message(user_id, text)
    except Exception as exc:
        logger.warning("Could not send message to %s: %s", user_id, exc)


async def _notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.ADMIN_IDS:
        await _safe_send(bot, admin_id, text)
