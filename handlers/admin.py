"""
Handler: Admin panel.

Commands:
    /admin  — open admin dashboard (IsAdmin protected)
    /stats  — quick bot statistics (IsAdmin protected)
    /users  — list registered users (IsAdmin protected)

Reply keyboard:
    "ورود به پنل مدیریت"  — same as /admin
    "بازگشت به منوی اصلی" — return to normal user keyboard

Features:
  - View pending / completed / all orders
  - Manage paid orders (fulfill or cancel with user notification)
  - Edit product base prices (stored in PostgreSQL, persists across restarts)
  - Financial reports (today / week / month / total revenue)
  - Broadcast message to all users
  - Total users stat on dashboard
  - Admin guide / help

All admin-facing text in Persian (فارسی).
"""

import contextlib
import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from filters import IsAdmin
from states.states import AdminStates, ProductState
from keyboards.callback_data import ProductCallback
from keyboards.admin_product import (
    product_list_kb,
    product_detail_kb,
    product_edit_success_kb,
)
from database.db import (
    get_all_orders,
    get_order,
    update_order_status,
    get_all_product_prices,
    update_product_price,
    get_price_or_default,
    get_revenue_by_period,
    get_total_users,
    get_order_count_by_status,
    get_all_users,
    get_open_tickets,
)
from keyboards.admin import (
    admin_panel_kb,
    admin_order_kb,
    admin_paid_order_kb,
    admin_back_kb,
    admin_finance_kb,
    admin_broadcast_confirm_kb,
)
from keyboards.admin_reply import admin_reply_kb
from keyboards.reply import main_reply_kb
from keyboards.inline import back_to_menu_kb
from utils.emojis import get_pe, PREMIUM_EMOJIS

router = Router(name="admin")
logger = logging.getLogger(__name__)


def _status_fa(status: str) -> str:
    return {
        "pending": "در انتظار",
        "paid": "پرداخت شده",
        "delivered": "تحویل شده",
        "cancelled": "لغو شده",
    }.get(status, status)


def _safe_amount(amount: int) -> str:
    return f"{amount:,}".replace(",", "،") if amount else "—"


# ═══════════════════════════════════════════════════════════════════════
#  REPLY KEYBOARD HANDLERS (text buttons)
# ═══════════════════════════════════════════════════════════════════════

@router.message(F.text.contains("ورود به پنل مدیریت"), IsAdmin())
async def reply_btn_admin_panel(message: Message, state: FSMContext) -> None:
    """Open admin dashboard when the admin taps the reply keyboard button."""
    await _show_admin_dashboard(message, state)


@router.message(F.text.contains("بازگشت به منوی اصلی"), IsAdmin())
async def reply_btn_back_to_main(message: Message, state: FSMContext) -> None:
    """Return to the normal user keyboard."""
    await state.clear()
    await message.answer(
        f"{get_pe('home')} <b>منوی اصلی</b>\nیک سرویس را انتخاب کنید:",
        reply_markup=main_reply_kb(),
    )


# ═══════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════

@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: Message, state: FSMContext) -> None:
    """Open admin dashboard — protected by IsAdmin filter."""
    await _show_admin_dashboard(message, state)


@router.message(Command("stats"), IsAdmin())
async def cmd_stats(message: Message) -> None:
    """Show quick bot statistics for admins — protected by IsAdmin filter."""
    user_count = await get_total_users()
    pending = await get_order_count_by_status("pending")
    paid = await get_order_count_by_status("paid")
    delivered = await get_order_count_by_status("delivered")
    cancelled = await get_order_count_by_status("cancelled")
    today_rev = await get_revenue_by_period("today")
    month_rev = await get_revenue_by_period("month")
    total_rev = await get_revenue_by_period("all")
    open_tickets = await get_open_tickets()

    await message.answer(
        f"{get_pe('chart')} <b>آمار سریع ربات</b>\n\n"
        f"{get_pe('users')} کل کاربران: <b>{user_count}</b>\n"
        f"{get_pe('yellow_circle')} سفارشات در انتظار: <b>{pending}</b>\n"
        f"{get_pe('green_circle')} پرداخت شده: <b>{paid}</b>\n"
        f"{get_pe('check')} انجام شده: <b>{delivered}</b>\n"
        f"{get_pe('cross')} لغو شده: <b>{cancelled}</b>\n\n"
        f"{get_pe('ticket')} تیکت‌های باز: <b>{len(open_tickets)}</b>\n\n"
        f"{get_pe('money')} درآمد امروز: <b>{_safe_amount(today_rev)} تومان</b>\n"
        f"{get_pe('calendar')} درآمد ماهانه: <b>{_safe_amount(month_rev)} تومان</b>\n"
        f"{get_pe('diamond')} درآمد کل: <b>{_safe_amount(total_rev)} تومان</b>",
        reply_markup=admin_reply_kb(),
    )


