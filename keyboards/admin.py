"""
Inline keyboards for the admin panel.
All labels in Persian (فارسی).
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_panel_kb(user_count: int = 0) -> InlineKeyboardMarkup:
    count_str = f" ({user_count})" if user_count else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 کاربران{count_str}", callback_data="admin:users_stat")],
        [InlineKeyboardButton(text="📋 سفارش‌های در انتظار", callback_data="admin:pending")],
        [InlineKeyboardButton(text="🔄 مدیریت سفارشات پرداخت شده", callback_data="admin:paid_orders")],
        [InlineKeyboardButton(text="✅ سفارش‌های تکمیل شده", callback_data="admin:completed")],
        [InlineKeyboardButton(text="💰 مدیریت قیمت محصولات", callback_data="admin:prices")],
        [InlineKeyboardButton(text="📊 تمام سفارش‌ها", callback_data="admin:all_orders")],
        [InlineKeyboardButton(text="📈 گزارش مالی", callback_data="admin:finance")],
        [InlineKeyboardButton(text="📣 پیام همگانی", callback_data="admin:broadcast")],
    ])


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تحویل داده شد", callback_data=f"admin:deliver:{order_id}")],
        [InlineKeyboardButton(text="❌ لغو سفارش", callback_data=f"admin:cancel:{order_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:panel")],
    ])


def admin_paid_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ انجام شد", callback_data=f"admin:complete:{order_id}")],
        [InlineKeyboardButton(text="❌ لغو شد", callback_data=f"admin:cancel:{order_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:paid_orders")],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 پنل مدیریت", callback_data="admin:panel")],
    ])


def admin_finance_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 به‌روزرسانی", callback_data="admin:finance")],
        [InlineKeyboardButton(text="🔙 پنل مدیریت", callback_data="admin:panel")],
    ])


def admin_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ارسال", callback_data="admin:broadcast:send")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="admin:panel")],
    ])
