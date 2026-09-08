"""
Persistent reply keyboards for the admin panel.
These keyboards sit at the bottom of the chat when an admin is active.

Labels in Persian (فارسی).

Button icons use Telegram Premium custom emojis via the
``icon_custom_emoji_id`` parameter (Bot API 9.4+), with colored ``style``.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils.emojis import get_premium_id


def admin_reply_kb() -> ReplyKeyboardMarkup:
    """Admin reply keyboard — shown when an admin enters the panel.

    Buttons:
        ⚙️ ورود به پنل مدیریت  — opens the inline admin dashboard
        🛒 بازگشت به منوی اصلی — returns to the normal user keyboard
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="ورود به پنل مدیریت",
                    style="primary",
                    icon_custom_emoji_id=get_premium_id("gear"),
                ),
            ],
            [
                KeyboardButton(
                    text="بازگشت به منوی اصلی",
                    style="success",
                    icon_custom_emoji_id=get_premium_id("home"),
                ),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )
