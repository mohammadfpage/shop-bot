"""
Handler: /start, main menu, profile, help, market rates, and order history.
All user-facing text in Persian (فارسی).
"""

import contextlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest

from database.db import get_or_create_user, get_user_orders, get_total_users
from keyboards.inline import (
    main_menu_kb,
    back_to_menu_kb,
    market_rates_refresh_kb,
    welcome_inline_kb,
)
from keyboards.reply import main_reply_kb
from keyboards.admin_reply import admin_reply_kb
from keyboards.callback_data import WelcomeCallback
from filters import IsAdmin

router = Router(name="user")


# ─── /start ──────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Register the user and show the Ultimate Welcome Experience.

    Sends a beautifully formatted Persian welcome message with:
      • A persistent ReplyKeyboardMarkup at the bottom (navigation)
      • An InlineKeyboardMarkup directly under the welcome text (quick actions)

    For admins, appends a special admin hint.
    """
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    is_admin = await IsAdmin()(message)

    text = (
        f"👋 <b>سلام {message.from_user.first_name} عزیز!</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 <b>فروشگاه هوشمند تلگرام</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🌟 <b>چرا ما؟</b>\n"
        "✅ تحویل <b>خودکار و آنی</b> پس از پرداخت\n"
        "🕐 پشتیبانی <b>۲۴ ساعته</b> در ۷ روز هفته\n"
        "💳 پرداخت <b>امن</b> از طریق زرین‌پال\n"
        "💰 قیمت‌های <b>رقابتی</b> با نرخ لحظه‌ای ارز\n"
        "🔒 <b>گارانتی</b> کیفیت تمامی خدمات\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>خدمات ما:</b>\n"
        "⭐ تلگرام پرمیوم (ماهانه تا سالانه)\n"
        "🎁 گیفت و استارز تلگرام\n"
        "🤖 اکانت پرمیوم هوش مصنوعی\n"
        "🎨 خدمات طراحی حرفه‌ای\n"
        "🛡 امنیت صفحه و اکانت\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    if is_admin:
        text += (
            "\n👑 <b>شما به عنوان مدیر شناخته شدید.</b>\n"
            "برای ورود به پنل مدیریت دستور /admin را ارسال کنید."
        )
        # Admins get: welcome text + inline quick actions + admin reply keyboard
        await message.answer(text, reply_markup=welcome_inline_kb())
        await message.answer(
            "⚙️ <b>پنل مدیریت</b>\nاز دکمه زیر استفاده کنید:",
            reply_markup=admin_reply_kb(),
        )
    else:
        # Regular users get: welcome text + inline quick actions + user reply keyboard
        await message.answer(text, reply_markup=welcome_inline_kb())
        await message.answer(
            "👇 از منوی زیر استفاده کنید:",
            reply_markup=main_reply_kb(),
        )


# ─── WelcomeCallback handlers (inline buttons under welcome text) ────

@router.callback_query(WelcomeCallback.filter(F.action == "categories"))
async def cb_welcome_categories(callback: CallbackQuery) -> None:
    """Show the main shop menu with all product categories."""
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🏠 <b>دسته‌بندی خدمات</b>\nیک سرویس را انتخاب کنید:",
            reply_markup=await main_menu_kb(),
        )
    await callback.answer()


@router.callback_query(WelcomeCallback.filter(F.action == "deals"))
async def cb_welcome_deals(callback: CallbackQuery) -> None:
    """Show special offers / discounts."""
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🔥 <b>تخفیف‌های ویژه</b>\n\n"
            "🎯 <b>پکیج پرمیوم تلگرام + استارز</b>\n"
            "   خرید اشتراک سالانه + ۵۰۰ استارز با ۱۵٪ تخفیف\n\n"
            "🎯 <b>اکانت هوش مصنوعی</b>\n"
            "   خرید همزمان ChatGPT + Gemini با ۱۰٪ تخفیف\n\n"
            "💡 برای بهره‌مندی از تخفیف‌ها، محصول مورد نظر را "
            "از منوی خرید انتخاب کنید.\n\n"
            "⏰ تخفیف‌ها محدود هستند!",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── Reply keyboard: 🛍 فروشگاه ────────────────────────────────────

@router.message(F.text == "🛍 فروشگاه")
async def reply_btn_shop(message: Message) -> None:
    """Show the inline shop menu when the user taps the shop button."""
    await message.answer(
        "🏠 <b>منوی خرید</b>\nیک سرویس را انتخاب کنید:",
        reply_markup=await main_menu_kb(),
    )


# ─── Reply keyboard: 👤 پروفایل ────────────────────────────────────

@router.message(F.text == "👤 پروفایل")
async def reply_btn_profile(message: Message) -> None:
    """Show the user's profile information."""
    user = await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    username_display = f"@{user['username']}" if user["username"] else "—"
    admin_badg = " | 🛡 مدیر" if user["is_admin"] else ""

    text = (
        f"👤 <b>پروفایل من</b>\n\n"
        f"🆔 شناسه: <code>{user['user_id']}</code>\n"
        f"📛 نام: {user['full_name']}\n"
        f"👤 یوزرنیم: {username_display}{admin_badg}\n"
        f"📅 تاریخ عضویت: {user['joined_at'][:10] if user['joined_at'] else '—'}"
    )
    await message.answer(text, reply_markup=main_reply_kb())


