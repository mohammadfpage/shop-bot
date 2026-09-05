"""
Handler: Design Services workflow.
Flow: choose_tier → enter_description → enter_contact → payment
All user-facing text in Persian (فارسی).
"""

import contextlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from states.states import DesignServiceStates
from utils.pricing import price_display, price_display_raw
from utils.zarinpal import request_payment
from database.db import create_order, create_payment, update_payment_authority, get_price_or_default
from keyboards.inline import (
    design_tier_kb,
    back_to_menu_kb,
    pay_link_kb,
)

router = Router(name="design")

_TIER_INFO = {
    "ai": ("طراحی با هوش مصنوعی", "design_ai"),
    "simple": ("طراحی ساده", "design_simple"),
    "normal": ("طراحی حرفه‌ای", "design_normal"),
    "special": ("طراحی ویژه", "design_special"),
}

_TIER_DESCRIPTIONS = {
    "ai": "طراحی خودکار با هوش مصنوعی به همراه بازبینی توسط کارشناس.",
    "simple": "طراحی پایه دستی — لوگو، بنر یا پست شبکه اجتماعی.",
    "normal": "طراحی حرفه‌ای چندعنصری با امکان اصلاحات.",
    "special": "پکیج طراحی سفارشی ویژه با پشتیبانی اولویت‌دار.",
}


# ─── Choose tier ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("design:tier:"))
async def cb_design_tier(callback: CallbackQuery, state: FSMContext) -> None:
    tier = callback.data.split(":")[2]
    if tier not in _TIER_INFO:
        await callback.answer("سطح نامعتبر", show_alert=True)
        return

    label, product_key = _TIER_INFO[tier]
    desc = _TIER_DESCRIPTIONS[tier]
    usd = await get_price_or_default(product_key)
    price_str = await price_display(usd)

    await state.update_data(tier=tier, product=label, product_usd=usd, description="")
    await state.set_state(DesignServiceStates.enter_description)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"🎨 <b>{label}</b>\n\n"
            f"{desc}\n\n"
            f"💰 قیمت: <b>{price_str}</b>\n\n"
            "📝 لطفاً پروژه خود را با جزئیات توضیح دهید.\n"
            "توضیحات را به صورت پیام بعدی ارسال کنید.",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── Enter project description ──────────────────────────────────────

@router.message(DesignServiceStates.enter_description)
async def msg_design_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()
    if len(description) < 10:
        await message.answer("⚠️ لطفاً توضیحات دقیق‌تری ارسال کنید (حداقل ۱۰ کاراکتر).")
        return

    await state.update_data(description=description)
    await state.set_state(DesignServiceStates.enter_contact)

    await message.answer(
        "📞 چگونه مدیر می‌تواند با شما ارتباط بگیرد؟\n"
        "نام کاربری <b>تلگرام</b> یا <b>شماره تماس</b> خود را ارسال کنید.",
        reply_markup=back_to_menu_kb(),
    )


# ─── Enter contact info ─────────────────────────────────────────────

@router.message(DesignServiceStates.enter_contact)
async def msg_design_contact(message: Message, state: FSMContext) -> None:
    contact = message.text.strip()
    if len(contact) < 3:
        await message.answer("⚠️ لطفاً اطلاعات تماس معتبری ارسال کنید.")
        return

    await state.update_data(contact=contact)

    data = await state.get_data()
    label = data["product"]
    usd = data["product_usd"]
    description = data["description"]

    final_irt, rate = await price_display_raw(usd)

    order_id = await create_order(
        user_id=message.from_user.id,
        product=f"طراحی: {label}",
        details=f"توضیحات: {description}\nتماس: {contact}",
        amount_irt=final_irt,
    )

    result = await request_payment(
        amount_irt=final_irt,
        description=f"خدمات طراحی — {label}",
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
    await state.set_state(DesignServiceStates.payment)

    rate_str = f"{rate:,.0f}".replace(",", "،")
    await message.answer(
        f"🎨 <b>خدمات طراحی — {label}</b>\n\n"
        f"📝 توضیحات: {description[:200]}{'…' if len(description) > 200 else ''}\n"
        f"📞 تماس: {contact}\n\n"
        f"💱 نرخ ارز: ۱ دلار = {rate_str} تومان\n"
        f"💰 مبلغ کل: <b>{final_irt:,} تومان</b>\n\n"
        "برای پرداخت روی دکمه زیر کلیک کنید. پس از پرداخت درخواست شما به تیم طراحی ارسال می‌شود.",
        reply_markup=pay_link_kb(result.start_pay_url),
    )
