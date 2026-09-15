"""
Inline keyboards for the user-facing side of the bot.
All labels in Persian (فارسی).
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.callback_data import WelcomeCallback
from utils.emojis import get_pe, get_premium_id

# ─── Welcome Inline Keyboard ─────────────────────────────────────────

def welcome_inline_kb() -> InlineKeyboardMarkup:
    """Inline keyboard attached directly under the /start welcome text.

    Provides quick actions so the user doesn't have to scroll
    through the reply keyboard to get started.
    Layout: 2-column grid with last button full-width if odd count.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="مشاهده دسته‌بندی‌ها",
        callback_data=WelcomeCallback(action="categories").pack(),
        style="primary",
        icon_custom_emoji_id=get_premium_id("store"),
    )
    builder.button(
        text="تخفیف‌های ویژه",
        callback_data=WelcomeCallback(action="deals").pack(),
        style="primary",
        icon_custom_emoji_id=get_premium_id("fire"),
    )
    builder.button(
        text="پیگیری سفارشات",
        callback_data="menu:my_orders",
        style="primary",
        icon_custom_emoji_id=get_premium_id("box"),
    )
    builder.adjust(2)  # 2-column layout; last button full-width if odd
    return builder.as_markup()


# ─── Dynamic Main Menu (shop menu with live DB prices) ────────────────

# Map each menu callback_data to the product_keys that belong to it.
# The lowest-priced product in the group is used as the "starting at" price.
# (No longer used for price display — main_menu_kb shows plain labels)



# Ordered list of (callback_data, label, emoji_key) for the menu rows
_MENU_ROWS: list[tuple[str, str, str]] = [
    ("menu:virtual_number", "شماره مجازی", "key_lock"),
    ("menu:premium",     "تلگرام پرمیوم", "purse"),
    ("menu:stars",       "خرید استارز",  "star"),
    ("menu:stars_gift",  "گیفت‌های استارز", "heart_simple"),
    ("menu:ai_accounts", "اکانت هوش مصنوعی","bot"),
    ("menu:design",      "خدمات طراحی",     "gear"),
    ("menu:security",    "امنیت صفحه",      "shield"),
    ("menu:market_rates","قیمت لحظه‌ای ارزها","chart"),
    ("menu:my_orders",   "پیگیری سفارشات",  "box"),
]


async def main_menu_kb() -> InlineKeyboardMarkup:
    """Build the main shop menu in 2-column layout.

    Button texts show only the category name (no prices) with a Premium
    custom emoji rendered as the button icon.
    """
    builder = InlineKeyboardBuilder()
    for cb_data, label, emoji_key in _MENU_ROWS:
        builder.button(
            text=label,
            callback_data=cb_data,
            style="primary",
            icon_custom_emoji_id=get_premium_id(emoji_key),
        )
    builder.adjust(2)  # 2-column layout
    # Last button (my_orders) stays full-width if odd count
    return builder.as_markup()


# ─── Telegram Premium ────────────────────────────────────────────────

async def premium_duration_kb() -> InlineKeyboardMarkup:
    """Build premium duration buttons with dynamic DB prices.
    
    Each button takes full width (1 per row) to prevent text truncation.
    """
    from database.db import get_price_or_default
    from utils.pricing import price_display

    durations = [
        ("premium:monthly",    "ماهانه",    "telegram_premium_monthly",  "calendar"),
        ("premium:quarterly",  "سه‌ماهه",   "telegram_premium_quarterly", "calendar"),
        ("premium:semi_annual", "شش‌ماهه",  "telegram_premium_semi_annual", "calendar"),
        ("premium:yearly",     "سالانه",    "telegram_premium_yearly",  "calendar"),
    ]

    builder = InlineKeyboardBuilder()
    for cb_data, base_label, product_key, emoji_key in durations:
        usd = await get_price_or_default(product_key)
        toman_str = await price_display(usd)
        toman_num = toman_str.replace(" تومان", "")
        builder.button(
            text=f"{base_label} — {toman_num} تومان",
            callback_data=cb_data,
            style="primary",
            icon_custom_emoji_id=get_premium_id(emoji_key),
        )
    builder.adjust(1)  # 1 button per row to show full text
    builder.row(InlineKeyboardButton(
        text="بازگشت",
        callback_data="menu:back",
        style="primary",
        icon_custom_emoji_id=get_premium_id("down"),
    ))
    return builder.as_markup()


def premium_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="برای خودم",
                              callback_data="premium:target:self",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("user"))],
        [InlineKeyboardButton(text="برای شخص دیگر",
                              callback_data="premium:target:other",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("users"))],
        [InlineKeyboardButton(text="بازگشت",
                              callback_data="premium:back",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("down"))],
    ])


# ─── Telegram Stars (Standard) ─────────────────────────────────────

def stars_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="برای خودم",
                              callback_data="stars:target:self",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("user"))],
        [InlineKeyboardButton(text="برای شخص دیگر",
                              callback_data="stars:target:other",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("users"))],
        [InlineKeyboardButton(text="بازگشت",
                              callback_data="stars:back",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("down"))],
    ])


# ─── Telegram Stars Gifts (individual items, 2-column layout) ───────

# Each gift: (emoji_key_for_button_icon, stars_count, product_key, display_name, static_price_toman)
# display_name uses plain unicode emojis — Telegram does NOT render custom
# <tg-emoji> tags inside buttons.
# Only include products that exist in config.PRICES / product_prices DB.
_STARS_GIFTS = [
    ("heart_simple", 15,  "stars_gift_heart_15",   "❤️ قلب",      92000),
    ("star",         15,  "stars_gift_teddy_15",   "🧸 تدی",      92000),
    ("gift",         25,  "stars_gift_gift_25",    "🎁 کادو",     138000),
    ("heart_simple", 25,  "stars_gift_rose_25",    "🌹 گل رز",    138000),
    ("sparkles",     50,  "stars_gift_cake_50",    "🎂 کیک",      290000),
    ("heart_simple", 50,  "stars_gift_flower_50",  "💐 گل",       290000),
    ("sparkles",     50,  "stars_gift_bottle_50",  "🍾 بطری",     290000),
    ("rocket",       50,  "stars_gift_rocket_50",  "🚀 سفینه",    290000),
    ("star",         100, "stars_gift_trophy_100", "🏆 جام",      470000),
    ("sparkles",     100, "stars_gift_ring_100",   "💍 حلقه",     470000),
    ("diamond",      100, "stars_gift_diamond_100","💎 الماس",    470000),
]


async def stars_gift_items_kb() -> InlineKeyboardMarkup:
    """Build the Stars Gifts keyboard with dynamic DB prices.

    Each gift button takes full width (1 per row) to show full text.
    Format: [Emoji] [Name] [Stars] ⭐️ - [Price] تومان
    """
    from database.db import get_all_product_prices
    from utils.pricing import price_display

    price_rows = await get_all_product_prices()
    price_map = {row["product_key"]: float(row["usd_price"]) for row in price_rows}
    builder = InlineKeyboardBuilder()

    # Build 1-column rows for all official gifts (full width each)
    for emoji_key, stars_count, pkey, display_name, static_price in _STARS_GIFTS:
        toman_num = f"{static_price:,}".replace(",", "،")
        builder.button(
            text=f"{display_name} {stars_count} ⭐️ - {toman_num} تومان",
            callback_data=f"stars_gift:item:{pkey}",
            style="primary",
            icon_custom_emoji_id=get_premium_id(emoji_key),
        )

    builder.adjust(1)  # 1 button per row to show full text

    # Back button
    builder.row(InlineKeyboardButton(
        text="برگشت ↩️",
        callback_data="menu:back",
        style="primary",
        icon_custom_emoji_id=get_premium_id("down"),
    ))

    return builder.as_markup()



# ─── AI Accounts ────────────────────────────────────────────────────

async def ai_platform_kb() -> InlineKeyboardMarkup:
    """Build AI platform buttons with dynamic DB prices.
    
    Each button takes full width (1 per row) to prevent text truncation.
    """
    from database.db import get_price_or_default
    from utils.pricing import price_display

    platforms = [
        ("ai:platform:chatgpt", "ChatGPT Plus", "chatgpt_premium", "bot"),
        ("ai:platform:gemini",  "Gemini Advanced", "gemini_premium", "sparkles"),
    ]

    builder = InlineKeyboardBuilder()
    for cb_data, base_label, product_key, emoji_key in platforms:
        usd = await get_price_or_default(product_key)
        toman_str = await price_display(usd)
        toman_num = toman_str.replace(" تومان", "")
        builder.button(
            text=f"{base_label} — {toman_num} تومان",
            callback_data=cb_data,
            style="primary",
            icon_custom_emoji_id=get_premium_id(emoji_key),
        )
    builder.adjust(1)  # 1 button per row to show full text
    builder.row(InlineKeyboardButton(
        text="بازگشت",
        callback_data="menu:back",
        style="primary",
        icon_custom_emoji_id=get_premium_id("down"),
    ))
    return builder.as_markup()


# ─── Design Services (Category → Tier) ────────────────────────────

async def design_category_kb() -> InlineKeyboardMarkup:
    """Show the 3 design sub-categories: Video, Photo, Logo.
    
    Each button takes full width (1 per row) to prevent text truncation.
    """
    from database.db import get_price_or_default
    from utils.pricing import price_display

    # Get cheapest price per category for display
    categories = [
        ("design:cat:video", "🎬 ویدیو", "design_video_ai", "film"),
        ("design:cat:photo", "📸 عکس",  "design_photo_ai", "camera"),
        ("design:cat:logo",  "🎨 لوگو",  "design_logo_ai", "palette"),
    ]

    builder = InlineKeyboardBuilder()
    for cb_data, base_label, product_key, emoji_key in categories:
        usd = await get_price_or_default(product_key)
        toman_str = await price_display(usd)
        toman_num = toman_str.replace(" تومان", "")
        builder.button(
            text=f"{base_label} — از {toman_num}",
            callback_data=cb_data,
            style="primary",
            icon_custom_emoji_id=get_premium_id(emoji_key),
        )
    builder.adjust(1)  # 1 button per row to show full text
    builder.row(InlineKeyboardButton(
        text="بازگشت",
        callback_data="menu:back",
        style="primary",
        icon_custom_emoji_id=get_premium_id("down"),
    ))
    return builder.as_markup()


async def design_tier_kb(category: str = "video") -> InlineKeyboardMarkup:
    """Show 4 quality tiers for a given design category with dynamic prices.
    
    Each button takes full width (1 per row) to prevent text truncation.
    """
    from database.db import get_price_or_default
    from utils.pricing import price_display

    tiers = [
        (f"design:tier:{category}:ai",      "با هوش مصنوعی", f"design_{category}_ai",      "bot"),
        (f"design:tier:{category}:simple",  "ساده",           f"design_{category}_simple",  "neutral"),
        (f"design:tier:{category}:pro",     "حرفه‌ای",        f"design_{category}_pro",     "star"),
        (f"design:tier:{category}:special", "ویژه",           f"design_{category}_special", "diamond"),
    ]

    builder = InlineKeyboardBuilder()
    for cb_data, base_label, product_key, emoji_key in tiers:
        usd = await get_price_or_default(product_key)
        toman_str = await price_display(usd)
        toman_num = toman_str.replace(" تومان", "")
        builder.button(
            text=f"{base_label} — {toman_num} تومان",
            callback_data=cb_data,
            style="primary",
            icon_custom_emoji_id=get_premium_id(emoji_key),
        )
    builder.adjust(1)  # 1 button per row to show full text
    builder.row(InlineKeyboardButton(
        text="بازگشت",
        callback_data="design:back_to_categories",
        style="primary",
        icon_custom_emoji_id=get_premium_id("down"),
    ))
    return builder.as_markup()


# ─── Page Security ──────────────────────────────────────────────────