# ─── Reply keyboard: 🎧 پشتیبانی ───────────────────────────────────

@router.message(F.text == "🎧 پشتیبانی")
async def reply_btn_support(message: Message) -> None:
    """Redirect to the ticket system."""
    # Import here to avoid circular imports
    from handlers.ticket import router as ticket_router
    # Trigger the ticket flow by sending the same message through the ticket handler
    # We just show a brief instruction since the ticket handler catches the text
    await message.answer(
        "🎧 <b>پشتیبانی</b>\n\n"
        "📌 برای ارسال تیکت پشتیبانی، پیام خود را ارسال کنید.\n"
        "پیام شما مستقیماً به تیم پشتیبانی ارسال خواهد شد.\n\n"
        "💡 اگر سؤالی دارید، پیام خود را بنویسید و ارسال کنید.",
        reply_markup=main_reply_kb(),
    )


# ─── Back to menu ────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:back")
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🏠 <b>منوی اصلی</b>\nیک سرویس را انتخاب کنید:",
            reply_markup=await main_menu_kb(),
        )
    await callback.answer()


# ─── Menu entry points ──────────────────────────────────────────────

@router.callback_query(F.data == "menu:premium")
async def cb_menu_premium(callback: CallbackQuery) -> None:
    from keyboards.inline import premium_duration_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "⭐ <b>تلگرام پرمیوم</b>\nیک پلن اشتراک را انتخاب کنید:",
            reply_markup=premium_duration_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:ai_accounts")
async def cb_menu_ai(callback: CallbackQuery) -> None:
    from keyboards.inline import ai_platform_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🤖 <b>اکانت هوش مصنوعی پرمیوم</b>\nیک پلتفرم را انتخاب کنید:",
            reply_markup=ai_platform_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:design")
async def cb_menu_design(callback: CallbackQuery) -> None:
    from keyboards.inline import design_category_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🎨 <b>خدمات طراحی</b>\nیک دسته را انتخاب کنید:",
            reply_markup=design_category_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:security")
async def cb_menu_security(callback: CallbackQuery) -> None:
    from keyboards.inline import security_tariff_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🛡 <b>امنیت صفحه</b>\nیک تعرفه را انتخاب کنید:",
            reply_markup=security_tariff_kb(),
        )
    await callback.answer()


# ─── Market Rates (Live Exchange Rates) ─────────────────────────────

