"""
Shared product delivery logic.

Called by:
  • handlers/payment.py   (manual "پرداخت کردم" button flow)
  • bot.py /verify         (automatic Zarinpal callback flow)

Both paths converge here so the delivery logic is never duplicated.
All user-facing text in Persian (فارسی).
"""

import asyncio
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
        if "شارژ کیف پول" in product:
            await _deliver_wallet_recharge(bot, user_id, order_id, product, details)
        elif "شماره مجازی" in product or "virtual" in product.lower():
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


async def _deliver_wallet_recharge(
    bot: Bot, user_id: int, order_id: int, product: str, details: str
) -> None:
    """Deliver wallet recharge — add the paid amount to the user's wallet."""
    from database.db import add_to_wallet, get_order

    order = await get_order(order_id)
    if not order:
        logger.error("Wallet recharge delivery failed: order #%s not found", order_id)
        return

    amount = order["amount_irt"]
    if amount <= 0:
        logger.error("Wallet recharge delivery failed: invalid amount for order #%s", order_id)
        return

    await add_to_wallet(user_id, amount)

    from database.db import get_wallet_balance
    new_balance = await get_wallet_balance(user_id)
    amount_str = f"{amount:,}".replace(",", "،")
    balance_str = f"{new_balance:,}".replace(",", "،")

    await _safe_send(
        bot,
        user_id,
        f"{get_pe('check')} <b>پرداخت موفق!</b>\n\n"
        f"{get_pe('purse')} <b>کیف پول شما شارژ شد!</b>\n\n"
        f"{get_pe('money')} مبلغ شارژ: <b>{amount_str} تومان</b>\n"
        f"{get_pe('purse')} موجودی فعلی: <b>{balance_str} تومان</b>\n\n"
        f"{get_pe('sparkles')} از خرید شما متشکریم!",
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
    bot: Bot, user_id: int, order_id: int, product_name: str, details: str
) -> None:
    """Deliver a purchased virtual number from Shiznumber — with auto-refund.

    Called ONLY after the user has paid (Zarinpal gateway or bot wallet).
    First attempts a real purchase on Shiznumber; if that fails, the full
    ``amount_irt`` is refunded back to the user's wallet and both the user
    and the admins are notified. The bot never keeps money for a number
    it could not deliver.

    On success the number is sent to the user and a background task polls
    the API for the SMS verification code every 5 seconds.

    ``details`` format: "سرویس: {slug} | آیتم: {item_id}"
    """
    import re

    from utils.shiznumber import order_virtual_number
    from database.db import update_order_status, add_to_wallet, get_user_orders

    # Extract item_id from details (e.g. "سرویس: telegram | آیتم: 57172")
    match = re.search(r"آیتم:\s*(\d+)", details)
    if not match:
        logger.error(
            "Virtual delivery: could not parse item_id from details='%s' (order #%s)",
            details, order_id,
        )
        return
    item_id = match.group(1)

    # Attempt actual API purchase
    api_order = await order_virtual_number(item_id)

    if not api_order:
        # PURCHASE FAILED — INITIATE AUTO-REFUND
        await update_order_status(order_id, "cancelled")

        # Get the order to find the exact final price paid
        orders = await get_user_orders(user_id)
        current_order = next((o for o in orders if o["order_id"] == order_id), None)

        if current_order and current_order.get("amount_irt"):
            refund_amount = current_order["amount_irt"]
            await add_to_wallet(user_id, refund_amount)

            from keyboards.inline import back_to_menu_kb
            await bot.send_message(
                user_id,
                f"❌ <b>خطا در دریافت شماره!</b>\n\n"
                f"متاسفانه در لحظه خرید شما، موجودی این شماره در سرور به پایان رسید یا خطایی رخ داد.\n"
                f"✅ مبلغ <b>{refund_amount:,} تومان</b> کاملاً به کیف پول شما در ربات بازگشت داده شد.",
                reply_markup=back_to_menu_kb()
            )

            # Notify Admins
            from config import config
            for admin in config.ADMIN_IDS:
                try:
                    await bot.send_message(admin, f"🚨 <b>کنسلی خودکار سفارش {order_id}</b>\nمبلغ {refund_amount:,} تومان به کیف پول کاربر {user_id} برگشت داده شد. (خطای API شیزنامبر)")
                except Exception:
                    pass
        return

    # PURCHASE SUCCESSFUL
    await update_order_status(order_id, "delivered")
    api_order_id = api_order.get("id")
    number = api_order.get("ordered_number")

    # Send the number to the user and initiate a background task that polls
    # the API every 5 seconds for the SMS verification code.
    await _safe_send(
        bot,
        user_id,
        f"{get_pe('sparkles')} <b>پرداخت موفق!</b>\n\n"
        f"{get_pe('key_lock')} <b>شماره مجازی شما:</b>\n"
        f"📱 شماره: <code>{number}</code>\n\n"
        "در حال دریافت کد تأیید... لطفاً صبر کنید.\n"
        "<i>حداکثر ۲ دقیقه زمان می‌برد.</i>",
    )
    asyncio.create_task(
        _poll_sms_code(bot, user_id, order_id, number, api_order_id)
    )


async def _poll_sms_code(
    bot: Bot, user_id: int, order_id: int, number: str, api_order_id: str
) -> None:
    """Background task — poll Shiznumber every 5s (up to 2 minutes) for the SMS code."""
    code = None
    try:
        from utils.shiznumber import get_number_code

        for _ in range(24):  # 24 × 5s = 120s
            await asyncio.sleep(5)
            try:
                result = await asyncio.wait_for(
                    get_number_code(str(api_order_id)), timeout=15
                )
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.warning(
                    "SMS code poll request failed (order #%s): %s", order_id, exc,
                )
                continue

            if not result:
                continue
            if result.get("code"):
                code = result.get("code", "")
                break
            if result.get("status") not in ("waiting", "wait_code", "", None):
                break
    except Exception as exc:
        logger.warning("SMS code polling task crashed (order #%s): %s", order_id, exc)

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
        # Code not received within timeout — alert the user and the admins.
        await _alert_delivery_failure(
            bot, user_id, order_id, "شماره مجازی",
            "کد تأیید ظرف ۲ دقیقه دریافت نشد",
            extra_info=f"شماره: {number}\nشناسه سفارش: {api_order_id}",
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