async def security_tariff_kb() -> InlineKeyboardMarkup:
    """Show security tariffs with dynamic prices from config.
    
    Each button takes full width (1 per row) to prevent text truncation.
    """
    from utils.pricing import price_display
    from config import config

    tariffs = [
        ("security:tariff:basic",     "پایه",      "basic",     "user"),
        ("security:tariff:standard",  "استاندارد", "standard",  "users"),
        ("security:tariff:advanced",  "پیشرفته",   "advanced",  "shield"),
    ]

    builder = InlineKeyboardBuilder()
    for cb_data, base_label, tariff_key, emoji_key in tariffs:
        tariff = config.SECURITY_TARIFFS.get(tariff_key, {})
        usd = tariff.get("usd", 0)
        toman_str = await price_display(usd)
        toman_num = toman_str.replace(" تومان", "")
        builder.button(
            text=f"{base_label} — {toman_num} تومان",
            callback_data=cb_data,
            style="primary",
            icon_custom_emoji_id=get_premium_id(emoji_key),
        )
    builder.adjust(1)  # 1 button per row to show full text
    builder.row(InlineKeyboardButton(
        text="بازگشت",
        callback_data="menu:back",
        style="primary",
        icon_custom_emoji_id=get_premium_id("down"),
    ))
    return builder.as_markup()


# ─── Market Rates ───────────────────────────────────────────────────

def market_rates_refresh_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="به‌روزرسانی",
                              callback_data="menu:market_rates",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("exchange"))],
        [InlineKeyboardButton(text="بازگشت به منو",
                              callback_data="menu:back",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("down"))],
    ])


# ─── Generic payment ────────────────────────────────────────────────

def payment_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="پرداخت",
                              callback_data="pay:confirm",
                              style="success",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="انصراف",
                              callback_data="pay:cancel",
                              style="danger",
                              icon_custom_emoji_id=get_premium_id("cross"))],
    ])


def pay_link_kb(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="پرداخت از طریق زرین‌پال",
                              url=pay_url,
                              style="success",
                              icon_custom_emoji_id=get_premium_id("card"))],
        [InlineKeyboardButton(text="پرداخت کردم",
                              callback_data="pay:check",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("check"))],
        [InlineKeyboardButton(text="انصراف",
                              callback_data="pay:cancel",
                              style="danger",
                              icon_custom_emoji_id=get_premium_id("cross"))],
    ])


# ─── Virtual Number (New API — "شماره مجازی") ──────────────────────

def virtual_services_kb(apps_data: dict | None = None) -> InlineKeyboardMarkup:
    """Build the application-selection grid dynamically from the Ozvinoo API.

    ``apps_data`` is the raw dict returned by ``get_applications_list()``,
    keyed by code (e.g. {"tg": {"id": 1, ...}, "wa": {"id": 2, ...}}).

    Layout:
      Row 0:  Telegram dedicated (full width)
      Grid:   3 columns for all other apps
      Footer: Back button
    """
    if apps_data is None:
        apps_data = {}

    builder = InlineKeyboardBuilder()

    # Persian labels for known API codes (fallback to code/title if unknown)
    app_map = {
        "tg": "تلگرام - پنل اختصاصی 💎", "wa": "واتساپ ✳️",
        "ig": "اینستاگرام 🚀", "change": "چنج نامبر 🗳",
        "google": "گوگل 🔍", "fb": "فیسبوک 📬",
        "imo": "ایمو 📶", "tiktok": "تیک تاک ⌚",
        "x": "ایکس ❎", "wechat": "وی چت 💬",
        "tinder": "تیندر 🔥", "likee": "لایکی 💖",
        "yahoo": "یاهو 🌀", "netflix": "نتفلیکس 💢",
        "paypal": "پیپال 🧾", "steam": "استیم 🎮",
        "microsoft": "مایکروسافت 💻", "line": "لاین 🧩",
        "uber": "اوبر 🚕", "alibaba": "علی بابا ☂️",
        "amazon": "آمازون 🐝", "discord": "دیسکورد 🚹",
        "apple": "اپل 🍎", "ebay": "ای بای 🛒",
    }

    app_list = list(apps_data.values()) if isinstance(apps_data, dict) else []
    tg_id = "1"  # fallback
    other_buttons = []

    for app in app_list:
        code = str(app.get("code", "")).lower()
        app_id = str(app.get("id", ""))
        # Identify Telegram (code == 'tg' or title contains 'telegram')
        if code == "tg" or "telegram" in str(app.get("title", "")).lower():
            tg_id = app_id
            continue
        btn_text = app_map.get(code, app.get("title", code))
        other_buttons.append(
            InlineKeyboardButton(text=btn_text, callback_data=f"v_app:{app_id}")
        )

    # Top Row: Full width Telegram
    builder.row(
        InlineKeyboardButton(text="تلگرام - پنل اختصاصی 💎", callback_data=f"v_app:{tg_id}")
    )

    # Grid: 3 columns for everything else
    for i in range(0, len(other_buttons), 3):
        builder.row(*other_buttons[i:i + 3])

    builder.row(InlineKeyboardButton(
        text="🔙 بازگشت به منو",
        callback_data="menu:back_main",
    ))
    return builder.as_markup()


def virtual_country_kb(countries: list, service_id, page: int = 0) -> InlineKeyboardMarkup:
    """Build a paginated, table-style keyboard for virtual number purchase.

    Layout (exactly 10 countries per page):
      Toggle:    [🚀 شماره غیرریپورت] or [💎 پنل اختصاصی]  ← Telegram only
      Controls:  [🔍 فیلتر پیشرفته] [🔄 خرید گروهی]
      Header:    [💰 قیمت] [📊 وضعیت] [🌍 نام کشور]
      Data rows: [price] [✅ موجود | ❌ ناموجود] [country]  (range-based callback)
      Pagination:[⬅️ قبلی] [بعدی ➡️]
      Footer:    [🔙 سرویس‌ها] → back to application list
    """
    builder = InlineKeyboardBuilder()

    # 1. Non-report toggle (Telegram only)
    sid_str = str(service_id)
    if sid_str == "1":
        builder.row(
            InlineKeyboardButton(text="🚀 شماره غیرریپورت", callback_data="v_app:tg_noreport")
        )
    elif sid_str == "tg_noreport":
        builder.row(
            InlineKeyboardButton(text="💎 تلگرام - پنل اختصاصی", callback_data="v_app:1")
        )

    # 2. Filter / Bulk controls
    builder.row(
        InlineKeyboardButton(text="🔍 فیلتر پیشرفته", callback_data=f"v_filter:{service_id}"),
        InlineKeyboardButton(text="🔄 خرید گروهی", callback_data=f"v_bulk:{service_id}"),
    )

    # 3. Header row
    builder.row(
        InlineKeyboardButton(text="💰 قیمت", callback_data="ignore"),
        InlineKeyboardButton(text="📊 وضعیت", callback_data="ignore"),
        InlineKeyboardButton(text="🌍 نام کشور", callback_data="ignore"),
    )

    # 4. Data rows (10 per page)
    items_per_page = 10
    start = page * items_per_page
    end = start + items_per_page

    for c in countries[start:end]:
        status_text = "✅ موجود" if c["in_stock"] else "❌ ناموجود"
        country_range = c.get("range", "1")
        cb_data = f"v_buy:{service_id}:{country_range}" if c["in_stock"] else "ignore"

        price = c.get("final_price", c.get("price", 0))
        country_name = c["country"][:15]

        builder.row(
            InlineKeyboardButton(text=f"{price:,}", callback_data=cb_data),
            InlineKeyboardButton(text=status_text, callback_data=cb_data),
            InlineKeyboardButton(text=country_name, callback_data=cb_data),
        )

    # 5. Pagination navigation
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"v_page:{service_id}:{page - 1}"))
    if end < len(countries):
        nav.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"v_page:{service_id}:{page + 1}"))
    if nav:
        builder.row(*nav)

    # 6. Footer — back to application list
    builder.row(InlineKeyboardButton(
        text="🔙 سرویس‌ها",
        callback_data="menu:virtual_number",
        style="primary",
        icon_custom_emoji_id=get_premium_id("down"),
    ))

    return builder.as_markup()


# ─── Back to menu ───────────────────────────────────────────────────

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="بازگشت به منو",
                              callback_data="menu:back",
                              style="primary",
                              icon_custom_emoji_id=get_premium_id("down"))],
    ])
