"""
Handler: Design Services workflow.
Flow: choose_category → choose_tier → enter_description → enter_contact → payment
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
from utils.emojis import get_pe
from database.db import create_order, create_payment, update_payment_authority, get_price_or_default
from keyboards.inline import (
    design_category_kb,
    design_tier_kb,
    back_to_menu_kb,
    pay_link_kb,
)

router = Router(name="design")

# Category display names
_CATEGORY_NAMES = {
    "video": "ویدیو",
    "photo": "عکس",
    "logo": "لوگو",
}

# Tier display names
_TIER_NAMES = {
    "ai": "با هوش مصنوعی",
    "simple": "ساده",
    "pro": "حرفه‌ای",
    "special": "ویژه",
}

# Product key pattern: design_{category}_{tier}
_TIER_DESCRIPTIONS = {
    "ai": "طراحی خودکار با هوش مصنوعی به همراه بازبینی توسط کارشناس.",
    "simple": "طراحی پایه دستی — لوگو، بنر یا پست شبکه اجتماعی.",
    "pro": "طراحی حرفه‌ای چندعنصری با امکان اصلاحات.",
    "special": "پکیج طراحی سفارشی ویژه با پشتیبانی اولویت‌دار.",
}


# ─── Choose category ─────────────────────────────────────────────

@router.callback_query(F.data == "menu:design")
async def cb_menu_design(callback: CallbackQuery) -> None:
    await callback.answer()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('fire')} <b>خدمات طراحی</b>\nیک دسته را انتخاب کنید:",
            reply_markup=await design_category_kb(),
        )
    await callback.answer()


# ─── Choose tier (within category) ──────────────────────────────

@router.callback_query(F.data.startswith("design:cat:"))
async def cb_design_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    category = callback.data.split(":")[2]
    if category not in _CATEGORY_NAMES:
        await callback.answer("دسته نامعتبر", show_alert=True)
        return

    cat_name = _CATEGORY_NAMES[category]
    await state.update_data(design_category=category)
    await state.set_state(DesignServiceStates.choose_tier)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('fire')} <b>خدمات طراحی — {cat_name}</b>\nیک سطح کیفیت را انتخاب کنید:",
            reply_markup=await design_tier_kb(category),
        )
    await callback.answer()


@router.callback_query(F.data == "design:back_to_categories")
async def cb_design_back_to_categories(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('fire')} <b>خدمات طراحی</b>\nیک دسته را انتخاب کنید:",
            reply_markup=await design_category_kb(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("design:tier:"), DesignServiceStates.choose_tier)
async def cb_design_tier(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    # design:tier:{category}:{tier}
    category = parts[2]
    tier = parts[3]

    if category not in _CATEGORY_NAMES or tier not in _TIER_NAMES:
        await callback.answer("گزینه نامعتبر", show_alert=True)
        return

    product_key = f"design_{category}_{tier}"
    cat_name = _CATEGORY_NAMES[category]
    tier_name = _TIER_NAMES[tier]
    label = f"{cat_name} — {tier_name}"
    desc = _TIER_DESCRIPTIONS[tier]
    usd = await get_price_or_default(product_key)
    price_str = await price_display(usd)

    await state.update_data(
        tier=tier,
        category=category,
        product=label,
        product_key=product_key,
        product_usd=usd,
        description="",
    )
    await state.set_state(DesignServiceStates.enter_description)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('fire')} <b>{label}</b>\n\n"
            f"{desc}\n\n"
            f"{get_pe('money')} قیمت: <b>{price_str}</b>\n\n"
            f"{get_pe('star')} لطفاً پروژه خود را با جزئیات توضیح دهید.\n"
            "توضیحات را به صورت پیام بعدی ارسال کنید.",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── Enter project description ──────────────────────────────────

@router.message(DesignServiceStates.enter_description)
async def msg_design_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()
    if len(description) < 10:
        await message.answer(f"{get_pe('warning')} لطفاً توضیحات دقیق‌تری ارسال کنید (حداقل ۱۰ کاراکتر).")
        return

    await state.update_data(description=description)
    await state.set_state(DesignServiceStates.enter_contact)

    await message.answer(
        f"{get_pe('call')} چگونه مدیر می‌تواند با شما ارتباط بگیرد?\n"
        "نام کاربری <b>تلگرام</b> یا <b>شماره تماس</b> خود را ارسال کنید.",
        reply_markup=back_to_menu_kb(),
    )


# ─── Enter contact info ─────────────────────────────────────────

@router.message(DesignServiceStates.enter_contact)
async def msg_design_contact(message: Message, state: FSMContext) -> None:
    contact = message.text.strip()
    if len(contact) < 3:
        await message.answer(f"{get_pe('warning')} لطفاً اطلاعات تماس معتبری ارسال کنید.")
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
            f"{get_pe('cross')} درخواست پرداخت ناموفق بود:\n{result.message}",
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
        f"{get_pe('fire')} <b>خدمات طراحی — {label}</b>\n\n"
        f"{get_pe('star')} توضیحات: {description[:200]}{'…' if len(description) > 200 else ''}\n"
        f"{get_pe('call')} تماس: {contact}\n\n"
        f"{get_pe('exchange')} نرخ ارز: ۱ دلار = {rate_str} تومان\n"
        f"{get_pe('money')} مبلغ کل: <b>{final_irt:,} تومان</b>\n\n"
        "برای پرداخت روی دکمه زیر کلیک کنید. پس از پرداخت درخواست شما به تیم طراحی ارسال می‌شود.",
        reply_markup=pay_link_kb(result.start_pay_url),
    )
