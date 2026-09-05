"""
Handler: AI Accounts (ChatGPT & Gemini) purchase workflow.
Flow: choose_platform → payment → auto-deliver credentials
All user-facing text in Persian (فارسی).
"""

import contextlib
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from states.states import AIAccountStates
from utils.pricing import price_display, price_display_raw
from utils.zarinpal import request_payment
from database.db import create_order, create_payment, update_payment_authority, get_price_or_default
from keyboards.inline import (
    ai_platform_kb,
    pay_link_kb,
    back_to_menu_kb,
)

router = Router(name="ai_accounts")

_PLATFORM_INFO = {
    "chatgpt": ("ChatGPT Plus", "chatgpt_premium"),
    "gemini": ("Gemini Advanced", "gemini_premium"),
}


# ─── Choose platform ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ai:platform:"))
async def cb_ai_platform(callback: CallbackQuery, state: FSMContext) -> None:
    platform = callback.data.split(":")[2]
    if platform not in _PLATFORM_INFO:
        await callback.answer("گزینه نامعتبر", show_alert=True)
        return

    label, product_key = _PLATFORM_INFO[platform]
    usd = await get_price_or_default(product_key)
    price_str = await price_display(usd)

    await state.update_data(platform=platform, product=label, product_usd=usd)
    await state.set_state(AIAccountStates.payment)

    # Create order
    final_irt, rate = await price_display_raw(usd)
    order_id = await create_order(
        user_id=callback.from_user.id,
        product=label,
        details=f"پلتفرم: {platform}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"اکانت پرمیوم {label}",
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

    rate_str = f"{rate:,.0f}".replace(",", "،")
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"🤖 <b>{label}</b>\n\n"
            f"💰 قیمت: <b>{final_irt:,} تومان</b>\n"
            f"💱 نرخ ارز: ۱ دلار = {rate_str} تومان\n\n"
            "پس از پرداخت، اطلاعات ورود اکانت شما به صورت خودکار ارسال می‌شود.",
            reply_markup=pay_link_kb(result.start_pay_url),
        )
    await callback.answer()