@router.message(Command("test_emojis"), F.from_user.id == 7174138646)
async def debug_test_emojis(message: Message):
    """Debug command to test premium emoji IDs and report broken ones."""
    await message.answer("🔍 در حال تست ایموجی‌های پرمیوم... این کار حدود ۲۰ ثانیه زمان می‌برد.")
    failed_emojis = []
    
    for key, data in PREMIUM_EMOJIS.items():
        fallback, premium_id = data
        if not premium_id:
            continue
            
        test_text = f"Test {key}: <tg-emoji emoji-id='{premium_id}'>{fallback}</tg-emoji>"
        try:
            # Explicitly parse_mode="HTML" just in case global default is missing
            await message.bot.send_message(
                chat_id=7174138646,
                text=test_text,
                parse_mode="HTML"
            )
            await asyncio.sleep(0.3)  # Anti-flood delay
        except Exception:
            # If it fails (e.g., DOCUMENT_INVALID), record the broken key
            failed_emojis.append(f"Key: {key} | ID: {premium_id}")
            
    if failed_emojis:
        report = "⚠️ این ایموجی‌ها نامعتبر هستند و باعث کرش ربات می‌شوند:\n\n" + "\n".join(failed_emojis)
    else:
        report = "✅ تمامی ایموجی‌ها سالم هستند!"
        
    await message.bot.send_message(chat_id=7174138646, text=report)


@router.message(Command("users"), IsAdmin())
async def cmd_users(message: Message) -> None:
    """Show the total number of registered users — protected by IsAdmin filter."""
    from database.db import get_pool
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT user_id, username, full_name, is_admin, joined_at "
        "FROM users ORDER BY joined_at DESC LIMIT 50"
    )

    if not rows:
        await message.answer(f"{get_pe('users')} هیچ کاربری ثبت‌نام نکرده است.", reply_markup=admin_reply_kb())
        return

    lines = [f"{get_pe('users')} <b>لیست کاربران</b> (تا ۵۰ نفر آخر)\n"]
    for r in rows:
        admin_tag = " "+get_pe('shield') if r["is_admin"] else ""
        username = f"@{r['username']}" if r["username"] else "—"
        lines.append(
            f"• <code>{r['user_id']}</code> | {r['full_name']} | {username}{admin_tag}"
        )

    lines.append(f"\nتعداد کل: {len(rows)} کاربر")
    await message.answer("\n".join(lines), reply_markup=admin_reply_kb())


