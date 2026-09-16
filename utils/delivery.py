"""
Shared product delivery logic.

Called by:
  • handlers/payment.py   (manual "پرداخت کردم" button flow)
  • bot.py /verify         (automatic Zarinpal callback flow)

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
from keyboards.inline import back_to_menu_kb
from utils.emojis import get_pe

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
        if "شماره مجازی" in product or "virtual" in product.lower():
            await _deliver_virtual_number(bot, user_id, order_id, product, details)
        elif "ChatGPT" in product or "Gemini" in product:
            await _deliver_ai_account(bot, user_id, order_id, product)
        elif "طراحی" in product or "Design" in product:
            await _deliver_design(bot, user_id, order_id, product, details)
        else:
            await _deliver_generic(bot, user_id, order_id, product)
    except Exception as exc:
        logger.exception("Delivery failed for order #%s: %s", order_id, exc)
        await _safe_send(
            bot,
            user_id,
            f"{get_pe('warning')} خطایی در تحویل خودکار رخ داد.\n"
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
            f"{get_pe('sparkles')} <b>پرداخت موفق!</b>\n\n"
            f"{get_pe('bot')} <b>اطلاعات ورود {product}:</b>\n\n"
            f"{get_pe('email_icon')} ایمیل: <code>{acc['email']}</code>\n"
            f"{get_pe('key_icon')} رمز عبور: <code>{acc['password']}</code>\n\n"
            f"{get_pe('warning')} لطفاً پس از ورود رمز عبور را تغییر دهید.\n"
            "برای پشتیبانی با @admin تماس بگیرید.",
        )
    else:
        await _safe_send(
            bot,
            user_id,
            f"{get_pe('check')} پرداخت موفق!\n\n"
            f"{get_pe('warning')} در حال حاضر اطلاعات ورود موجود نیست. "
            f"مدیر ما {product} شما را به زودی تحویل خواهد داد.",
        )


async def _deliver_design(
    bot: Bot, user_id: int, order_id: int, product: str, details: str
) -> None:
    await _safe_send(
        bot,
        user_id,
        f"{get_pe('sparkles')} <b>پرداخت موفق!</b>\n\n"
        f"{get_pe('fire')} درخواست طراحی شما ثبت شد!\n"
        "تیم طراحی ما درخواست شما را بررسی کرده و به زودی با شما تماس خواهد گرفت.",
    )

    # Notify admins
    order = await get_order(order_id)
    if order:
        admin_msg = (
            f"{get_pe('fire')} <b>سفارش طراحی جدید #{order['order_id']}</b>\n\n"
            f"{get_pe('user')} کاربر: <code>{order['user_id']}</code>\n"
            f"{get_pe('note')} جزئیات:\n{order['details']}\n\n"
            f"{get_pe('money')} مبلغ: {order['amount_irt']:,} تومان\n"
            "لطفاً این سفارش را پردازش کنید."
        )
        await _notify_admins(bot, admin_msg)


async def _deliver_virtual_number(
    bot: Bot, user_id: int, order_id: int, product: str, details: str
) -> None:
    """Deliver a virtual number — call Shiznumber API to purchase the number,
    then poll for the SMS code and send it to the user.

    If the Shiznumber API fails AFTER payment, alert the admin immediately.

    ``details`` format: "سرویس: {slug} | آیتم: {item_id}"
    """
    import asyncio
    from utils.shiznumber import buy_virtual_number, get_number_code

    # Parse slug and item_id from details
    slug = None
    item_id = None
    if "سرویس:" in details and "|" in details:
        try:
            slug = details.split("|")[0].split("سرویس:")[1].strip()
            item_id = details.split("|")[1].split("آیتم:")[1].strip()
        except (ValueError, IndexError):
            pass

    if not slug or not item_id:
        await _alert_delivery_failure(bot, user_id, order_id, product,
                                      "شناسه سرویس یا آیتم یافت نشد")
        return

    # Step 1: Purchase the number from Shiznumber
    result = await buy_virtual_number(item_id)

    if not result or result.get("error"):
        error_msg = result.get("error", "خطای ناشناخته") if result else "خطا در اتصال"
        await _alert_delivery_failure(bot, user_id, order_id, product, error_msg)
        return

    shiz_order_id = result.get("order_id", result.get("id", ""))
    number = result.get("number", "نامشخص")

    # Step 2: Send the number to the user
    await _safe_send(
        bot,
        user_id,
        f"{get_pe('sparkles')} <b>پرداخت موفق!</b>\n\n"
        f"{get_pe('key_lock')} <b>شماره مجازی شما:</b>\n"
        f"📱 شماره: <code>{number}</code>\n"
        f"🌍 سرویس: {slug}\n\n"
        "در حال دریافت کد تأیید... لطفاً صبر کنید.\n"
        "<i>حداکثر ۲ دقیقه زمان می‌برد.</i>",
    )

    # Step 3: Poll for the SMS code (up to 2 minutes, every 5 seconds)
    code = None
    for attempt in range(24):  # 24 × 5s = 120s
        await asyncio.sleep(5)
        code_result = await get_number_code(str(shiz_order_id))

        if code_result and code_result.get("code"):
            code = code_result.get("code", "")
            break

        if code_result and code_result.get("status") not in ("waiting", "wait_code", ""):
            # Non-retryable error
            error_code = code_result.get("error", code_result.get("status", "خطا"))
            await _alert_delivery_failure(bot, user_id, order_id, product, error_code)
            return

    if code:
        await _safe_send(
            bot,
            user_id,
            f"{get_pe('check')} <b>کد تأیید دریافت شد!</b>\n\n"
            f"📱 شماره: <code>{number}</code>\n"
            f"🔑 کد تأیید: <code>{code}</code>\n\n"
            "از این کد برای فعال‌سازی حساب خود استفاده کنید.\n"
            f"{get_pe('warning')} این کد محرمانه است، آن را با کسی به اشتراک نگذارید.",
        )
    else:
        # Code not received within timeout
        await _alert_delivery_failure(
            bot, user_id, order_id, product,
            "کد تأیید ظرف ۲ دقیقه دریافت نشد",
            extra_info=f"شماره: {number}\nشناسه سفارش Shiznumber: {shiz_order_id}",
        )


async def _deliver_generic(bot: Bot, user_id: int, order_id: int, product: str) -> None:
    await _safe_send(
        bot,
        user_id,
        f"{get_pe('sparkles')} <b>پرداخت موفق!</b>\n\n"
        f"سفارش <b>{product}</b> شما تأیید شد.\n\n"
        "فعال‌سازی اشتراک‌های پرمیوم به زودی انجام خواهد شد.\n"
        "برای پشتیبانی با @admin تماس بگیرید.",
    )

    order = await get_order(order_id)
    if order:
        admin_msg = (
            f"{get_pe('money')} <b>سفارش پرداخت شده #{order['order_id']}</b>\n\n"
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


async def _alert_delivery_failure(
    bot: Bot,
    user_id: int,
    order_id: int,
    product: str,
    error_msg: str,
    extra_info: str = "",
) -> None:
    """Alert both the user and admin when Shiznumber delivery fails.

    The user is told their payment succeeded but delivery had an issue.
    The admin receives full transaction details for manual resolution.
    """
    from database.db import get_order

    # 1. Notify the user
    await _safe_send(
        bot,
        user_id,
        f"{get_pe('warning')} <b>پرداخت شما موفق بود اما در تحویل خودکار مشکلی پیش آمد.</b>\n\n"
        f"تیکت شما برای پشتیبانی ارسال شد و اکانت به زودی تحویل می‌گردد.\n\n"
        f"{get_pe('ticket')} شماره سفارش: <code>#{order_id}</code>\n"
        f"{get_pe('call')} لطفاً منتظر پاسخ پشتیبانی باشید.",
    )

    # 2. Notify all admins with full details
    order = await get_order(order_id)
    order_info = ""
    if order:
        order_info = (
            f"{get_pe('box')} شماره سفارش: #{order['order_id']}\n"
            f"{get_pe('user')} کاربر: <code>{order['user_id']}</code>\n"
            f"{get_pe('shopping')} محصول: {order['product']}\n"
            f"{get_pe('note')} جزئیات: {order['details']}\n"
            f"{get_pe('money')} مبلغ: {order['amount_irt']:,} تومان\n"
        )

    admin_msg = (
        f"{get_pe('cross')} <b>خطا در تحویل خودکار سفارش #{order_id}</b>\n\n"
        f"{order_info}\n"
        f"{get_pe('warning')} خطا: {error_msg}\n"
    )
    if extra_info:
        admin_msg += f"\n{get_pe('note')} اطلاعات اضافی:\n{extra_info}\n"

    admin_msg += (
        f"\n{get_pe('call')} لطفاً سفارش را به صورت دستی پردازش کنید."
    )

    await _notify_admins(bot, admin_msg)
    logger.warning(
        "Shiznumber delivery failure for order #%s (user %s): %s",
        order_id, user_id, error_msg,
    )
