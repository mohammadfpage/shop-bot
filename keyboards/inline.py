"""
Inline keyboards for the user-facing side of the bot.
All labels in Persian (فارسی).
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# ─── Main Menu ───────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ تلگرام پرمیوم", callback_data="menu:premium")],
        [InlineKeyboardButton(text="🎁 گیفت تلگرام / استارز", callback_data="menu:stars")],
        [InlineKeyboardButton(text="📱 شماره مجازی", callback_data="menu:virtual")],
        [InlineKeyboardButton(text="🤖 اکانت هوش مصنوعی", callback_data="menu:ai_accounts")],
        [InlineKeyboardButton(text="🎨 خدمات طراحی", callback_data="menu:design")],
        [InlineKeyboardButton(text="🛡 امنیت صفحه", callback_data="menu:security")],
        [InlineKeyboardButton(text="📊 قیمت لحظه‌ای ارزها", callback_data="menu:market_rates")],
        [InlineKeyboardButton(text="📋 پیگیری سفارشات", callback_data="menu:my_orders")],
    ])


# ─── Telegram Premium ────────────────────────────────────────────────

def premium_duration_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 ماهانه", callback_data="premium:monthly")],
        [InlineKeyboardButton(text="📅 سه‌ماهه", callback_data="premium:quarterly")],
        [InlineKeyboardButton(text="📅 شش‌ماهه", callback_data="premium:semi_annual")],
        [InlineKeyboardButton(text="📅 سالانه", callback_data="premium:yearly")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")],
    ])


def premium_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 برای خودم", callback_data="premium:target:self")],
        [InlineKeyboardButton(text="👥 برای شخص دیگر", callback_data="premium:target:other")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="premium:back")],
    ])


# ─── Telegram Stars ─────────────────────────────────────────────────

def stars_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 برای خودم", callback_data="stars:target:self")],
        [InlineKeyboardButton(text="👥 برای شخص دیگر", callback_data="stars:target:other")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="stars:back")],
    ])


# ─── Virtual Numbers ────────────────────────────────────────────────

def virtual_country_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇮🇷 ایران", callback_data="vn:country:iran")],
        [InlineKeyboardButton(text="🇺🇸 آمریکا", callback_data="vn:country:usa")],
        [InlineKeyboardButton(text="🇬🇧 بریتانیا", callback_data="vn:country:uk")],
        [InlineKeyboardButton(text="🇩🇪 آلمان", callback_data="vn:country:germany")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")],
    ])


# ─── AI Accounts ────────────────────────────────────────────────────

def ai_platform_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ChatGPT Plus", callback_data="ai:platform:chatgpt")],
        [InlineKeyboardButton(text="✨ Gemini Advanced", callback_data="ai:platform:gemini")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")],
    ])


# ─── Design Services ────────────────────────────────────────────────

def design_tier_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ طراحی با هوش مصنوعی", callback_data="design:tier:ai")],
        [InlineKeyboardButton(text="2️⃣ طراحی ساده", callback_data="design:tier:simple")],
        [InlineKeyboardButton(text="3️⃣ طراحی حرفه‌ای", callback_data="design:tier:normal")],
        [InlineKeyboardButton(text="4️⃣ طراحی ویژه", callback_data="design:tier:special")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")],
    ])


# ─── Page Security ──────────────────────────────────────────────────

def security_tariff_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 پایه", callback_data="security:tariff:basic")],
        [InlineKeyboardButton(text="🥈 استاندارد", callback_data="security:tariff:standard")],
        [InlineKeyboardButton(text="🥇 پیشرفته", callback_data="security:tariff:advanced")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")],
    ])


# ─── Market Rates ───────────────────────────────────────────────────

def market_rates_refresh_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 به‌روزرسانی", callback_data="menu:market_rates")],
        [InlineKeyboardButton(text="🔙 بازگشت به منو", callback_data="menu:back")],
    ])


# ─── Generic payment ────────────────────────────────────────────────

def payment_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت", callback_data="pay:confirm")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="pay:cancel")],
    ])


def pay_link_kb(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت از طریق زرین‌پال", url=pay_url)],
        [InlineKeyboardButton(text="✅ پرداخت کردم", callback_data="pay:check")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="pay:cancel")],
    ])


# ─── Back to menu ───────────────────────────────────────────────────

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت به منو", callback_data="menu:back")],
    ])