# ═══════════════════════════════════════════════════════════════════════
#  ADMIN GUIDE / HELP
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:guide", IsAdmin())
async def cb_admin_guide(callback: CallbackQuery) -> None:
    """Show the admin guide — how to use the panel, respond to tickets, broadcast."""
    await callback.answer()
    guide_text = (
        f"{get_pe('star')} <b>راهنمای مدیران</b>\n\n"

        f"{get_pe('num1')} {get_pe('chart')} <b>آمار کاربران</b>\n"
        "   تعداد کل کاربران ثبت‌شده و وضعیت سفارشات را نمایش می‌دهد.\n\n"

        f"{get_pe('num2')} {get_pe('blue_heart')} <b>ارسال پیام همگانی (Broadcast)</b>\n"
        "   متنی بنویسید و آن را به تمام کاربران ربات ارسال کنید.\n"
        "   پیش از ارسال، پیش‌نمایشی از پیام نمایش داده می‌شود.\n"
        "   پس از تأیید، ربات به هر کاربر یک پیام ارسال می‌کند.\n\n"

        f"{get_pe('num3')} {get_pe('ticket')} <b>مدیریت تیکت‌ها</b>\n"
        "   وقتی کاربری تیکت پشتیبانی ارسال کند، پیام او برای شما\n"
        "   فوروارد می‌شود. روی دکمه «📝 پاسخ» کلیک کنید و پاسخ خود\n"
        "   را بنویسید. پاسخ شما برای کاربر ارسال خواهد شد.\n"
        f"   همچنین می‌توانید تیکت را بدون پاسخ با «{get_pe('check')} بستن تیکت» ببندید.\n\n"

        f"🔹 <b>{get_pe('money')} مدیریت قیمت محصولات</b>\n"
        "   قیمت پایه محصولات (به دلار) را ویرایش کنید.\n"
        "   قیمت نهایی = (قیمت دلاری × نرخ لحظه‌ای ارز) × (۱ + ۲۰٪)\n\n"

        f"🔹 <b>{get_pe('chart')} گزارش مالی</b>\n"
        "   درآمد امروز، هفتگی، ماهانه و کل را مشاهده کنید.\n\n"

        f"🔹 <b>{get_pe('ticket')} سفارشات</b>\n"
        "   سفارشات در انتظار، پرداخت شده، تکمیل شده و لغو شده.\n"
        "   سفارشات پرداخت شده را پس از انجام، به «انجام شده» تغییر\n"
        "   دهید تا به کاربر اطلاع‌رسانی شود.\n\n"

        f"{get_pe('key_lock')} <b>دستورات سریع:</b>\n"
        "   <code>/admin</code> — باز کردن پنل مدیریت\n"
        "   <code>/stats</code> — آمار سریع\n"
        "   <code>/users</code> — لیست کاربران"
    )

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            guide_text,
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════

async def _show_admin_dashboard(message: Message, state: FSMContext) -> None:
    """Display the admin dashboard with inline keyboard."""
    await state.clear()
    user_count = await get_total_users()
    await message.answer(
        f"{get_pe('gear')} <b>پنل مدیریت</b>\n\n"
        f"{get_pe('users')} تعداد کاربران: <b>{user_count}</b>\n\n"
        "یک عملیات را انتخاب کنید:",
        reply_markup=admin_panel_kb(user_count),
    )


# ═══════════════════════════════════════════════════════════════════════
#  INLINE CALLBACK HANDLERS (all protected by IsAdmin filter)
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:panel", IsAdmin())
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    user_count = await get_total_users()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('gear')} <b>پنل مدیریت</b>\n\n"
            f"{get_pe('users')} تعداد کاربران: <b>{user_count}</b>\n\n"
            "یک عملیات را انتخاب کنید:",
            reply_markup=admin_panel_kb(user_count),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:users_stat", IsAdmin())
async def cb_admin_users_stat(callback: CallbackQuery) -> None:
    await callback.answer()
    user_count = await get_total_users()
    pending_count = await get_order_count_by_status("pending")
    paid_count = await get_order_count_by_status("paid")
    delivered_count = await get_order_count_by_status("delivered")
    cancelled_count = await get_order_count_by_status("cancelled")

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('users')} <b>آمار کاربران و سفارشات</b>\n\n"
            f"{get_pe('user')} کل کاربران: <b>{user_count}</b>\n"
            f"{get_pe('yellow_circle')} سفارشات در انتظار: <b>{pending_count}</b>\n"
            f"{get_pe('green_circle')} سفارشات پرداخت شده: <b>{paid_count}</b>\n"
            f"{get_pe('check')} سفارشات انجام شده: <b>{delivered_count}</b>\n"
            f"{get_pe('cross')} سفارشات لغو شده: <b>{cancelled_count}</b>",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:pending", IsAdmin())
