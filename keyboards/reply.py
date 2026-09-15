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

# Mapping exact button texts to API service_ids
VIRTUAL_SERVICES_MAP = {
    "تلگرام - پنل اختصاصی 💎": "1",
    "واتساپ ✳️": "2",
    "اینستاگرام 🚀": "3",
    "چنج نامبر 🗳": "4",
    "گوگل 🔍": "5",
    "فیسبوک 📬": "6",
    "ایمو 📶": "7",
    "وی چت 💬": "8",
    "ایکس ❎": "9",
    "تیک تاک ⌚": "10",
    "لایکی 💖": "11",
    "تیندر 🔥": "12",
    "سینگال 📶": "13",
    "یاهو 🌀": "14",
    "وبمانی 🌐": "15",
    "چت جی پی تی 🤖": "16",
    "نتفلیکس 💢": "17",
    "پیپال 🧾": "18",
    "استیم 🎮": "19",
    "مایکروسافت 💻": "20",
    "لاین 🧩": "21",
    "اوبر 🚕": "22",
    "علی بابا ☂️": "23",
    "آمازون 🐝": "24",
    "دیسکورد 🚹": "25",
    "ای بای 🛒": "26",
    "اپل 🍎": "27",
    "اکسپرس 🛍": "28",
    "ویکی 🐳": "29",
    "پاپارا 💸": "30",
    "گوگل ویس 🟢": "31",
}


def virtual_services_reply_kb() -> ReplyKeyboardMarkup:
    """Build a ReplyKeyboardMarkup for virtual-number service selection.

    Layout:
      Row 0:  تلگرام - پنل اختصاصی 💎  (full width, top)
      Grid:   3 columns for all other apps (RTL reversed)
      Footer: 🔙 بازگشت
    """
    builder = ReplyKeyboardBuilder()

    # Top Row — Telegram dedicated (full width)
    builder.row(KeyboardButton(text="تلگرام - پنل اختصاصی 💎"))

    # Rest of the apps in 3-column rows (reversed for RTL layout)
    app_names = list(VIRTUAL_SERVICES_MAP.keys())[1:]
    buttons = [KeyboardButton(text=name) for name in app_names]

    for i in range(0, len(buttons), 3):
        chunk = buttons[i:i + 3]
        builder.row(*chunk[::-1])  # Reverse for RTL layout

    # Back button
    builder.row(KeyboardButton(text="🔙 بازگشت"))

    return builder.as_markup(resize_keyboard=True)
