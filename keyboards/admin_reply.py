"""
Persistent reply keyboards for the admin panel.
These keyboards sit at the bottom of the chat when an admin is active.

Labels in Persian (فارسی).
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def admin_reply_kb() -> ReplyKeyboardMarkup:
    """Admin reply keyboard — shown when an admin enters the panel.

    Buttons:
        ⚙️ ورود به پنل مدیریت  — opens the inline admin dashboard
        🛒 بازگشت به منوی اصلی — returns to the normal user keyboard
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚙️ ورود به پنل مدیریت"),
            ],
            [
                KeyboardButton(text="🔙 بازگشت به منوی اصلی"),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )
