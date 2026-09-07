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
# (No longer used for price display — main_menu_kb shows plain labels)



# Ordered list of (callback_data, label) for the menu rows (no price suffix)
_MENU_ROWS: list[tuple[str, str]] = [
    ("menu:premium",     "⭐ تلگرام پرمیوم"),
    ("menu:stars",       "🌟 خرید استارز"),
    ("menu:stars_gift",  "🎁 گیفت‌های استارز"),
    ("menu:ai_accounts", "🤖 اکانت هوش مصنوعی"),
    ("menu:design",      "🎨 خدمات طراحی"),
    ("menu:security",    "🛡 امنیت صفحه"),
    ("menu:market_rates","📊 قیمت لحظه‌ای ارزها"),
    ("menu:my_orders",   "📋 پیگیری سفارشات"),
]


async def main_menu_kb() -> InlineKeyboardMarkup:
    """Build the main shop menu — plain category labels, no price suffix."""
    builder = InlineKeyboardBuilder()
    for cb_data, label in _MENU_ROWS:
        builder.button(text=label, callback_data=cb_data)
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


# ─── Telegram Stars (Standard) ─────────────────────────────────────

def stars_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 برای خودم", callback_data="stars:target:self")],
        [InlineKeyboardButton(text="👥 برای شخص دیگر", callback_data="stars:target:other")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="stars:back")],
    ])


# ─── Telegram Stars Gifts (individual items, 2-column layout) ───────

# Each gift: (emoji, stars_count, product_key)
_STARS_GIFTS = [
    ("💖", 15,  "stars_gift_heart_15"),
    ("🧸", 50,  "stars_gift_bear_50"),
    ("🎁", 25,  "stars_gift_present_25"),
    ("📱", 25,  "stars_gift_phone_25"),
    ("🎂", 50,  "stars_gift_cake_50"),
    ("🌷", 50,  "stars_gift_flower_50"),
    ("🍾", 50,  "stars_gift_champagne_50"),
    ("🚀", 50,  "stars_gift_rocket_50"),
    ("💝", 100, "stars_gift_ribbon_100"),
    ("💍", 100, "stars_gift_ring_100"),
]
# Special diamond gift (full-width button at bottom)
_DIAMOND_GIFT = ("💎", 100, "stars_gift_diamond_100")


async def stars_gift_items_kb() -> InlineKeyboardMarkup:
    """Build the 2-column Stars Gifts keyboard with dynamic DB prices."""
    from database.db import get_all_product_prices
    from utils.pricing import price_display

    price_rows = await get_all_product_prices()
    price_map = {row["product_key"]: float(row["usd_price"]) for row in price_rows}
    builder = InlineKeyboardBuilder()

    # Build 2-column rows for the standard gifts
    for i in range(0, len(_STARS_GIFTS), 2):
        row_buttons = []
        for j in range(2):
            if i + j >= len(_STARS_GIFTS):
                break
            emoji, stars_count, pkey = _STARS_GIFTS[i + j]
            usd = price_map.get(pkey, 0.0)
            toman_str = await price_display(usd)
            # Extract numeric toman value (e.g. "۵۹,۰۰۰ تومان" → "۵۹,۰۰۰")
            toman_num = toman_str.replace(" تومان", "")
            row_buttons.append(InlineKeyboardButton(
                text=f"{emoji} {toman_num} تومان - ⭐️ {stars_count}",
                callback_data=f"stars_gift:item:{pkey}"
            ))
        builder.row(*row_buttons)

    # Diamond gift — full-width button
    d_emoji, d_stars, d_pkey = _DIAMOND_GIFT
    d_usd = price_map.get(d_pkey, 0.0)
    d_toman_str = await price_display(d_usd)
    d_toman_num = d_toman_str.replace(" تومان", "")
    builder.row(InlineKeyboardButton(
        text=f"{d_emoji} گیفت الماس ({d_toman_num} تومان) - ⭐️ {d_stars}",
        callback_data=f"stars_gift:item:{d_pkey}"
    ))

    # Back button
    builder.row(InlineKeyboardButton(text="🔙 برگشت ↩️", callback_data="menu:back"))

    return builder.as_markup()



# ─── AI Accounts ────────────────────────────────────────────────────

def ai_platform_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ChatGPT Plus", callback_data="ai:platform:chatgpt")],
        [InlineKeyboardButton(text="✨ Gemini Advanced", callback_data="ai:platform:gemini")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")],
    ])


# ─── Design Services (Category → Tier) ────────────────────────────

def design_category_kb() -> InlineKeyboardMarkup:
    """Show the 3 design sub-categories: Video, Photo, Logo."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 ویدیو", callback_data="design:cat:video")],
        [InlineKeyboardButton(text="🖼 عکس", callback_data="design:cat:photo")],
        [InlineKeyboardButton(text="✏️ لوگو", callback_data="design:cat:logo")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")],
    ])


def design_tier_kb(category: str = "video") -> InlineKeyboardMarkup:
    """Show 4 quality tiers for a given design category."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 با هوش مصنوعی", callback_data=f"design:tier:{category}:ai")],
        [InlineKeyboardButton(text="📝 ساده", callback_data=f"design:tier:{category}:simple")],
        [InlineKeyboardButton(text="⭐ حرفه‌ای", callback_data=f"design:tier:{category}:pro")],
        [InlineKeyboardButton(text="💎 ویژه", callback_data=f"design:tier:{category}:special")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="design:back_to_categories")],
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
