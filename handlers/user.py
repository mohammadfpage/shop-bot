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
from keyboards.inline import main_menu_kb, back_to_menu_kb, market_rates_refresh_kb
from keyboards.reply import main_reply_kb
from keyboards.admin_reply import admin_reply_kb
from filters import IsAdmin

router = Router(name="user")


# ─── /start ──────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Register the user and show the main reply keyboard + inline menu.

    For admins, appends a special hint and shows the admin reply keyboard
    with the "⚙️ ورود به پنل مدیریت" button.
    """
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    is_admin = await IsAdmin()(message)

    text = (
        f"👋 <b>سلام {message.from_user.first_name} عزیز!</b>\n\n"
        "به فروشگاه تلگرام خوش آمدید.\n"
        "از منوی زیر خدمات مورد نظر خود را انتخاب کنید:"
    )

    if is_admin:
        text += (
            "\n\n👑 <b>شما به عنوان مدیر شناخته شدید.</b>\n"
            "برای ورود به پنل مدیریت دستور /admin را ارسال کنید "
            "یا از دکمه زیر استفاده کنید."
        )
        await message.answer(text, reply_markup=admin_reply_kb())
    else:
        await message.answer(text, reply_markup=main_reply_kb())


# ─── Reply keyboard: 🛒 محصولات / خرید ──────────────────────────────

@router.message(F.text == "🛒 محصولات / خرید")
async def reply_btn_shop(message: Message) -> None:
    """Show the inline shop menu when the user taps the shop button."""
    await message.answer(
        "🏠 <b>منوی خرید</b>\nیک سرویس را انتخاب کنید:",
        reply_markup=main_menu_kb(),
    )


# ─── Reply keyboard: 👤 پروفایل من ──────────────────────────────────

@router.message(F.text == "👤 پروفایل من")
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


# ─── Reply keyboard: 📚 راهنما ──────────────────────────────────────

@router.message(F.text == "📚 راهنما")
async def reply_btn_help(message: Message) -> None:
    """Show help text (admin-aware)."""
    is_admin = await IsAdmin()(message)

    text = (
        "📚 <b>راهنمای ربات</b>\n\n"
        "🔹 <b>🛒 محصولات / خرید</b> — مشاهده و خرید خدمات\n"
        "🔹 <b>👤 پروفایل من</b> — اطلاعات حساب شما\n"
        "🔹 <b>💵 قیمت روز ارز</b> — مشاهده نرخ لحظه‌ای ارزها\n"
        "🔹 <b>🎧 پشتیبانی (تیکت)</b> — ارسال پیام به پشتیبانی\n"
        "🔹 <b>📚 راهنما</b> — نمایش این متن\n\n"
        "💡 برای شروع خرید، روی «🛒 محصولات / خرید» کلیک کنید.\n"
        "💡 برای ارتباط با پشتیبانی، روی «🎧 پشتیبانی (تیکت)» کلیک کنید."
    )

    if is_admin:
        text += (
            "\n\n👑 <b>پنل مدیریت:</b>\n"
            "🔹 <b>⚙️ ورود به پنل مدیریت</b> — داشبورد مدیریتی\n"
            "🔹 دستور <code>/admin</code> — ورود سریع به پنل مدیریت\n"
            "🔹 دستور <code>/stats</code> — آمار سریع ربات\n"
            "🔹 دستور <code>/users</code> — لیست کاربران"
        )
        await message.answer(text, reply_markup=admin_reply_kb())
    else:
        await message.answer(text, reply_markup=main_reply_kb())


# ─── Back to menu ────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:back")
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🏠 <b>منوی اصلی</b>\nیک سرویس را انتخاب کنید:",
            reply_markup=main_menu_kb(),
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


@router.callback_query(F.data == "menu:virtual")
async def cb_menu_virtual(callback: CallbackQuery) -> None:
    from keyboards.inline import virtual_country_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "📱 <b>شماره مجازی</b>\nیک کشور را انتخاب کنید:",
            reply_markup=virtual_country_kb(),
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
    from keyboards.inline import design_tier_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🎨 <b>خدمات طراحی</b>\nیک سطح خدمات را انتخاب کنید:",
            reply_markup=design_tier_kb(),
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