async def cb_admin_pending(callback: CallbackQuery) -> None:
    await callback.answer()
    orders = await get_all_orders(status="pending")
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('ticket')} سفارش در انتظاری وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = [f"{get_pe('ticket')} <b>سفارش‌های در انتظار</b>\n"]
        for o in orders[:20]:
            lines.append(
                f"#{o['order_id']} | {o['product']} | "
                f"{_safe_amount(o['amount_irt'])} تومان | کاربر: {o['user_id']}"
            )
        text = "\n".join(lines)
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:paid_orders", IsAdmin())
async def cb_admin_paid_orders(callback: CallbackQuery) -> None:
    await callback.answer()
    orders = await get_all_orders(status="paid")
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('ticket')} سفارش پرداخت شده‌ای برای پردازش وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = [f"{get_pe('star_gift')} <b>سفارشات پرداخت شده (نیاز به پردازش)</b>\n"]
        for o in orders[:20]:
            lines.append(
                f"#{o['order_id']} | {o['product']} | "
                f"{_safe_amount(o['amount_irt'])} تومان | کاربر: {o['user_id']}"
            )
        lines.append("\nروی سفارش مورد نظر کلیک کنید:")
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        from utils.emojis import get_premium_id
        buttons = []
        for o in orders[:10]:
            buttons.append([InlineKeyboardButton(
                text=f"#{o['order_id']} — {o['product'][:30]}",
                callback_data=f"admin:view_paid:{o['order_id']}",
                style="primary",
                icon_custom_emoji_id=get_premium_id("box"),
            )])
        buttons.append([InlineKeyboardButton(
            text="پنل مدیریت",
            callback_data="admin:panel",
            style="primary",
            icon_custom_emoji_id=get_premium_id("home"),
        )])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:view_paid:"), IsAdmin())
async def cb_admin_view_paid(callback: CallbackQuery) -> None:
    await callback.answer()
    order_id = int(callback.data.split(":")[3])
    order = await get_order(order_id)
    if not order:
        await callback.answer("⚠️ سفارش یافت نشد.", show_alert=True)
        return

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('star')} <b>جزئیات سفارش #{order['order_id']}</b>\n\n"
            f"{get_pe('user')} شناسه کاربر: <code>{order['user_id']}</code>\n"
            f"{get_pe('box')} محصول: {order['product']}\n"
            f"📝 جزئیات: {order['details'] or '—'}\n"
            f"{get_pe('money')} مبلغ: {_safe_amount(order['amount_irt'])} تومان\n"
            f"{get_pe('calendar')} تاریخ: {order['created_at'][:16] if order['created_at'] else '—'}\n"
            f"{get_pe('chart')} وضعیت: {get_pe('green_circle')} پرداخت شده\n\n"
            "عملیات مورد نظر را انتخاب کنید:",
            reply_markup=admin_paid_order_kb(order_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:complete:"), IsAdmin())
async def cb_admin_complete(callback: CallbackQuery) -> None:
    await callback.answer()
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await callback.answer("⚠️ سفارش یافت نشد.", show_alert=True)
        return

    await update_order_status(order_id, "delivered")

    try:
        await callback.bot.send_message(
            order["user_id"],
            f"{get_pe('check')} <b>سفارش شما تکمیل شد!</b>\n\n"
            f"{get_pe('box')} شماره سفارش: #{order_id}\n"
            f"🛍 محصول: {order['product']}\n\n"
            f"از خرید شما متشکریم! {get_pe('thumbsup')}"
        )
    except Exception as exc:
        logger.warning("Could not notify user %s: %s", order["user_id"], exc)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('check')} سفارش #{order_id} به عنوان <b>انجام شده</b> ثبت شد.\n"
            f"{get_pe('user')} به کاربر <code>{order['user_id']}</code> اطلاع‌رسانی شد.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:completed", IsAdmin())
