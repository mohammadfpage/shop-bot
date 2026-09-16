"""
Persistent reply keyboards for the bot's main menu.
These keyboards sit at the bottom of the chat and persist across messages.

Labels in Persian (فارسی).

Button icons use Telegram Premium custom emojis via the
``icon_custom_emoji_id`` parameter (Bot API 9.4+), with colored ``style``.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from utils.emojis import get_premium_id


def main_reply_kb() -> ReplyKeyboardMarkup:
    """Default reply keyboard shown on /start and throughout the conversation.

    2-column persistent navigation:
        🛍 فروشگاه  |  👤 پروفایل
        🎧 پشتیبانی |  📋 سفارشات
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="فروشگاه",
                    style="primary",
                    icon_custom_emoji_id=get_premium_id("store"),
                ),
                KeyboardButton(
                    text="پروفایل",
                    style="primary",
                    icon_custom_emoji_id=get_premium_id("user"),
                ),
            ],
            [
                KeyboardButton(
                    text="پشتیبانی",
                    style="primary",
                    icon_custom_emoji_id=get_premium_id("call"),
                ),
                KeyboardButton(
                    text="سفارشات",
                    style="primary",
                    icon_custom_emoji_id=get_premium_id("box"),
                ),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )


# ─── Virtual Number Services (Reply Keyboard) ──────────────────────
# Shiznumber API — slugs instead of numeric IDs
# The static map below is used as a fallback only; the live map is
# fetched dynamically from the Shiznumber API via get_services_map().

SHIZ_SERVICES_MAP = {
    "تلگرام 💎": "telegram",
    "مایکروسافت 💻": "microsoft",
    "تیندر 🔥": "tinder",
    "واتساپ ✳️": "whatsapp",
    "اینستاگرام 🚀": "instagram",
    "فیسبوک 📬": "facebook",
    "توییتر 🐦": "twitter",
    "گوگل / جیمیل 🔍": "google",
}

# Legacy alias — kept so other modules that import VIRTUAL_SERVICES_MAP
# don't break at import time (they should migrate to SHIZ_SERVICES_MAP).
VIRTUAL_SERVICES_MAP = SHIZ_SERVICES_MAP


def virtual_services_reply_kb(services_map: dict[str, str] | None = None) -> ReplyKeyboardMarkup:
    """Build a ReplyKeyboardMarkup for virtual-number service selection.

    If *services_map* is provided (fetched dynamically from the API),
    those services are used.  Otherwise falls back to the hardcoded
    ``SHIZ_SERVICES_MAP``.

    Layout (2-column RTL grid) with Telegram pinned to the top:
      Row: تلگрам 💎
      Row: واتساپ ✳️  |  اینستاگرام 🚀
      ...
      Footer: 🔙 بازگشت
    """
    svc = services_map or SHIZ_SERVICES_MAP
    builder = ReplyKeyboardBuilder()

    # Pin Telegram to the top row if it exists
    tg_key = next((k for k in svc if "تلگرام" in k), None)
    if tg_key:
        builder.row(KeyboardButton(text=tg_key))

    # All other services in 2-column RTL grid
    other_keys = [k for k in svc if k != tg_key]
    buttons = [KeyboardButton(text=name) for name in other_keys]
    for i in range(0, len(buttons), 2):
        builder.row(*buttons[i : i + 2][::-1])  # reversed for RTL

    # Back button
    builder.row(KeyboardButton(text="🔙 بازگشت"))

    return builder.as_markup(resize_keyboard=True)
