"""
Persistent reply keyboards for the bot's main menu.
These keyboards sit at the bottom of the chat and persist across messages.

Labels in Persian (فارسی).

Button icons use Telegram Premium custom emojis via the
``icon_custom_emoji_id`` parameter (Bot API 9.4+), with colored ``style``.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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