async def cb_admin_completed(callback: CallbackQuery) -> None:
    await callback.answer()
    orders = await get_all_orders(status="delivered")
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('check')} هنوز سفارش تکمیل شده‌ای وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = [f"{get_pe('check')} <b>سفارش‌های تکمیل شده</b>\n"]
        for o in orders[:20]:
            lines.append(f"#{o['order_id']} | {o['product']} | {_safe_amount(o['amount_irt'])} تومان")
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:all_orders", IsAdmin())
async def cb_admin_all(callback: CallbackQuery) -> None:
    await callback.answer()
    orders = await get_all_orders()
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(f"{get_pe('ticket')} سفارشی یافت نشد.", reply_markup=admin_back_kb())
    else:
        lines = [f"{get_pe('chart')} <b>تمام سفارش‌ها</b>\n"]
        for o in orders[:20]:
            status_e = {"pending": get_pe('yellow_circle'), "paid": get_pe('green_circle'), "delivered": get_pe('check'), "cancelled": get_pe('cross')}.get(o["status"], "❓")
            lines.append(
                f"#{o['order_id']} | {o['product']} | "
                f"{_safe_amount(o['amount_irt'])} تومان | {status_e} {_status_fa(o['status'])}"
            )
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:finance", IsAdmin())
async def cb_admin_finance(callback: CallbackQuery) -> None:
    await callback.answer()
    today = await get_revenue_by_period("today")
    week = await get_revenue_by_period("week")
    month = await get_revenue_by_period("month")
    total = await get_revenue_by_period("all")

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('chart')} <b>گزارش مالی</b>\n\n"
            f"{get_pe('calendar')} درآمد امروز: <b>{_safe_amount(today)} تومان</b>\n"
            f"{get_pe('calendar')} درآمد هفتگی: <b>{_safe_amount(week)} تومان</b>\n"
            f"{get_pe('calendar')} درآمد ماهانه: <b>{_safe_amount(month)} تومان</b>\n"
            f"{get_pe('money')} درآمد کل: <b>{_safe_amount(total)} تومان</b>\n\n"
            "<i>شامل سفارشات پرداخت شده و انجام شده.</i>",
            reply_markup=admin_finance_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast", IsAdmin())
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.broadcast_message)
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('blue_heart')} <b>ارسال پیام همگانی</b>\n\n"
            "متن پیامی که می‌خواهید به تمام کاربران ارسال شود را بنویسید.\n\n"
            "<i>برای انصراف روی «پنل مدیریت» کلیک کنید.</i>",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.message(AdminStates.broadcast_message)
async def msg_broadcast_text(message: Message, state: FSMContext) -> None:
    if not await IsAdmin()(message):
        return

    text = message.text.strip()
    if len(text) < 2:
        await message.answer("⚠️ پیام نمی‌تواند خالی باشد.")
        return

    await state.update_data(broadcast_text=text)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from utils.emojis import get_premium_id
    preview_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ارسال به همه",
                              callback_data="admin:broadcast:send",
                              style="success",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="انصراف",
                              callback_data="admin:panel",
                              style="danger",
                              icon_custom_emoji_id=get_premium_id("cross"))],
    ])

    await message.answer(
        f"{get_pe('blue_heart')} <b>پیش‌نمایش پیام همگانی:</b>\n\n"
        f"{text}\n\n"
        "این پیام به تمام کاربران ثبت‌شده ارسال خواهد شد.\n"
        "آیا مطمئن هستید؟",
        reply_markup=preview_kb,
    )


@router.callback_query(F.data == "admin:broadcast:send", IsAdmin())
async def cb_broadcast_send(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    if not broadcast_text:
        await callback.answer("⚠️ متن پیام یافت نشد.", show_alert=True)
        return

    await state.clear()

    users = await get_all_users()
    total = len(users)
    sent = 0
    failed = 0

    await callback.message.edit_text(
        f"{get_pe('blue_heart')} <b>در حال ارسال پیام همگانی...</b>\n\n"
        f"{get_pe('users')} تعداد کل کاربران: {total}\n"
        "لطفاً صبر کنید...",
        reply_markup=admin_back_kb(),
    )

    for user_row in users:
        user_id = user_row["user_id"]
        try:
            await callback.bot.send_message(user_id, broadcast_text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('blue_heart')} <b>ارسال پیام همگانی تکمیل شد!</b>\n\n"
            f"{get_pe('users')} کل کاربران: {total}\n"
            f"{get_pe('check')} موفق: {sent}\n"
            f"{get_pe('cross')} ناموفق: {failed}",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:tickets", IsAdmin())
async def cb_admin_tickets(callback: CallbackQuery) -> None:
    """Show open support tickets."""
    await callback.answer()
    open_tickets = await get_open_tickets()
    if not open_tickets:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('ticket')} <b>تیکت‌های باز</b>\n\nهیچ تیکت بازی وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = [f"{get_pe('ticket')} <b>تیکت‌های باز ({len(open_tickets)})</b>\n"]
        for t in open_tickets[:20]:
            lines.append(
                f"#{t['ticket_id']} | {get_pe('user')} {t['full_name']} | "
                f"{get_pe('calendar')} {t['created_at'][:16] if t['created_at'] else '—'}\n"
                f"   💬 {t['message'][:80]}{'…' if len(t['message']) > 80 else ''}"
            )
        lines.append("\nبرای پاسخ به تیکت، از دکمه «📝 پاسخ» روی پیام فوروارد شده استفاده کنید.")
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:prices", IsAdmin())
async def cb_admin_prices(callback: CallbackQuery, state: FSMContext) -> None:
    """Show the inline product list with live DB prices.

    This is the "Single-Message Panel" — the same message is edited
    at each step, keeping the chat clean.
    """
    await callback.answer()
    await state.clear()
    price_rows = await get_all_product_prices()

    if not price_rows:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('money')} <b>هیچ محصولی یافت نشد.</b>",
                reply_markup=admin_back_kb(),
            )
        await callback.answer()
        return

    # Build the list of dicts for the keyboard builder
    products = [
        {
            "product_key": row["product_key"],
            "label": row["label"],
            "usd_price": float(row["usd_price"]),
        }
        for row in price_rows
    ]

    text = (
        f"{get_pe('money')} <b>مدیریت قیمت محصولات</b>\n\n"
        "روی محصول مورد نظر کلیک کنید تا قیمت آن را ویرایش کنید:"
    )

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            text,
            reply_markup=product_list_kb(products),
        )
    await callback.answer()


# ─── ProductCallback: SELECT (show detail view) ─────────────────────

@router.callback_query(
    ProductCallback.filter(F.action == "select"),
    IsAdmin(),
)
async def cb_product_select(
    callback: CallbackQuery,
    callback_data: ProductCallback,
    state: FSMContext,
) -> None:
    """Show product details with an "ویرایش قیمت" inline button.

    This edits the same message — no new messages in the chat.
    """
    await callback.answer()
    await state.clear()
    key = callback_data.product_key

    price_rows = await get_all_product_prices()
    product = next((r for r in price_rows if r["product_key"] == key), None)

    if not product:
        await callback.answer("⚠️ محصول یافت نشد.", show_alert=True)
        return

    label = product["label"]
    price = float(product["usd_price"])

    text = (
        f"{get_pe('box')} <b>جزئیات محصول</b>\n\n"
        f"🏷 نام: <b>{label}</b>\n"
        f"🔑 کلید: <code>{key}</code>\n"
        f"{get_pe('money')} قیمت فعلی: <b>${price:.2f}</b>\n\n"
        f"💡 قیمت نهایی = (قیمت دلاری × نرخ ارز) × (۱ + ۲۰٪ حاشیه)"
    )

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            text,
            reply_markup=product_detail_kb(key, label, price),
        )
    await callback.answer()


# ─── ProductCallback: EDIT (enter FSM state) ────────────────────────

@router.callback_query(
    ProductCallback.filter(F.action == "edit"),
    IsAdmin(),
)
async def cb_product_edit(
    callback: CallbackQuery,
    callback_data: ProductCallback,
    state: FSMContext,
) -> None:
    """Enter FSM state — ask admin to type the new USD price.

    Edits the same message to keep the chat clean.
    """
    await callback.answer()
    key = callback_data.product_key

    # Store the product key in FSM state so we can retrieve it later
    await state.update_data(price_key=key)
    await state.set_state(ProductState.waiting_for_price)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('star')} <b>ویرایش قیمت</b>\n\n"
            f"محصول: <code>{key}</code>\n\n"
            "لطفاً قیمت جدید را به عدد (دلار) ارسال کنید:\n"
            "(مثال: <code>29.99</code>)",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


