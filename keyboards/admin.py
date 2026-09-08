"""
Inline keyboards for the admin panel.
All labels in Persian (فارسی).

Button icons use Telegram Premium custom emojis via the
``icon_custom_emoji_id`` parameter (Bot API 9.4+). The button text stays
plain Unicode while the icon is rendered as the Premium custom emoji.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils.emojis import get_premium_id


def admin_panel_kb(user_count: int = 0) -> InlineKeyboardMarkup:
    count_str = f" ({user_count})" if user_count else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"کاربران{count_str}",
                              callback_data="admin:users_stat",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("users"))],
        [InlineKeyboardButton(text="ارسال پیام همگانی",
                              callback_data="admin:broadcast",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("call"))],
        [InlineKeyboardButton(text="مدیریت تیکت‌ها",
                              callback_data="admin:tickets",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("ticket"))],
        [InlineKeyboardButton(text="سفارش‌های در انتظار",
                              callback_data="admin:pending",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("yellow_circle"))],
        [InlineKeyboardButton(text="مدیریت سفارشات پرداخت شده",
                              callback_data="admin:paid_orders",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("green_circle"))],
        [InlineKeyboardButton(text="سفارش‌های تکمیل شده",
                              callback_data="admin:completed",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="مدیریت قیمت محصولات",
                              callback_data="admin:prices",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("money"))],
        [InlineKeyboardButton(text="تمام سفارش‌ها",
                              callback_data="admin:all_orders",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("chart"))],
        [InlineKeyboardButton(text="گزارش مالی",
                              callback_data="admin:finance",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("chart"))],
        [InlineKeyboardButton(text="راهنمای مدیران",
                              callback_data="admin:guide",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("question"))],
    ])


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تحویل داده شد",
                              callback_data=f"admin:deliver:{order_id}",
                              style="success",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="لغو سفارش",
                              callback_data=f"admin:cancel:{order_id}",
                              style="danger",
                              icon_custom_emoji_id=get_premium_id("cross"))],
        [InlineKeyboardButton(text="بازگشت",
                              callback_data="admin:panel",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("down"))],
    ])


def admin_paid_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="انجام شد",
                              callback_data=f"admin:complete:{order_id}",
                              style="success",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="لغو شد",
                              callback_data=f"admin:cancel:{order_id}",
                              style="danger",
                              icon_custom_emoji_id=get_premium_id("cross"))],
        [InlineKeyboardButton(text="بازگشت",
                              callback_data="admin:paid_orders",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("down"))],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="پنل مدیریت",
                              callback_data="admin:panel",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("home"))],
    ])


def admin_finance_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="به‌روزرسانی",
                              callback_data="admin:finance",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("exchange"))],
        [InlineKeyboardButton(text="پنل مدیریت",
                              callback_data="admin:panel",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("home"))],
    ])


def admin_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ارسال",
                              callback_data="admin:broadcast:send",
                              style="success",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="انصراف",
                              callback_data="admin:panel",
                              style="danger",
                              icon_custom_emoji_id=get_premium_id("cross"))],
    ])
