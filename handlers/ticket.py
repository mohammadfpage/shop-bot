"""
Handler: Support Ticket System.

Flow:
    1. User clicks "پشتیبانی" on reply keyboard.
    2. Bot prompts the user to describe their issue.
    3. User sends their message.
    4. Bot saves the ticket in the DB and forwards it to SUPPORT_ADMIN_ID.
    5. Admin sees the forwarded message with an inline "📝 پاسخ" button.
    6. Admin clicks the button, types a reply.
    7. Bot sends the reply back to the user.

All user-facing text in Persian (فارسی).
"""

import contextlib
import logging
from typing import Any

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest

from config import config
from states.states import TicketStates
from database.db import (
    create_ticket,
    get_ticket,
    close_ticket,
    get_or_create_user,
)
from keyboards.reply import main_reply_kb
from keyboards.inline import back_to_menu_kb
from utils.emojis import get_pe, get_premium_id

router = Router(name="ticket")
logger = logging.getLogger(__name__)


# ─── "🎧 پشتیبانی" pressed on reply keyboard ──────────────────────

@router.message(F.text.contains("پشتیبانی"))
async def cb_ticket_start(message: Message, state: FSMContext) -> None:
    """Prompt the user to write their support message."""
    await state.set_state(TicketStates.waiting_message)
    await message.answer(
        f"{get_pe('call')} <b>پشتیبانی</b>\n\n"
        "لطفاً پیام یا مشکل خود را به صورت متنی بنویسید.\n"
        "پیام شما برای پشتیبان ارسال خواهد شد.\n\n"
        "برای انصراف، روی دکمه «🔙 بازگشت به منو» کلیک کنید.",
        reply_markup=back_to_menu_kb(),
    )


# ─── Cancel from back-to-menu ────────────────────────────────────────