# ─── ProductState: receive new price text ────────────────────────────

@router.message(ProductState.waiting_for_price)
async def msg_product_price_input(message: Message, state: FSMContext) -> None:
    """Receive the new price, update DB, edit bot message to success.

    CRITICAL UX: Deletes the admin's text message to keep chat clean,
    then edits the original bot message to show confirmation.
    """
    if not await IsAdmin()(message):
        return

    text = message.text.strip()

    # Validate the price input
    try:
        new_price = float(text)
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ لطفاً یک عدد مثبت معتبر ارسال کنید.")
        return

    data = await state.get_data()
    key = data.get("price_key")
    if not key:
        await message.answer("⚠️ خطا: کلید محصول یافت نشد. لطفاً دوباره از پنل شروع کنید.")
        await state.clear()
        return

    old_price = await get_price_or_default(key)
    updated = await update_product_price(key, new_price)

    # CRITICAL UX: Delete the admin's text message to keep chat clean
    try:
        await message.delete()
    except Exception:
        pass  # message may already be deleted or permissions issue

    await state.clear()

    if not updated:
        # Try to find the original message to edit it
        try:
            await message.answer(
                f"⚠️ خطا در به‌روزرسانی قیمت <code>{key}</code>.",
                reply_markup=admin_back_kb(),
            )
        except Exception:
            pass
        return

    # Success: edit the original bot message to show confirmation
    success_text = (
        f"{get_pe('check')} <b>قیمت با موفقیت بروزرسانی شد.</b>\n\n"
        f"{get_pe('box')} محصول: <code>{key}</code>\n"
        f"{get_pe('money')} قیمت قبلی: ${old_price:.2f}\n"
        f"{get_pe('money')} قیمت جدید: <b>${new_price:.2f}</b>\n\n"
        "💡 قیمت نهایی = (قیمت دلاری × نرخ ارز) × (۱ + ۲۰٪ حاشیه)"
    )

    try:
        await message.answer(
            success_text,
            reply_markup=product_edit_success_kb(),
        )
    except Exception:
        pass


# NOTE: The old AdminStates.edit_price_key and edit_price_value handlers
# have been replaced by the inline ProductCallback system above.
# See: cb_admin_prices → cb_product_select → cb_product_edit → msg_product_price_input


@router.callback_query(F.data.startswith("admin:deliver:"), IsAdmin())
async def cb_admin_deliver(callback: CallbackQuery) -> None:
    await callback.answer()
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    await update_order_status(order_id, "delivered")

    if order:
        try:
            await callback.bot.send_message(
                order["user_id"],
                f"{get_pe('check')} <b>سفارش شما تکمیل شد!</b>\n\n"
                f"{get_pe('box')} شماره سفارش: #{order_id}\n"
                f"🛍 محصول: {order['product']}\n\n"
                f"از خرید شما متشکریم! {get_pe('thumbsup')}"
            )
        except Exception as exc:
            logger.warning("Could not notify user %s: %s", order["user_id"], exc)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('check')} سفارش #{order_id} به عنوان <b>تحویل شده</b> ثبت شد.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:cancel:"), IsAdmin())
async def cb_admin_cancel(callback: CallbackQuery) -> None:
    await callback.answer()
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    await update_order_status(order_id, "cancelled")

    if order:
        try:
            await callback.bot.send_message(
                order["user_id"],
                f"{get_pe('cross')} <b>سفارش شما لغو شد.</b>\n\n"
                f"{get_pe('box')} شماره سفارش: #{order_id}\n"
                f"🛍 محصول: {order['product']}\n\n"
                "اگر سؤالی دارید با پشتیبانی تماس بگیرید."
            )
        except Exception as exc:
            logger.warning("Could not notify user %s: %s", order["user_id"], exc)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('cross')} سفارش #{order_id} <b>لغو شد</b>.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()
