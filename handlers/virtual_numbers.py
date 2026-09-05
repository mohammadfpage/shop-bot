"""
Handler: Virtual Numbers workflow.
Flow: choose_country → payment → deliver number (post-payment only)
All user-facing text in Persian (فارسی).
"""

import contextlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from states.states import VirtualNumberStates
from utils.pricing import price_display, price_display_raw
from utils.zarinpal import request_payment
from utils.virtual_api import fetch_virtual_number
from database.db import create_order, create_payment, update_payment_authority, update_order_status, get_price_or_default
from keyboards.inline import (
    virtual_country_kb,
    pay_link_kb,
    back_to_menu_kb,
)

router = Router(name="virtual_numbers")

_COUNTRY_PRICES: dict[str, str] = {
    "iran": "ایران",
    "usa": "آمریکا",
    "uk": "بریتانیا",
    "germany": "آلمان",
}


# ─── Choose country ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vn:country:"))
async def cb_vn_country(callback: CallbackQuery, state: FSMContext) -> None:
    country = callback.data.split(":")[2]
    if country not in _COUNTRY_PRICES:
        await callback.answer("کشور نامعتبر", show_alert=True)
        return

    usd = await get_price_or_default("virtual_number")
    price_str = await price_display(usd)
    country_name = _COUNTRY_PRICES[country]

    await state.update_data(country=country, country_name=country_name, product_usd=usd)
    await state.set_state(VirtualNumberStates.payment)

    # Create order
    final_irt, rate = await price_display_raw(usd)
    order_id = await create_order(
        user_id=callback.from_user.id,
        product=f"شماره مجازی ({country_name})",
        details=f"کشور: {country_name}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"شماره مجازی — {country_name}",
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
            f"📱 <b>شماره مجازی — {country_name}</b>\n\n"
            f"💰 قیمت: <b>{final_irt:,} تومان</b>\n"
            f"💱 نرخ ارز: ۱ دلار = {rate_str} تومان\n\n"
            "پس از پرداخت موفق، شماره مجازی شما ارسال خواهد شد.",
            reply_markup=pay_link_kb(result.start_pay_url),
        )
    await callback.answer()
