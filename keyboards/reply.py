"""
Persistent reply keyboards for the bot's main menu.
These keyboards sit at the bottom of the chat and persist across messages.

Labels in Persian (فارسی).
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_reply_kb() -> ReplyKeyboardMarkup:
    """Default reply keyboard shown on /start and throughout the conversation.

    Buttons:
        🛍 فروشگاه          — opens inline shop menu
        👤 پروفایل           — shows user profile
        🎧 پشتیبانی          — opens ticket flow
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛍 فروشگاه"),
            ],
            [
                KeyboardButton(text="👤 پروفایل"),
                KeyboardButton(text="🎧 پشتیبانی"),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )
