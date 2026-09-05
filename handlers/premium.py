"""
Handler: Telegram Premium subscription purchase workflow.
Flow: choose_duration → choose_target → [enter_other_id] → payment
All user-facing text in Persian (فارسی).
"""

import contextlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from states.states import TelegramPremiumStates
from utils.pricing import price_display, price_display_raw
from utils.zarinpal import request_payment
from database.db import create_order, update_order_amount, create_payment, update_payment_authority, get_price_or_default
from keyboards.inline import (
    premium_duration_kb,
    premium_target_kb,
    pay_link_kb,
    back_to_menu_kb,
)

router = Router(name="premium")

# Labels (Persian)
_DURATION_LABELS = {
    "monthly": "تلگرام پرمیوم — ماهانه",
    "quarterly": "تلگرام پرمیوم — سه‌ماهه",
    "semi_annual": "تلگرام پرمیوم — شش‌ماهه",
    "yearly": "تلگرام پرمیوم — سالانه",
}

_DURATION_KEYS = {
    "monthly": "telegram_premium_monthly",
    "quarterly": "telegram_premium_quarterly",
    "semi_annual": "telegram_premium_semi_annual",
    "yearly": "telegram_premium_yearly",
}


# ─── Back to premium menu ────────────────────────────────────────────

@router.callback_query(F.data.startswith("premium:back"))
async def cb_premium_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "⭐ <b>تلگرام پرمیوم</b>\nیک پلن اشتراک را انتخاب کنید:",
            reply_markup=premium_duration_kb(),
        )
    await callback.answer()


# ─── Choose duration ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("premium:") & ~F.data.startswith("premium:target:") & ~F.data.startswith("premium:back"))
async def cb_choose_duration(callback: CallbackQuery, state: FSMContext) -> None:
    duration = callback.data.split(":")[1]
    if duration not in _DURATION_LABELS:
        await callback.answer("گزینه نامعتبر", show_alert=True)
        return

    label = _DURATION_LABELS[duration]
    product_key = _DURATION_KEYS[duration]
    usd = await get_price_or_default(product_key)
    price_str = await price_display(usd)

    await state.update_data(product=label, product_usd=usd)
    await state.set_state(TelegramPremiumStates.choose_target)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"⭐ <b>{label}</b>\n\n"
            f"💰 قیمت: <b>{price_str}</b>\n\n"
            "این اشتراک برای چه کسی است؟",
            reply_markup=premium_target_kb(),
        )
    await callback.answer()


# ─── Choose target ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("premium:target:"), TelegramPremiumStates.choose_target)
async def cb_choose_target(callback: CallbackQuery, state: FSMContext) -> None:
    target = callback.data.split(":")[2]

    if target == "self":
        await state.update_data(target_user=callback.from_user.id, target_label="خودم")
        await _initiate_payment(callback, state)
    else:
        await state.set_state(TelegramPremiumStates.enter_other_id)
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "👥 لطفاً <b>شناسه کاربری تلگرام</b> دریافت‌کننده را ارسال کنید.\n"
                "(فقط شناسه عددی — مثال: <code>123456789</code>)",
                reply_markup=back_to_menu_kb(),
            )
    await callback.answer()


# ─── Enter other user ID ─────────────────────────────────────────────

@router.message(TelegramPremiumStates.enter_other_id)
async def msg_enter_other_id(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("⚠️ لطفاً یک شناسه عددی معتبر ارسال کنید.", reply_markup=back_to_menu_kb())
        return

    target_id = int(text)
    await state.update_data(target_user=target_id, target_label=f"شناسه {target_id}")
    await _initiate_payment_msg(message, state)


# ─── Payment initiation ──────────────────────────────────────────────

async def _initiate_payment(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    product = data["product"]
    usd = data["product_usd"]
    target_label = data["target_label"]

    final_irt, rate = await price_display_raw(usd)

    order_id = await create_order(
        user_id=callback.from_user.id,
        product=product,
        details=f"دریافت‌کننده: {target_label}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"{product} برای {target_label}",
    )

    if not result.success or not result.authority:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"❌ درخواست پرداخت ناموفق بود:\n{result.message}\n\nلطفاً بعداً دوباره تلاش کنید.",
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
    )
    await state.set_state(TelegramPremiumStates.payment)

    rate_str = f"{rate:,.0f}".replace(",", "،")
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"💳 <b>پرداخت: {product}</b>\n\n"
            f"👤 دریافت‌کننده: {target_label}\n"
            f"💱 نرخ ارز: ۱ دلار = {rate_str} تومان\n"
            f"💰 مبلغ کل: <b>{final_irt:,} تومان</b>\n\n"
            f"برای ادامه پرداخت روی دکمه زیر کلیک کنید:",
            reply_markup=pay_link_kb(result.start_pay_url),
        )


async def _initiate_payment_msg(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    product = data["product"]
    usd = data["product_usd"]
    target_label = data["target_label"]

    final_irt, rate = await price_display_raw(usd)

    order_id = await create_order(
        user_id=message.from_user.id,
        product=product,
        details=f"دریافت‌کننده: {target_label}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"{product} برای {target_label}",
    )

    if not result.success or not result.authority:
        await message.answer(
            f"❌ درخواست پرداخت ناموفق بود:\n{result.message}\n\nلطفاً بعداً دوباره تلاش کنید.",
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
    )
    await state.set_state(TelegramPremiumStates.payment)

    rate_str = f"{rate:,.0f}".replace(",", "،")
    await message.answer(
        f"💳 <b>پرداخت: {product}</b>\n\n"
        f"👤 دریافت‌کننده: {target_label}\n"
        f"💱 نرخ ارز: ۱ دلار = {rate_str} تومان\n"
        f"💰 مبلغ کل: <b>{final_irt:,} تومان</b>\n\n"
        f"برای ادامه پرداخت روی دکمه زیر کلیک کنید:",
        reply_markup=pay_link_kb(result.start_pay_url),
    )
