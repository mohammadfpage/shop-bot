"""
Handler: Admin panel.

Commands:
    /admin  — open admin dashboard (IsAdmin protected)
    /stats  — quick bot statistics (IsAdmin protected)
    /users  — list registered users (IsAdmin protected)

Reply keyboard:
    "⚙️ ورود به پنل مدیریت"  — same as /admin
    "🔙 بازگشت به منوی اصلی" — return to normal user keyboard

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
from states.states import AdminStates
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

@router.message(F.text == "⚙️ ورود به پنل مدیریت", IsAdmin())
async def reply_btn_admin_panel(message: Message, state: FSMContext) -> None:
    """Open admin dashboard when the admin taps the reply keyboard button."""
    await _show_admin_dashboard(message, state)


@router.message(F.text == "🔙 بازگشت به منوی اصلی", IsAdmin())
async def reply_btn_back_to_main(message: Message, state: FSMContext) -> None:
    """Return to the normal user keyboard."""
    await state.clear()
    await message.answer(
        "🏠 <b>منوی اصلی</b>\nیک سرویس را انتخاب کنید:",
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
        f"📊 <b>آمار سریع ربات</b>\n\n"
        f"👥 کل کاربران: <b>{user_count}</b>\n"
        f"🟡 سفارشات در انتظار: <b>{pending}</b>\n"
        f"🟢 پرداخت شده: <b>{paid}</b>\n"
        f"✅ انجام شده: <b>{delivered}</b>\n"
        f"❌ لغو شده: <b>{cancelled}</b>\n\n"
        f"🎫 تیکت‌های باز: <b>{len(open_tickets)}</b>\n\n"
        f"💰 درآمد امروز: <b>{_safe_amount(today_rev)} تومان</b>\n"
        f"📆 درآمد ماهانه: <b>{_safe_amount(month_rev)} تومان</b>\n"
        f"💎 درآمد کل: <b>{_safe_amount(total_rev)} تومان</b>",
        reply_markup=admin_reply_kb(),
    )


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
        await message.answer("👥 هیچ کاربری ثبت‌نام نکرده است.", reply_markup=admin_reply_kb())
        return

    lines = [f"👥 <b>لیست کاربران</b> (تا ۵۰ نفر آخر)\n"]
    for r in rows:
        admin_tag = " 🛡" if r["is_admin"] else ""
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
    guide_text = (
        "📖 <b>راهنمای مدیران</b>\n\n"

        "🔹 <b>📊 آمار کاربران</b>\n"
        "   تعداد کل کاربران ثبت‌شده و وضعیت سفارشات را نمایش می‌دهد.\n\n"

        "🔹 <b>✉️ ارسال پیام همگانی (Broadcast)</b>\n"
        "   متنی بنویسید و آن را به تمام کاربران ربات ارسال کنید.\n"
        "   پیش از ارسال، پیش‌نمایشی از پیام نمایش داده می‌شود.\n"
        "   پس از تأیید، ربات به هر کاربر یک پیام ارسال می‌کند.\n\n"

        "🔹 <b>🎫 مدیریت تیکت‌ها</b>\n"
        "   وقتی کاربری تیکت پشتیبانی ارسال کند، پیام او برای شما\n"
        "   فوروارد می‌شود. روی دکمه «📝 پاسخ» کلیک کنید و پاسخ خود\n"
        "   را بنویسید. پاسخ شما برای کاربر ارسال خواهد شد.\n"
        "   همچنین می‌توانید تیکت را بدون پاسخ با «✅ بستن تیکت» ببندید.\n\n"

        "🔹 <b>💰 مدیریت قیمت محصولات</b>\n"
        "   قیمت پایه محصولات (به دلار) را ویرایش کنید.\n"
        "   قیمت نهایی = (قیمت دلاری × نرخ لحظه‌ای ارز) × (۱ + ۲۰٪)\n\n"

        "🔹 <b>📈 گزارش مالی</b>\n"
        "   درآمد امروز، هفتگی، ماهانه و کل را مشاهده کنید.\n\n"

        "🔹 <b>📋 سفارشات</b>\n"
        "   سفارشات در انتظار، پرداخت شده، تکمیل شده و لغو شده.\n"
        "   سفارشات پرداخت شده را پس از انجام، به «انجام شده» تغییر\n"
        "   دهید تا به کاربر اطلاع‌رسانی شود.\n\n"

        "🔑 <b>دستورات سریع:</b>\n"
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
        f"🔧 <b>پنل مدیریت</b>\n\n"
        f"👥 تعداد کاربران: <b>{user_count}</b>\n\n"
        "یک عملیات را انتخاب کنید:",
        reply_markup=admin_panel_kb(user_count),
    )


# ═══════════════════════════════════════════════════════════════════════
#  INLINE CALLBACK HANDLERS (all protected by IsAdmin filter)
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:panel", IsAdmin())
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_count = await get_total_users()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"🔧 <b>پنل مدیریت</b>\n\n"
            f"👥 تعداد کاربران: <b>{user_count}</b>\n\n"
            "یک عملیات را انتخاب کنید:",
            reply_markup=admin_panel_kb(user_count),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:users_stat", IsAdmin())
async def cb_admin_users_stat(callback: CallbackQuery) -> None:
    user_count = await get_total_users()
    pending_count = await get_order_count_by_status("pending")
    paid_count = await get_order_count_by_status("paid")
    delivered_count = await get_order_count_by_status("delivered")
    cancelled_count = await get_order_count_by_status("cancelled")

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"👥 <b>آمار کاربران و سفارشات</b>\n\n"
            f"👤 کل کاربران: <b>{user_count}</b>\n"
            f"🟡 سفارشات در انتظار: <b>{pending_count}</b>\n"
            f"🟢 سفارشات پرداخت شده: <b>{paid_count}</b>\n"
            f"✅ سفارشات انجام شده: <b>{delivered_count}</b>\n"
            f"❌ سفارشات لغو شده: <b>{cancelled_count}</b>",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:pending", IsAdmin())
async def cb_admin_pending(callback: CallbackQuery) -> None:
    orders = await get_all_orders(status="pending")
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "📋 سفارش در انتظاری وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = ["📋 <b>سفارش‌های در انتظار</b>\n"]
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
    orders = await get_all_orders(status="paid")
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "📋 سفارش پرداخت شده‌ای برای پردازش وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = ["🔄 <b>سفارشات پرداخت شده (نیاز به پردازش)</b>\n"]
        for o in orders[:20]:
            lines.append(
                f"#{o['order_id']} | {o['product']} | "
                f"{_safe_amount(o['amount_irt'])} تومان | کاربر: {o['user_id']}"
            )
        lines.append("\nروی سفارش مورد نظر کلیک کنید:")
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = []
        for o in orders[:10]:
            buttons.append([InlineKeyboardButton(
                text=f"#{o['order_id']} — {o['product'][:30]}",
                callback_data=f"admin:view_paid:{o['order_id']}"
            )])
        buttons.append([InlineKeyboardButton(text="🔙 پنل مدیریت", callback_data="admin:panel")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:view_paid:"), IsAdmin())
async def cb_admin_view_paid(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[3])
    order = await get_order(order_id)
    if not order:
        await callback.answer("⚠️ سفارش یافت نشد.", show_alert=True)
        return

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"📄 <b>جزئیات سفارش #{order['order_id']}</b>\n\n"
            f"👤 شناسه کاربر: <code>{order['user_id']}</code>\n"
            f"📦 محصول: {order['product']}\n"
            f"📝 جزئیات: {order['details'] or '—'}\n"
            f"💰 مبلغ: {_safe_amount(order['amount_irt'])} تومان\n"
            f"📅 تاریخ: {order['created_at'][:16] if order['created_at'] else '—'}\n"
            f"📊 وضعیت: 🟢 پرداخت شده\n\n"
            "عملیات مورد نظر را انتخاب کنید:",
            reply_markup=admin_paid_order_kb(order_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:complete:"), IsAdmin())
async def cb_admin_complete(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await callback.answer("⚠️ سفارش یافت نشد.", show_alert=True)
        return

    await update_order_status(order_id, "delivered")

    try:
        await callback.bot.send_message(
            order["user_id"],
            f"✅ <b>سفارش شما تکمیل شد!</b>\n\n"
            f"📦 شماره سفارش: #{order_id}\n"
            f"🛍 محصول: {order['product']}\n\n"
            "از خرید شما متشکریم! 🙏"
        )
    except Exception as exc:
        logger.warning("Could not notify user %s: %s", order["user_id"], exc)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"✅ سفارش #{order_id} به عنوان <b>انجام شده</b> ثبت شد.\n"
            f"👤 به کاربر <code>{order['user_id']}</code> اطلاع‌رسانی شد.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:completed", IsAdmin())
async def cb_admin_completed(callback: CallbackQuery) -> None:
    orders = await get_all_orders(status="delivered")
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "✅ هنوز سفارش تکمیل شده‌ای وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = ["✅ <b>سفارش‌های تکمیل شده</b>\n"]
        for o in orders[:20]:
            lines.append(f"#{o['order_id']} | {o['product']} | {_safe_amount(o['amount_irt'])} تومان")
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:all_orders", IsAdmin())
async def cb_admin_all(callback: CallbackQuery) -> None:
    orders = await get_all_orders()
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("📋 سفارشی یافت نشد.", reply_markup=admin_back_kb())
    else:
        lines = ["📊 <b>تمام سفارش‌ها</b>\n"]
        for o in orders[:20]:
            status_e = {"pending": "🟡", "paid": "🟢", "delivered": "✅", "cancelled": "❌"}.get(o["status"], "❓")
            lines.append(
                f"#{o['order_id']} | {o['product']} | "
                f"{_safe_amount(o['amount_irt'])} تومان | {status_e} {_status_fa(o['status'])}"
            )
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:finance", IsAdmin())
async def cb_admin_finance(callback: CallbackQuery) -> None:
    today = await get_revenue_by_period("today")
    week = await get_revenue_by_period("week")
    month = await get_revenue_by_period("month")
    total = await get_revenue_by_period("all")

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"📈 <b>گزارش مالی</b>\n\n"
            f"🕐 درآمد امروز: <b>{_safe_amount(today)} تومان</b>\n"
            f"📅 درآمد هفتگی: <b>{_safe_amount(week)} تومان</b>\n"
            f"📆 درآمد ماهانه: <b>{_safe_amount(month)} تومان</b>\n"
            f"💰 درآمد کل: <b>{_safe_amount(total)} تومان</b>\n\n"
            "<i>شامل سفارشات پرداخت شده و انجام شده.</i>",
            reply_markup=admin_finance_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast", IsAdmin())
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast_message)
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "📣 <b>ارسال پیام همگانی</b>\n\n"
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
    preview_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ارسال به همه", callback_data="admin:broadcast:send")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="admin:panel")],
    ])

    await message.answer(
        f"📣 <b>پیش‌نمایش پیام همگانی:</b>\n\n"
        f"{text}\n\n"
        "این پیام به تمام کاربران ثبت‌شده ارسال خواهد شد.\n"
        "آیا مطمئن هستید؟",
        reply_markup=preview_kb,
    )


@router.callback_query(F.data == "admin:broadcast:send", IsAdmin())
async def cb_broadcast_send(callback: CallbackQuery, state: FSMContext) -> None:
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
        f"📣 <b>در حال ارسال پیام همگانی...</b>\n\n"
        f"👥 تعداد کل کاربران: {total}\n"
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
            f"📣 <b>ارسال پیام همگانی تکمیل شد!</b>\n\n"
            f"👥 کل کاربران: {total}\n"
            f"✅ موفق: {sent}\n"
            f"❌ ناموفق: {failed}",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:tickets", IsAdmin())
async def cb_admin_tickets(callback: CallbackQuery) -> None:
    """Show open support tickets."""
    open_tickets = await get_open_tickets()
    if not open_tickets:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "🎫 <b>تیکت‌های باز</b>\n\nهیچ تیکت بازی وجود ندارد.",
                reply_markup=admin_back_kb(),
            )
    else:
        lines = [f"🎫 <b>تیکت‌های باز ({len(open_tickets)})</b>\n"]
        for t in open_tickets[:20]:
            lines.append(
                f"#{t['ticket_id']} | 👤 {t['full_name']} | "
                f"📅 {t['created_at'][:16] if t['created_at'] else '—'}\n"
                f"   💬 {t['message'][:80]}{'…' if len(t['message']) > 80 else ''}"
            )
        lines.append("\nبرای پاسخ به تیکت، از دکمه «📝 پاسخ» روی پیام فوروارد شده استفاده کنید.")
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:prices", IsAdmin())
async def cb_admin_prices(callback: CallbackQuery, state: FSMContext) -> None:
    price_rows = await get_all_product_prices()
    lines = ["💰 <b>قیمت پایه محصولات (USD)</b>\n"]
    for row in price_rows:
        lines.append(f"  <code>{row['product_key']}</code> = ${row['usd_price']:.2f} — {row['label']}")
    lines.append("\n🔑 کلید محصول مورد نظر را ارسال کنید (مثال: <code>chatgpt_premium</code>).")

    await state.set_state(AdminStates.edit_price_key)
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminStates.edit_price_key)
async def msg_admin_price_key(message: Message, state: FSMContext) -> None:
    if not await IsAdmin()(message):
        return

    key = message.text.strip()
    price_rows = await get_all_product_prices()
    valid_keys = [row["product_key"] for row in price_rows]

    if key not in valid_keys:
        await message.answer(
            f"⚠️ کلید <code>{key}</code> یافت نشد.\nکلیدهای معتبر:\n" +
            "\n".join(f"<code>{k}</code>" for k in valid_keys),
            reply_markup=admin_back_kb(),
        )
        return

    current_price = await get_price_or_default(key)
    await state.update_data(price_key=key)
    await state.set_state(AdminStates.edit_price_value)
    await message.answer(
        f"قیمت فعلی <code>{key}</code>: <b>${current_price:.2f}</b>\n\n"
        "قیمت جدید به دلار را ارسال کنید (مثال: <code>29.99</code>):",
        reply_markup=admin_back_kb(),
    )


@router.message(AdminStates.edit_price_value)
async def msg_admin_price_value(message: Message, state: FSMContext) -> None:
    if not await IsAdmin()(message):
        return

    text = message.text.strip()
    try:
        new_price = float(text)
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ لطفاً یک عدد مثبت معتبر ارسال کنید.", reply_markup=admin_back_kb())
        return

    data = await state.get_data()
    key = data["price_key"]
    old_price = await get_price_or_default(key)

    updated = await update_product_price(key, new_price)
    if not updated:
        await message.answer(
            f"⚠️ خطا در به‌روزرسانی قیمت <code>{key}</code>.",
            reply_markup=admin_back_kb(),
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"✅ قیمت با موفقیت به‌روزرسانی شد!\n\n"
        f"<code>{key}</code>: ${old_price:.2f} → <b>${new_price:.2f}</b>\n\n"
        "قیمت نهایی با نرخ لحظه‌ای ارز + حاشیه سود ۲۰٪ محاسبه می‌شود.",
        reply_markup=admin_back_kb(),
    )


@router.callback_query(F.data.startswith("admin:deliver:"), IsAdmin())
async def cb_admin_deliver(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    await update_order_status(order_id, "delivered")

    if order:
        try:
            await callback.bot.send_message(
                order["user_id"],
                f"✅ <b>سفارش شما تکمیل شد!</b>\n\n"
                f"📦 شماره سفارش: #{order_id}\n"
                f"🛍 محصول: {order['product']}\n\n"
                "از خرید شما متشکریم! 🙏"
            )
        except Exception as exc:
            logger.warning("Could not notify user %s: %s", order["user_id"], exc)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"✅ سفارش #{order_id} به عنوان <b>تحویل شده</b> ثبت شد.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:cancel:"), IsAdmin())
async def cb_admin_cancel(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    await update_order_status(order_id, "cancelled")

    if order:
        try:
            await callback.bot.send_message(
                order["user_id"],
                f"❌ <b>سفارش شما لغو شد.</b>\n\n"
                f"📦 شماره سفارش: #{order_id}\n"
                f"🛍 محصول: {order['product']}\n\n"
                "اگر سؤالی دارید با پشتیبانی تماس بگیرید."
            )
        except Exception as exc:
            logger.warning("Could not notify user %s: %s", order["user_id"], exc)

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"❌ سفارش #{order_id} <b>لغو شد</b>.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()