@router.callback_query(F.data == "menu:back", StateFilter(TicketStates.waiting_message))
async def cb_ticket_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel ticket creation and return to main menu."""
    await callback.answer()
    await state.clear()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🏠 <b>منوی اصلی</b>\nیک سرویس را انتخاب کنید:",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── User sends their ticket message ────────────────────────────────

@router.message(TicketStates.waiting_message)
async def msg_ticket_submit(message: Message, state: FSMContext) -> None:
    """Save the ticket to DB and forward to the support admin."""
    text = message.text
    if not text or len(text.strip()) < 3:
        await message.answer("⚠️ لطفاً حداقل ۳ کاراکتر بنویسید.")
        return

    # 1) Save ticket in DB
    ticket_id = await create_ticket(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        message=text.strip(),
    )

    await state.clear()

    # 2) Confirm to user
    await message.answer(
        f"{get_pe('check')} <b>تیکت #{ticket_id} ثبت شد!</b>\n\n"
        "پیام شما برای پشتیبان ارسال شد.\n"
        f"به زودی پاسخ دریافت خواهید کرد. {get_pe('sparkles')}",
        reply_markup=main_reply_kb(),
    )

    # 3) Build the admin notification with an inline reply button
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="پاسخ به تیکت",
                callback_data=f"ticket:reply:{ticket_id}",
                style="success",
                icon_custom_emoji_id=get_premium_id("call"),
            )
        ],
        [
            InlineKeyboardButton(
                text="بستن تیکت",
                callback_data=f"ticket:close:{ticket_id}",
                style="danger",
                icon_custom_emoji_id=get_premium_id("cross"),
            )
        ],
    ])

    admin_text = (
        f"{get_pe('ticket')} <b>تیکت جدید #{ticket_id}</b>\n\n"
        f"{get_pe('user')} کاربر: {message.from_user.full_name}\n"
        f"🆔 شناسه: <code>{message.from_user.id}</code>\n"
        f"📛 یوزرنیم: @{message.from_user.username or 'ندارد'}\n"
        f"{get_pe('calendar')} تاریخ: {ticket_id}\n\n"
        f"💬 پیام:\n{text.strip()}"
    )

    # 4) Forward to the support admin
    try:
        await message.bot.send_message(
            chat_id=config.SUPPORT_ADMIN_ID,
            text=admin_text,
            reply_markup=admin_kb,
        )
    except Exception as exc:
        logger.error("Failed to forward ticket #%s to admin: %s", ticket_id, exc)
        await message.answer(
            "⚠️ ارسال تیکت با مشکل مواجه شد. لطفاً بعداً دوباره تلاش کنید."
        )


# ─── Admin clicks "📝 پاسخ به تیکت" ────────────────────────────────

@router.callback_query(F.data.startswith("ticket:reply:"))
async def cb_admin_reply_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    """Admin initiates a reply to a specific ticket."""
    await callback.answer()
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ دسترسی غیرمجاز", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket = await get_ticket(ticket_id)

    if not ticket:
        await callback.answer("⚠️ تیکت یافت نشد.", show_alert=True)
        return

    if ticket["status"] == "closed":
        await callback.answer("⚠️ این تیکت قبلاً بسته شده است.", show_alert=True)
        return

    # Store ticket_id in FSM state for the next message
    await state.set_state(TicketStates.admin_reply)
    await state.update_data(reply_ticket_id=ticket_id, reply_user_id=ticket["user_id"])

    await callback.message.answer(
        f"{get_pe('star')} <b>در حال پاسخ به تیکت #{ticket_id}</b>\n\n"
        f"{get_pe('user')} کاربر: {ticket['full_name']} (<code>{ticket['user_id']}</code>)\n"
        f"💬 پیام اصلی:\n<i>{ticket['message']}</i>\n\n"
        "حالا پاسخ خود را بنویسید:",
    )
    await callback.answer()


# ─── Admin sends the reply text ──────────────────────────────────────

@router.message(TicketStates.admin_reply)
async def msg_admin_send_reply(message: Message, state: FSMContext) -> None:
    """Send the admin's reply back to the user and close the ticket."""
    if message.from_user.id not in config.ADMIN_IDS:
        return

    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    user_id = data.get("reply_user_id")

    if not ticket_id or not user_id:
        await message.answer("⚠️ خطا: اطلاعات تیکت یافت نشد.")
        await state.clear()
        return

    reply_text = message.text.strip()
    if not reply_text:
        await message.answer("⚠️ پاسخ نمی‌تواند خالی باشد.")
        return

    # 1) Send reply to the user
    try:
        await message.bot.send_message(
            chat_id=user_id,
            text=(
                f"{get_pe('call')} <b>پاسخ پشتیبانی — تیکت #{ticket_id}</b>\n\n"
                f"{reply_text}\n\n"
                "اگر سؤال دیگری دارید، مجدداً تیکت ارسال کنید."
            ),
            reply_markup=main_reply_kb(),
        )
    except Exception as exc:
        logger.error("Failed to send reply to user %s: %s", user_id, exc)
        await message.answer(
            f"⚠️ ارسال پاسخ به کاربر <code>{user_id}</code> ناموفق بود.\n"
            "ممکن است کاربر ربات را بلاک کرده باشد."
        )

    # 2) Close the ticket
    await close_ticket(ticket_id)

    await state.clear()
    await message.answer(
        f"{get_pe('check')} پاسخ تیکت #{ticket_id} با موفقیت ارسال شد و تیکت بسته شد."
    )


# ─── Admin clicks "✅ بستن تیکت" ────────────────────────────────────

@router.callback_query(F.data.startswith("ticket:close:"))
async def cb_admin_close_ticket(callback: CallbackQuery) -> None:
    """Admin closes a ticket without replying."""
    await callback.answer()
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ دسترسی غیرمجاز", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket = await get_ticket(ticket_id)

    if not ticket:
        await callback.answer("⚠️ تیکت یافت نشد.", show_alert=True)
        return

    if ticket["status"] == "closed":
        await callback.answer("⚠️ این تیکت قبلاً بسته شده است.", show_alert=True)
        return

    await close_ticket(ticket_id)

    # Optionally notify the user
    try:
        await callback.bot.send_message(
            chat_id=ticket["user_id"],
            text=(
                f"{get_pe('ticket')} <b>تیکت #{ticket_id} بسته شد.</b>\n\n"
                "تیکت شما توسط مدیر بسته شد.\n"
                "اگر سؤال دیگری دارید، مجدداً تیکت ارسال کنید."
            ),
            reply_markup=main_reply_kb(),
        )
    except Exception as exc:
        logger.warning("Could not notify user %s about ticket close: %s", ticket["user_id"], exc)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"✅ تیکت #{ticket_id} بسته شد.",
        )
    await callback.answer("تیکت بسته شد.", show_alert=True)
