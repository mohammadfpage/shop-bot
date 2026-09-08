"""
Handler: Telegram Stars & Gifts purchase workflows.

Standard Stars (buy_stars):
    enter_quantity (min 50) → choose_target → [enter_other_id] → payment

Stars Gifts (buy_stars_gift):
    choose_package → payment → gift link delivery

All user-facing text in Persian (فارسی).
"""

import contextlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from states.states import TelegramStarsStates, TelegramStarsGiftStates
from utils.pricing import price_display, price_display_raw
from utils.zarinpal import request_payment
from utils.emojis import get_pe
from database.db import create_order, create_payment, update_payment_authority, get_price_or_default
from keyboards.inline import (
    stars_target_kb,
    stars_gift_items_kb,
    pay_link_kb,
    back_to_menu_kb,
    main_menu_kb,
)

router = Router(name="stars")

MIN_STARS = 50


# ══════════════════════════════════════════════════════════════════════
#  STANDARD STARS (Custom Quantity)
# ══════════════════════════════════════════════════════════════════════

# ─── Gateway: Enter stars menu ───────────────────────────────────────

@router.callback_query(F.data == "menu:stars")
async def cb_enter_stars_state(callback: CallbackQuery, state: FSMContext) -> None:
    """Set state so the next text message is captured for star quantity."""
    await callback.answer()
    await state.set_state(TelegramStarsStates.enter_quantity)
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('star_gift')} <b>خرید استارز تلگرام</b>\n\n"
            "چه تعداد استارز می‌خواهید؟\n"
            "<i>حداقل: ۵۰ استارز</i>\n\n"
            "تعداد را به صورت پیام ارسال کنید (مثال: <code>100</code>).",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── Back to stars menu ─────────────────────────────────────────────

@router.callback_query(F.data == "stars:back")
async def cb_stars_back(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('star_gift')} <b>خرید استارز تلگرام</b>\n\n"
            "چه تعداد استارز می‌خواهید؟\n"
            "<i>حداقل: ۵۰ استارز</i>\n\n"
            "تعداد را به صورت پیام ارسال کنید.",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── Enter quantity ──────────────────────────────────────────────────

@router.message(TelegramStarsStates.enter_quantity)
async def msg_stars_quantity(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit() or int(text) < MIN_STARS:
        await message.answer(
            f"⚠️ لطفاً عددی بزرگتر یا مساوی {MIN_STARS} ارسال کنید.",
            reply_markup=back_to_menu_kb(),
        )
        return

    qty = int(text)
    per_50_usd = await get_price_or_default("telegram_stars_per_50")
    usd_price = (qty / 50) * per_50_usd
    price_str = await price_display(usd_price)

    await state.update_data(stars_qty=qty, product_usd=usd_price)
    await state.set_state(TelegramStarsStates.choose_target)

    await message.answer(
        f"{get_pe('star_gift')} <b>{qty} استارز تلگرام</b>\n\n"
        f"{get_pe('money')} قیمت: <b>{price_str}</b>\n\n"
        "این استارزها برای چه کسی است؟",
        reply_markup=stars_target_kb(),
    )


# ─── Choose target ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("stars:target:"), TelegramStarsStates.choose_target)
async def cb_stars_target(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    target = callback.data.split(":")[2]

    if target == "self":
        await state.update_data(target_user=callback.from_user.id, target_label="خودم")
        await _stars_payment(callback, state)
    else:
        await state.set_state(TelegramStarsStates.enter_other_id)
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('users')} لطفاً <b>شناسه کاربری تلگرام</b> دریافت‌کننده را ارسال کنید.\n"
            "(فقط شناسه عددی — مثال: <code>123456789</code>)",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


@router.message(TelegramStarsStates.enter_other_id)
async def msg_stars_other_id(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("⚠️ لطفاً یک شناسه عددی معتبر ارسال کنید.", reply_markup=back_to_menu_kb())
        return

    target_id = int(text)
    await state.update_data(target_user=target_id, target_label=f"شناسه {target_id}")
    await _stars_payment_msg(message, state)


# ─── Payment (callback path) ────────────────────────────────────────

async def _stars_payment(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    qty = data["stars_qty"]
    usd = data["product_usd"]
    target_label = data["target_label"]

    final_irt, rate = await price_display_raw(usd)

    order_id = await create_order(
        user_id=callback.from_user.id,
        product=f"استارز تلگرام ×{qty}",
        details=f"دریافت‌کننده: {target_label}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"{qty} استارز تلگرام برای {target_label}",
    )

    if not result.success or not result.authority:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"❌ درخواست پرداخت ناموفق بود:\n{result.message}",
                reply_markup=back_to_menu_kb(),
            )
        await state.clear()
        return

    payment_id = await create_payment(order_id, final_irt)
    await update_payment_authority(payment_id, result.authority)
    await state.update_data(order_id=order_id, payment_id=payment_id, authority=result.authority, amount_irt=final_irt)
    await state.set_state(TelegramStarsStates.payment)

    rate_str = f"{rate:,.0f}".replace(",", "،")
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('card')} <b>پرداخت: {qty} استارز تلگرام</b>\n\n"
            f"{get_pe('user')} دریافت‌کننده: {target_label}\n"
            f"{get_pe('exchange')} نرخ ارز: ۱ دلار = {rate_str} تومان\n"
            f"{get_pe('money')} مبلغ کل: <b>{final_irt:,} تومان</b>\n\n"
            "برای پرداخت روی دکمه زیر کلیک کنید:",
            reply_markup=pay_link_kb(result.start_pay_url),
        )


# ─── Payment (message path) ─────────────────────────────────────────

async def _stars_payment_msg(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    qty = data["stars_qty"]
    usd = data["product_usd"]
    target_label = data["target_label"]

    final_irt, rate = await price_display_raw(usd)

    order_id = await create_order(
        user_id=message.from_user.id,
        product=f"استارز تلگرام ×{qty}",
        details=f"دریافت‌کننده: {target_label}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"{qty} استارز تلگرام برای {target_label}",
    )

    if not result.success or not result.authority:
        await message.answer(
            f"❌ درخواست پرداخت ناموفق بود:\n{result.message}",
            reply_markup=back_to_menu_kb(),
        )
        await state.clear()
        return

    payment_id = await create_payment(order_id, final_irt)
    await update_payment_authority(payment_id, result.authority)
    await state.update_data(order_id=order_id, payment_id=payment_id, authority=result.authority, amount_irt=final_irt)
    await state.set_state(TelegramStarsStates.payment)

    rate_str = f"{rate:,.0f}".replace(",", "،")
    await message.answer(
        f"{get_pe('card')} <b>پرداخت: {qty} استارز تلگرام</b>\n\n"
        f"{get_pe('user')} دریافت‌کننده: {target_label}\n"
        f"{get_pe('exchange')} نرخ ارز: ۱ دلار = {rate_str} تومان\n"
        f"{get_pe('money')} مبلغ کل: <b>{final_irt:,} تومان</b>\n\n"
        "برای پرداخت روی دکمه زیر کلیک کنید:",
        reply_markup=pay_link_kb(result.start_pay_url),
    )


# ══════════════════════════════════════════════════════════════════════
#  STARS GIFTS (Fixed Packages)
# ══════════════════════════════════════════════════════════════════════

# Mapping from product_key to stars count (for order details)
_GIFT_STARS_MAP: dict[str, int] = {
    "stars_gift_heart_15": 15,
    "stars_gift_bear_50": 50,
    "stars_gift_present_25": 25,
    "stars_gift_phone_25": 25,
    "stars_gift_cake_50": 50,
    "stars_gift_flower_50": 50,
    "stars_gift_champagne_50": 50,
    "stars_gift_rocket_50": 50,
    "stars_gift_ribbon_100": 100,
    "stars_gift_ring_100": 100,
    "stars_gift_diamond_100": 100,
}

# Mapping from product_key to emoji (for order details)
_GIFT_EMOJI_MAP: dict[str, str] = {
    "stars_gift_heart_15": "💖",
    "stars_gift_bear_50": "🧸",
    "stars_gift_present_25": "🎁",
    "stars_gift_phone_25": "📱",
    "stars_gift_cake_50": "🎂",
    "stars_gift_flower_50": "🌷",
    "stars_gift_champagne_50": "🍾",
    "stars_gift_rocket_50": "🚀",
    "stars_gift_ribbon_100": "💝",
    "stars_gift_ring_100": "💍",
    "stars_gift_diamond_100": "💎",
}


@router.callback_query(F.data == "menu:stars_gift")
async def cb_enter_stars_gift(callback: CallbackQuery, state: FSMContext) -> None:
    """Show the individual stars gifts grid."""
    await callback.answer()
    await state.set_state(TelegramStarsGiftStates.choose_package)
    kb = await stars_gift_items_kb()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('gift')} <b>گیفت‌های استارز تلگرام</b>\n\n"
            "یک گیفت را انتخاب کنید:\n"
            "<i>لینک هدیه پس از پرداخت برای شما ارسال می‌شود.</i>",
            reply_markup=kb,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("stars_gift:item:"), TelegramStarsGiftStates.choose_package)
