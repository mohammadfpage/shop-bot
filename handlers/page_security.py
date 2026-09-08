"""
Handler: Page Security service.
Flow: choose_tariff → enter_page_url → enter_details → confirm → forward to admin
All user-facing text in Persian (فارسی).
"""

import contextlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from states.states import PageSecurityStates
from utils.pricing import price_display
from utils.emojis import get_pe
from database.db import create_order, get_or_create_user
from keyboards.inline import (
    security_tariff_kb,
    back_to_menu_kb,
)

router = Router(name="page_security")


# ─── Choose tariff ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("security:tariff:"))
async def cb_security_tariff(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    tariff_key = callback.data.split(":")[2]
    tariffs = config.SECURITY_TARIFFS

    if tariff_key not in tariffs:
        await callback.answer("تعرفه نامعتبر", show_alert=True)
        return

    tariff = tariffs[tariff_key]
    usd = tariff["usd"]
    desc = tariff["description"]
    price_str = await price_display(usd)

    tariff_names = {"basic": "پایه", "standard": "استاندارد", "advanced": "پیشرفته"}
    tariff_name = tariff_names.get(tariff_key, tariff_key)

    await state.update_data(tariff_key=tariff_key, tariff_desc=desc, product_usd=usd)
    await state.set_state(PageSecurityStates.enter_page_url)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('shield')} <b>امنیت صفحه — {tariff_name}</b>\n\n"
            f"{desc}\n\n"
            f"{get_pe('money')} قیمت: <b>{price_str}</b>\n\n"
            f"{get_pe('web')} لطفاً <b>آدرس URL صفحه‌ای</b> که می‌خواهید امن شود را ارسال کنید.",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── Enter page URL ──────────────────────────────────────────────────

@router.message(PageSecurityStates.enter_page_url)
async def msg_page_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        await message.answer(f"{get_pe('warning')} لطفاً یک آدرس URL معتبر ارسال کنید (شروع با http:// یا https://).")
        return

    await state.update_data(page_url=url)
    await state.set_state(PageSecurityStates.enter_details)

    await message.answer(
        f"{get_pe('star')} لطفاً <b>نگرانی‌ها یا الزامات امنیتی خاص</b> را توضیح دهید.\n"
        "اگر موردی نیست، فقط <code>none</code> ارسال کنید.",
        reply_markup=back_to_menu_kb(),
    )


# ─── Enter details ──────────────────────────────────────────────────

@router.message(PageSecurityStates.enter_details)
async def msg_security_details(message: Message, state: FSMContext) -> None:
    details = message.text.strip()
    await state.update_data(details=details)
    await state.set_state(PageSecurityStates.confirm)

    data = await state.get_data()
    tariff_key = data["tariff_key"]
    page_url = data["page_url"]
    usd = data["product_usd"]
    price_str = await price_display(usd)

    tariff_names = {"basic": "پایه", "standard": "استاندارد", "advanced": "پیشرفته"}
    tariff_name = tariff_names.get(tariff_key, tariff_key)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from utils.emojis import get_premium_id
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تأیید و ارسال",
                              callback_data="security:confirm",
                              style="success",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="انصراف",
                              callback_data="menu:back",
                              style="danger",
                              icon_custom_emoji_id=get_premium_id("cross"))],
    ])

    await message.answer(
        f"{get_pe('shield')} <b>خلاصه درخواست امنیتی</b>\n\n"
        f"تعرفه: <b>{tariff_name}</b>\n"
        f"صفحه: <code>{page_url}</code>\n"
        f"جزئیات: {details if details.lower() != 'none' else '—'}\n"
        f"{get_pe('money')} قیمت تخمینی: <b>{price_str}</b>\n\n"
        "روی <b>تأیید و ارسال</b> کلیک کنید تا درخواست شما به تیم ما ارسال شود.\n"
        "مدیر ما به زودی با شما تماس خواهد گرفت.",
        reply_markup=confirm_kb,
    )


# ─── Confirm → forward to admin ─────────────────────────────────────

@router.callback_query(F.data == "security:confirm", PageSecurityStates.confirm)
async def cb_security_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()

    user = await get_or_create_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    tariff_key = data["tariff_key"]
    tariff_desc = data["tariff_desc"]
    page_url = data["page_url"]
    details = data.get("details", "")
    usd = data["product_usd"]
    price_str = await price_display(usd)

    tariff_names = {"basic": "پایه", "standard": "استاندارد", "advanced": "پیشرفته"}
    tariff_name = tariff_names.get(tariff_key, tariff_key)

    # Create order (no payment required yet — admin will contact user)
    await create_order(
        user_id=callback.from_user.id,
        product=f"امنیت: {tariff_name}",
        details=f"URL: {page_url}\nجزئیات: {details}\nتماس: @{callback.from_user.username or 'N/A'}",
        amount_irt=0,
    )

    # Forward to all admins
    admin_msg = (
        f"{get_pe('shield')} <b>درخواست امنیتی جدید</b>\n\n"
        f"{get_pe('user')} کاربر: {callback.from_user.full_name} (@{callback.from_user.username or 'N/A'})\n"
        f"{get_pe('id_icon')} شناسه: <code>{callback.from_user.id}</code>\n\n"
        f"تعرفه: <b>{tariff_name}</b>\n"
        f"توضیحات: {tariff_desc}\n"
        f"صفحه: <code>{page_url}</code>\n"
        f"جزئیات: {details if details.lower() != 'none' else '—'}\n"
        f"{get_pe('money')} قیمت: {price_str}\n\n"
        f"<i>برای تکمیل سفارش با کاربر تماس بگیرید.</i>"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await callback.bot.send_message(admin_id, admin_msg)
        except Exception:
            pass

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('check')} <b>درخواست شما با موفقیت ثبت شد!</b>\n\n"
            "مدیر ما به زودی با شما تماس خواهد گرفت تا جزئیات را بررسی کرده و پرداخت را نهایی کند.",
            reply_markup=back_to_menu_kb(),
        )
    await state.clear()
    await callback.answer()
