"""
Inline keyboards for the user-facing side of the bot.
All labels in Persian (فارسی).
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.callback_data import WelcomeCallback

# ─── Welcome Inline Keyboard ─────────────────────────────────────────

def welcome_inline_kb() -> InlineKeyboardMarkup:
    """Inline keyboard attached directly under the /start welcome text.

    Provides quick actions so the user doesn't have to scroll
    through the reply keyboard to get started.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🛒 مشاهده دسته‌بندی‌ها",
                callback_data=WelcomeCallback(action="categories").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔥 تخفیف‌های ویژه",
                callback_data=WelcomeCallback(action="deals").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 پیگیری سفارشات",
                callback_data="menu:my_orders",
            ),
        ],
    ])


# ─── Dynamic Main Menu (shop menu with live DB prices) ────────────────

# Map each menu callback_data to the product_keys that belong to it.
# The lowest-priced product in the group is used as the "starting at" price.
_CATEGORY_PRODUCT_KEYS: dict[str, tuple[str, ...]] = {
    "menu:premium": (
        "telegram_premium_monthly",
        "telegram_premium_quarterly",
        "telegram_premium_semi_annual",
        "telegram_premium_yearly",
    ),
    "menu:stars":       ("telegram_stars_per_50",),
    "menu:virtual":     ("virtual_number",),
    "menu:ai_accounts": ("chatgpt_premium", "gemini_premium"),
    "menu:design": (
        "design_ai",
        "design_simple",
        "design_normal",
        "design_special",
    ),
    "menu:security":    (),  # tariffs are not in product_prices table
}

# Human-readable labels per category
_CATEGORY_LABELS: dict[str, str] = {
    "menu:premium":    "⭐ تلگرام پرمیوم",
    "menu:stars":      "🎁 گیفت تلگرام / استارز",
    "menu:virtual":    "📱 شماره مجازی",
    "menu:ai_accounts":"🤖 اکانت هوش مصنوعی",
    "menu:design":     "🎨 خدمات طراحی",
    "menu:security":   "🛡 امنیت صفحه",
}

# Categories shown WITHOUT a price suffix
_NO_PRICE_CATEGORIES: frozenset[str] = frozenset({
    "menu:market_rates",
    "menu:my_orders",
    "menu:security",
})

# Ordered list of (callback_data, label) for the menu rows
_MENU_ROWS: list[tuple[str, str]] = [
    ("menu:premium",    "⭐ تلگرام پرمیوم"),
    ("menu:stars",      "🎁 گیفت تلگرام / استارز"),
    ("menu:virtual",    "📱 شماره مجازی"),
    ("menu:ai_accounts","🤖 اکانت هوش مصنوعی"),
    ("menu:design",     "🎨 خدمات طراحی"),
    ("menu:security",   "🛡 امنیت صفحه"),
    ("menu:market_rates","📊 قیمت لحظه‌ای ارزها"),
    ("menu:my_orders",  "📋 پیگیری سفارشات"),
]


async def main_menu_kb() -> InlineKeyboardMarkup:
    """Build the main shop menu with live DB prices on each category.

    For each category that has products in ``product_prices``, the
    button shows the lowest starting price:

        ⭐ تلگرام پرمیوم  — از $5.99
        🤖 اکانت هوش مصنوعی  — از $14.99

    Categories without products (market rates, orders, security)
    are shown without a price suffix.

    Returns a cached ``InlineKeyboardMarkup`` ready for the handler.
    """
    from database.db import get_all_product_prices

    # Fetch live prices from DB once
    price_rows = await get_all_product_prices()

    # Build a lookup: product_key → usd_price
    price_map: dict[str, float] = {
        row["product_key"]: float(row["usd_price"])
        for row in price_rows
    }

    builder = InlineKeyboardBuilder()

    for cb_data, label in _MENU_ROWS:
        product_keys = _CATEGORY_PRODUCT_KEYS.get(cb_data)

        if cb_data in _NO_PRICE_CATEGORIES or not product_keys:
            # No price to show — plain label
            builder.button(text=label, callback_data=cb_data)
            continue

        # Pick the lowest-priced product in this category as the starting price
        prices = [
            price_map[k]
            for k in product_keys
            if k in price_map
        ]

        if prices:
            min_price = min(prices)
            text = f"{label}  — از ${min_price:.2f}"
        else:
            text = label

        builder.button(text=text, callback_data=cb_data)

    builder.adjust(1)
    return builder.as_markup()


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
