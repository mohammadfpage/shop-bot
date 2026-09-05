"""
Persistent reply keyboards for the bot's main menu.
These keyboards sit at the bottom of the chat and persist across messages.

Labels in Persian (فارسی).
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_reply_kb() -> ReplyKeyboardMarkup:
    """Default reply keyboard shown on /start and throughout the conversation.

    Buttons:
        🛒 محصولات / خرید    — opens inline shop menu
        👤 پروفایل من        — shows user profile
        💵 قیمت روز ارز     — shows cached exchange rates
        🎧 پشتیبانی (تیکت)  — opens ticket flow
        📚 راهنما            — shows help text
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛒 محصولات / خرید"),
            ],
            [
                KeyboardButton(text="💵 قیمت روز ارز"),
            ],
            [
                KeyboardButton(text="👤 پروفایل من"),
                KeyboardButton(text="🎧 پشتیبانی (تیکت)"),
            ],
            [
                KeyboardButton(text="📚 راهنما"),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )
