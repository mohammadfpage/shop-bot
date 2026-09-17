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
# Shiznumber API — slugs instead of numeric IDs.
# The services map (display name → slug) is fetched live from the
# Shiznumber API via get_services_map() and is always required here.


def virtual_services_reply_kb(services_map: dict[str, str]) -> ReplyKeyboardMarkup:
    """Build a ReplyKeyboardMarkup for virtual-number service selection.

    Telegram is pinned to its own row, all other services are laid out
    in a 2-column RTL grid, capped at ~200 buttons to stay within
    Telegram's ReplyKeyboardMarkup size limits.

    Layout:
      Row: تلگرام 💎
      Row: واتساپ ✳️  |  اینستاگرام 🚀
      ...
      Footer: 🔙 بازگشت
    """
    builder = ReplyKeyboardBuilder()

    # Pin Telegram to the top row if it exists
    tg_key = next((k for k in services_map.keys() if "تلگرام" in k), None)
    if tg_key:
        builder.row(KeyboardButton(text=tg_key))

    # All other services in 2-column RTL grid (max 200 buttons)
    other_apps = [name for name in services_map.keys() if name != tg_key]
    buttons = [KeyboardButton(text=name) for name in other_apps][:200]
    for i in range(0, len(buttons), 2):
        builder.row(*buttons[i : i + 2][::-1])  # reversed for RTL

    # Back button
    builder.row(KeyboardButton(text="🔙 بازگشت"))

    return builder.as_markup(resize_keyboard=True)