@router.callback_query(F.data == "menu:market_rates")
async def cb_market_rates(callback: CallbackQuery) -> None:
    from utils.pricing import get_market_data

    data = await get_market_data()
    if not data:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "⚠️ دریافت اطلاعات بازار با مشکل مواجه شد.\nلطفاً دوباره تلاش کنید.",
                reply_markup=market_rates_refresh_kb(),
            )
        await callback.answer()
        return

    lines = ["📊 <b>قیمت لحظه‌ای ارزها و طلا</b>\n"]

    def build_lookup(category: str) -> dict[str, dict]:
        """Index one BrsApi root array by its exact symbol value."""
        return {
            item["symbol"]: item
            for item in data.get(category, [])
            if isinstance(item, dict) and item.get("symbol")
        }

    gold = build_lookup("gold")
    currency = build_lookup("currency")
    cryptocurrency = build_lookup("cryptocurrency")

    def as_number(value: object) -> float:
        """Convert API numbers, including numeric strings, to floats."""
        if value is None:
            return 0.0
        try:
            return float(str(value).replace(",", "").replace("،", "").strip())
        except (TypeError, ValueError):
            return 0.0

    def format_number(value: object) -> str:
        number = as_number(value)
        if number.is_integer():
            return f"{int(number):,}"
        return f"{number:,.8f}".rstrip("0").rstrip(".")

    def format_item(
        items: dict[str, dict],
        symbol: str,
        name: str,
        unit: str,
    ) -> str:
        item = items.get(symbol)
        if not item:
            return f"  {name}: ⚠️ موجود نیست"

        price = item.get("price")
        change = as_number(item.get("change_percent"))
        change_icon = "📈" if change >= 0 else "📉"
        return (
            f"  {name}: <b>{format_number(price)}</b> {unit} "
            f"{change_icon} {change:+.2f}%"
        )

    # ── Popular Currencies (prices are in Toman) ──
    lines.append("🔸 <b>ارزهای پرکاربرد:</b>")
    lines.append(format_item(currency, "USD", "🇺🇸 دلار آمریکا", "تومان"))
    lines.append(format_item(currency, "EUR", "🇪🇺 یورو", "تومان"))
    lines.append(format_item(currency, "USDT_IRT", "💰 تتر", "تومان"))
    lines.append("")

    # ── Gold & Coins (prices are in Toman) ──
    lines.append("🔸 <b>طلا و سکه:</b>")
    lines.append(format_item(gold, "IR_GOLD_18K", "🥇 طلای ۱۸ عیار", "تومان"))
    lines.append(format_item(gold, "IR_COIN_EMAMI", "🪙 سکه امامی", "تومان"))
    lines.append(format_item(gold, "IR_COIN_BAHAR", "🪙 سکه بهار آزادی", "تومان"))
    lines.append("")

    # ── Cryptocurrencies (prices are in USD) ──
    lines.append("🔸 <b>رمزارزهای اصلی:</b>")
    lines.append(format_item(cryptocurrency, "BTC", "₿ بیت‌کوین", "USD"))
    lines.append(format_item(cryptocurrency, "ETH", "⟠ اتریوم", "USD"))
    lines.append(format_item(cryptocurrency, "SOL", "◎ سولانا", "USD"))
    lines.append("")
    lines.append("⏰ نرخ‌ها لحظه‌ای هستند و هر ۵ دقیقه به‌روز می‌شوند.")

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=market_rates_refresh_kb(),
        )
    await callback.answer()


# ─── My Orders (پیگیری سفارشات) ─────────────────────────────────────

@router.callback_query(F.data == "menu:my_orders")
async def cb_my_orders(callback: CallbackQuery) -> None:
    orders = await get_user_orders(callback.from_user.id)
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "📋 <b>پیگیری سفارشات</b>\n\nشما هنوز سفارشی ثبت نکرده‌اید.",
                reply_markup=back_to_menu_kb(),
            )
    else:
        lines = ["📋 <b>پیگیری سفارشات</b>\n"]
        for o in orders[:10]:  # last 10
            lines.append(_format_order_line(o))
        lines.append("\nبرای اطلاعات بیشتر روی شماره سفارش کلیک کنید.")
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=back_to_menu_kb(),
            )
    await callback.answer()


def _format_order_line(o) -> str:
    """Format a single order line with detailed status."""
    status_map = {
        "pending":   ("🟡", "در انتظار پرداخت"),
        "paid":      ("🟢", "پرداخت شده / در صف انجام"),
        "delivered": ("✅", "انجام شده"),
        "cancelled": ("❌", "لغو شده"),
    }
    emoji, label = status_map.get(o["status"], ("❓", o["status"]))
    amount = f"{o['amount_irt']:,}".replace(",", "،") if o["amount_irt"] else "—"
    return f"{emoji} #{o['order_id']} | {o['product']} | {amount} تومان | {label}"


def _status_fa(status: str) -> str:
    """Convert order status to Persian."""
    return {
        "pending": "در انتظار",
        "paid": "پرداخت شده",
        "delivered": "تحویل شده",
        "cancelled": "لغو شده",
    }.get(status, status)