async def cb_stars_gift_item(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle individual gift item selection and initiate payment."""
    await callback.answer()
    product_key = callback.data.split(":", 2)[2]

    stars_count = _GIFT_STARS_MAP.get(product_key)
    if not stars_count:
        await callback.answer("⚠️ گیفت نامعتبر.", show_alert=True)
        return

    emoji = _GIFT_EMOJI_MAP.get(product_key, "🎁")

    usd_price = await get_price_or_default(product_key)
    final_irt, rate = await price_display_raw(usd_price)

    order_id = await create_order(
        user_id=callback.from_user.id,
        product=f"گیفت استارز {emoji} ×{stars_count}",
        details=f"لینک هدیه — {stars_count} استارز — {product_key}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"گیفت {stars_count} استارز تلگرام {emoji}",
    )

    if not result.success or not result.authority:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"❌ درخواست پرداخت ناموفق بود:\n{result.message}",
                reply_markup=back_to_menu_kb(),
            )
        await state.clear()
        return

    payment_id = await create_payment(order_id, final_irt)
    await update_payment_authority(payment_id, result.authority)
    await state.update_data(
        order_id=order_id,
        payment_id=payment_id,
        authority=result.authority,
        amount_irt=final_irt,
        stars_qty=stars_count,
    )
    await state.set_state(TelegramStarsGiftStates.payment)

    rate_str = f"{rate:,.0f}".replace(",", "،")
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('card')} <b>پرداخت: گیفت {emoji} {stars_count} استارز</b>\n\n"
            f"{get_pe('exchange')} نرخ ارز: ۱ دلار = {rate_str} تومان\n"
            f"{get_pe('money')} مبلغ کل: <b>{final_irt:,} تومان</b>\n\n"
            "برای پرداخت روی دکمه زیر کلیک کنید:",
            reply_markup=pay_link_kb(result.start_pay_url),
        )

    await callback.answer()


@router.callback_query(F.data == "stars_gift:back")
async def cb_stars_gift_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to gift item selection."""
    await callback.answer()
    await state.set_state(TelegramStarsGiftStates.choose_package)
    kb = await stars_gift_items_kb()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('gift')} <b>گیفت‌های استارز تلگرام</b>\n\n"
            "یک گیفت را انتخاب کنید:\n"
            "<i>لینک هدیه پس از پرداخت برای شما ارسال می‌شود.</i>",
            reply_markup=kb,
        )
    await callback.answer()
