"""
Handler: /start, main menu, profile, help, market rates, and order history.
All user-facing text in Persian (فارسی).
"""

import contextlib
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest

from database.db import get_or_create_user, get_user_orders, get_total_users, update_user_phone, user_has_phone, get_wallet_balance
from states.states import VirtualNumberStates
from keyboards.inline import (
    main_menu_kb,
    back_to_menu_kb,
    market_rates_refresh_kb,
    welcome_inline_kb,
)
from keyboards.reply import main_reply_kb, virtual_services_reply_kb
from keyboards.admin_reply import admin_reply_kb
from keyboards.callback_data import WelcomeCallback
from filters import IsAdmin, IsDynamicService
from utils.emojis import get_pe
from utils.shiznumber import get_panel_balance

router = Router(name="user")

logger = logging.getLogger(__name__)


# ─── Registration / Rules ───────────────────────────────────────────

RULES_TEXT = (
    "📌 <b>نکات لازم در هنگام خرید شماره مجازی:</b>\n\n"
    "1️⃣ شماره های ستاره دار داخل لیست نوریپ و نوبن هستند و شماره های دارای لایک از کددهی سریعتری برخوردارند.\n"
    "2️⃣ برای تلگرام از فیلترشکن رایگان استفاده نکنید و حتما از نسخه اصلی تلگرام استفاده کنید.\n"
    "3️⃣ برای واتساپ سعی کنید به ip کشوری وصل شوید که قصد استفاده از شماره مجازی آن کشور را دارید !\n"
    "4️⃣ حتما حتما لازم است که برنامه مورد نظر ، کد تایید ارسال کند . ممکن است متوجه نشوید که برای تایید شماره به شما تماس گرفته باشد ، پس حتما گزینه ارسال پیامک تایید را انتخاب کنید.\n"
    "5️⃣ هر شماره تا 15 دقیقه قابلیت استفاده دارد و در این مدت تا هر چند تا کد که لازم دارید را می‌توانید دریافت کنید.\n\n"
    "👇 جهت موافقت با قوانین و ورود به ربات، روی دکمه <b>«تایید قوانین و ارسال شماره»</b> کلیک کنید:"
)


def contact_request_kb() -> ReplyKeyboardMarkup:
    """Reply keyboard with a single request_contact button for onboarding."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 تایید قوانین و ارسال شماره", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─── /start ──────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Register the user and show the Ultimate Welcome Experience.

    If the user has NOT shared their phone number yet, show the rules
    and a request_contact button instead of the main menu.
    """
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    # ── Mandatory registration: check for phone number ──
    has_phone = await user_has_phone(message.from_user.id)
    if not has_phone:
        # New user or user who hasn't shared contact yet — show rules
        await message.answer(
            RULES_TEXT,
            reply_markup=contact_request_kb(),
        )
        return

    is_admin = await IsAdmin()(message)

    text = (
        f"{get_pe('wave')} <b>سلام {message.from_user.first_name} عزیز!</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{get_pe('bot')} <b>فروشگاه هوشمند تلگرام</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"{get_pe('sparkles')} <b>چرا ما؟</b>\n"
        f"{get_pe('check')} تحویل <b>خودکار و آنی</b> پس از پرداخت\n"
        f"{get_pe('call')} پشتیبانی <b>۲۴ ساعته</b> در ۷ روز هفته\n"
        f"{get_pe('card')} پرداخت <b>امن</b> از طریق زرین‌پال\n"
        f"{get_pe('money')} قیمت‌های <b>رقابتی</b> با نرخ لحظه‌ای ارز\n"
        f"{get_pe('lock')} <b>گارانتی</b> کیفیت تمامی خدمات\n\n"

        f"📱 ارائه دهنده خدمات <b>شماره مجازی</b> و خرید انواع <b>اکانت‌های پرمیوم</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{get_pe('box')} <b>خدمات ما:</b>\n"
        f"{get_pe('key_lock')} شماره مجازی\n"
        f"{get_pe('bot')} خرید انواع اکانت‌های پرمیوم\n"
        f"{get_pe('star')} تلگرام پرمیوم (ماهانه تا سالانه)\n"
        f"{get_pe('heart_simple')} گیفت و استارز تلگرام\n"
        f"{get_pe('fire')} خدمات طراحی حرفه‌ای\n"
        f"{get_pe('shield')} امنیت صفحه و اکانت\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    if is_admin:
        text += (
            f"\n{get_pe('medal')} <b>شما به عنوان مدیر شناخته شدید.</b>\n"
            "برای ورود به پنل مدیریت دستور /admin را ارسال کنید."
        )
        # Admins get: welcome text + inline quick actions + admin reply keyboard
        await message.answer(text, reply_markup=welcome_inline_kb())
        await message.answer(
            f"{get_pe('gear')} <b>پنل مدیریت</b>\nاز دکمه زیر استفاده کنید:",
            reply_markup=admin_reply_kb(),
        )
    else:
        # Regular users get: welcome text + inline quick actions + user reply keyboard
        await message.answer(text, reply_markup=welcome_inline_kb())
        await message.answer(
            f"{get_pe('down')} از منوی زیر استفاده کنید:",
            reply_markup=main_reply_kb(),
        )


# ─── Contact sharing (mandatory registration) ───────────────────────

@router.message(F.contact)
async def process_contact(message: Message) -> None:
    """Handle shared contact — verify it belongs to the sender, save, and welcome."""
    if message.contact.user_id != message.from_user.id:
        await message.answer(
            "⚠️ لطفاً شماره تماس <b>خودتان</b> را با استفاده از دکمه زیر ارسال کنید.",
            reply_markup=contact_request_kb(),
        )
        return

    phone_number = message.contact.phone_number
    try:
        await update_user_phone(message.from_user.id, phone_number)
    except Exception as exc:
        logger.error(
            "Failed to save phone for user %s: %s", message.from_user.id, exc,
        )

    await message.answer(
        f"✅ ثبت نام شما با موفقیت انجام شد و قوانین پذیرفته شد.\n"
        f"به فروشگاه خوش آمدید!",
        reply_markup=main_reply_kb(),
    )


# ─── WelcomeCallback handlers (inline buttons under welcome text) ────

@router.callback_query(WelcomeCallback.filter(F.action == "categories"))
async def cb_welcome_categories(callback: CallbackQuery) -> None:
    """Show the main shop menu with all product categories."""
    await callback.answer()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('home')} <b>دسته‌بندی خدمات</b>\nیک سرویس را انتخاب کنید:",
            reply_markup=await main_menu_kb(),
        )
    await callback.answer()


@router.callback_query(WelcomeCallback.filter(F.action == "deals"))
async def cb_welcome_deals(callback: CallbackQuery) -> None:
    """Show special offers / discounts."""
    await callback.answer()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('fire')} <b>تخفیف‌های ویژه</b>\n\n"
            f"{get_pe('diamond')} <b>پکیج پرمیوم تلگرام + استارز</b>\n"
            "   خرید اشتراک سالانه + ۵۰۰ استارز با ۱۵٪ تخفیف\n\n"
            f"{get_pe('bot')} <b>اکانت هوش مصنوعی</b>\n"
            "   خرید همزمان ChatGPT + Gemini با ۱۰٪ تخفیف\n\n"
            f"{get_pe('star')} برای بهره‌مندی از تخفیف‌ها، محصول مورد نظر را "
            "از منوی خرید انتخاب کنید.\n\n"
            f"{get_pe('calendar')} تخفیف‌ها محدود هستند!",
            reply_markup=back_to_menu_kb(),
        )
    await callback.answer()


# ─── Reply keyboard: 🛍 فروشگاه ────────────────────────────────────

@router.message(F.text.contains("فروشگاه"))
async def reply_btn_shop(message: Message) -> None:
    """Show the inline shop menu when the user taps the shop button."""
    await message.answer(
        f"{get_pe('home')} <b>منوی خرید</b>\nیک سرویس را انتخاب کنید:",
        reply_markup=await main_menu_kb(),
    )


# ─── Reply keyboard: 👤 پروفایل ────────────────────────────────────

@router.message(F.text.contains("پروفایل"))
async def reply_btn_profile(message: Message) -> None:
    """Show the user's profile information."""
    user = await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    username_display = f"@{user['username']}" if user["username"] else "—"
    admin_badg = f" | {get_pe('shield')} مدیر" if user["is_admin"] else ""
    wallet_balance = await get_wallet_balance(message.from_user.id)

    text = (
        f"{get_pe('user')} <b>پروفایل من</b>\n\n"
        f"{get_pe('id_icon')} شناسه: <code>{user['user_id']}</code>\n"
        f"{get_pe('name_badge')} نام: {user['full_name']}\n"
        f"{get_pe('user')} یوزرنیم: {username_display}{admin_badg}\n"
        f"{get_pe('purse')} موجودی کیف پول: <b>{wallet_balance:,}</b> تومان\n"
        f"{get_pe('calendar')} تاریخ عضویت: {user['joined_at'][:10] if user['joined_at'] else '—'}"
    )
    await message.answer(text, reply_markup=main_reply_kb())


# ─── Reply keyboard: 🎧 پشتیبانی ───────────────────────────────────

@router.message(F.text.contains("پشتیبانی"))
async def reply_btn_support(message: Message, state: FSMContext) -> None:
    """Redirect to the ticket system and set FSM state so the next message is captured."""
    from states.states import TicketStates
    await state.set_state(TicketStates.waiting_message)
    await message.answer(
        f"{get_pe('call')} <b>پشتیبانی</b>\n\n"
        f"{get_pe('ticket')} لطفاً پیام یا مشکل خود را به صورت متنی بنویسید.\n"
        "پیام شما مستقیماً به تیم پشتیبانی ارسال خواهد شد.\n\n"
        "برای انصراف، روی دکمه «🔙 بازگشت به منو» کلیک کنید.",
        reply_markup=back_to_menu_kb(),
    )


# ─── Reply keyboard: 📋 سفارشات ─────────────────────────────────

@router.message(F.text.contains("سفارشات"))
async def reply_btn_orders(message: Message) -> None:
    """Show the user's order history when the orders button is tapped."""
    orders = await get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(
            f"{get_pe('ticket')} <b>پیگیری سفارشات</b>\n\nشما هنوز سفارشی ثبت نکرده‌اید.",
            reply_markup=main_reply_kb(),
        )
    else:
        lines = [f"{get_pe('ticket')} <b>پیگیری سفارشات</b>\n"]
        for o in orders[:10]:
            lines.append(_format_order_line(o))
        lines.append("\nبرای اطلاعات بیشتر روی شماره سفارش کلیک کنید.")
        await message.answer(
            "\n".join(lines),
            reply_markup=main_reply_kb(),
        )


# ─── Back to menu ────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:back")
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('home')} <b>منوی اصلی</b>\nیک سرویس را انتخاب کنید:",
            reply_markup=await main_menu_kb(),
        )
    await callback.answer()


# ─── Menu entry points ──────────────────────────────────────────────

@router.callback_query(F.data == "menu:premium")
async def cb_menu_premium(callback: CallbackQuery) -> None:
    await callback.answer()
    from keyboards.inline import premium_duration_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('star')} <b>تلگرام پرمیوم</b>\nیک پلن اشتراک را انتخاب کنید:",
            reply_markup=await premium_duration_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:ai_accounts")
async def cb_menu_ai(callback: CallbackQuery) -> None:
    await callback.answer()
    from keyboards.inline import ai_platform_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('bot')} <b>اکانت هوش مصنوعی پرمیوم</b>\nیک پلتفرم را انتخاب کنید:",
            reply_markup=await ai_platform_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:design")
async def cb_menu_design(callback: CallbackQuery) -> None:
    await callback.answer()
    from keyboards.inline import design_category_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('fire')} <b>خدمات طراحی</b>\nیک دسته را انتخاب کنید:",
            reply_markup=await design_category_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:security")
async def cb_menu_security(callback: CallbackQuery) -> None:
    await callback.answer()
    from keyboards.inline import security_tariff_kb
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('shield')} <b>امنیت صفحه</b>\nیک تعرفه را انتخاب کنید:",
            reply_markup=await security_tariff_kb(),
        )
    await callback.answer()


# ─── Virtual Number (شماره مجازی) — New API ───────────────────────

@router.callback_query(F.data == "menu:virtual_number")
async def cb_menu_virtual_number(callback: CallbackQuery) -> None:
    """Show the ReplyKeyboard for virtual-number service selection."""
    try:
        from utils.shiznumber import get_services_map
        services_map = await get_services_map()

        if not services_map:
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    "⚠️ ارتباط با سرور ارائه‌دهنده برقرار نشد. لطفاً کمی بعد تلاش کنید.",
                    reply_markup=back_to_menu_kb(),
                )
            await callback.answer()
            return

        text = (
            "📈 جهت خرید شماره مجازی لطفا نوع سرویس و پلتفرم مدنظر خود را "
            "از کیبورد پایین انتخاب نمایید؛"
        )
        # Send a new message with the dynamic reply keyboard
        await callback.message.answer(text, reply_markup=virtual_services_reply_kb(services_map))
    except Exception as e:
        logger.error(f"CRASH IN MENU VIRTUAL: {e}", exc_info=True)
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=back_to_menu_kb(),
            )
    await callback.answer()


@router.message(IsDynamicService())
async def process_shiz_service_selection(
    message: Message,
    state: FSMContext,
    shiz_slug: str,
) -> None:
    """Handle a service tapped from the dynamic ReplyKeyboard.

    The ``IsDynamicService`` filter resolves the tapped text against the
    live API services map and passes the matching slug as ``shiz_slug``.
    """
    from utils.shiznumber import get_service_numbers
    from utils.shiznumber import get_services_map
    from keyboards.inline import virtual_country_kb

    slug = shiz_slug
    services_map = await get_services_map()

    await message.answer(f"⏳ در حال دریافت لیست کشورهای {message.text}...")

    countries = await get_service_numbers(slug)

    if not countries:
        await message.answer(
            "⚠️ در حال حاضر شماره‌ای برای این سرویس موجود نیست.\n"
            "لطفاً بعداً دوباره تلاش کنید.",
            reply_markup=virtual_services_reply_kb(services_map),
        )
        return

    await state.set_state(VirtualNumberStates.choose_country)
    await state.update_data(
        virtual_slug=slug,
        virtual_countries=countries,
    )

    text = (
        f"🌐 سرویس {message.text} انتخاب شد.\n"
        "👉 جهت خرید شماره مجازی روی نام کشور مورد نظر خود کلیک نمایید:"
    )

    await message.answer(text, reply_markup=virtual_country_kb(countries, slug, 0))


@router.message(F.text == "🔙 بازگشت")
async def reply_btn_virtual_back(message: Message, state: FSMContext) -> None:
    """Handle the Back button from the virtual-services reply keyboard.

    Returns to the main reply keyboard.
    """
    await state.clear()
    await message.answer(
        f"{get_pe('home')} <b>منوی اصلی</b>",
        reply_markup=main_reply_kb(),
    )


@router.callback_query(F.data.startswith("v_app:"))
async def cb_app_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """An app was selected via inline toggle — fetch its countries and show the table (page 0).

    With the Shiznumber migration, the callback data is ``v_app:{slug}``.
    """
    try:
        slug = callback.data.split(":", 1)[1]

        from utils.shiznumber import get_service_numbers
        from keyboards.inline import virtual_country_kb, virtual_services_kb
        from states.states import VirtualNumberStates

        await callback.message.edit_text("⏳ در حال دریافت لیست کشورها...")

        countries = await get_service_numbers(slug)

        if not countries:
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    "⚠️ در حال حاضر شماره‌ای برای این سرویس موجود نیست.\n"
                    "لطفاً بعداً دوباره تلاش کنید.",
                    reply_markup=await virtual_services_kb(),
                )
            await callback.answer()
            return

        await state.set_state(VirtualNumberStates.choose_country)
        await state.update_data(
            virtual_slug=slug,
            virtual_countries=countries,
        )

        text = (
            f"🌐 سرویس انتخاب شد.\n"
            "👉 جهت خرید شماره مجازی روی نام کشور مورد نظر خود کلیک نمایید:"
        )

        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                text,
                reply_markup=virtual_country_kb(countries, slug, page=0),
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"CRASH IN APP HANDLER: {e}", exc_info=True)
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=await virtual_services_kb(),
            )
        await callback.answer()


@router.callback_query(F.data == "menu:back_main")
async def cb_back_to_main(callback: CallbackQuery) -> None:
    """Back to the main shop menu (used by the Virtual Number grid footer)."""
    await callback.answer()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{get_pe('home')} <b>منوی اصلی</b>\nیک سرویس را انتخاب کنید:",
            reply_markup=await main_menu_kb(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("v_page:"))
async def cb_virtual_country_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Flip between virtual-country pages using the FSM-cached list."""
    try:
        parts = callback.data.split(":")
        slug = parts[1]
        page = int(parts[2])

        from keyboards.inline import virtual_country_kb, virtual_services_kb

        data = await state.get_data()
        countries = data.get("virtual_countries")
        non_report = data.get("non_report", False)

        # Refresh if the cached list belongs to a different slug
        if not countries or data.get("virtual_slug") != slug:
            from utils.shiznumber import get_service_numbers
            countries = await get_service_numbers(slug)
            await state.update_data(
                virtual_slug=slug,
                virtual_countries=countries,
            )

        if not countries:
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    "⚠️ لیست کشورها منقضی شده است.",
                    reply_markup=await virtual_services_kb(),
                )
            await callback.answer()
            return

        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(
                reply_markup=virtual_country_kb(countries, slug, page=page, non_report=non_report)
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"CRASH IN PAGINATION: {e}", exc_info=True)
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=await virtual_services_kb(),
            )
        await callback.answer()


@router.callback_query(F.data.startswith("v_buy:"))
async def cb_virtual_buy(callback: CallbackQuery, state: FSMContext) -> None:
    """User tapped a country row — show confirmation with the final price.

    The callback data format is ``v_buy:{item_id}`` where item_id is the
    unique Shiznumber number-item ID.
    """
    try:
        parts = callback.data.split(":")
        if len(parts) < 2:
            await callback.answer("⚠️ داده نامعتبر.", show_alert=True)
            return

        item_id = parts[1]

        from keyboards.inline import virtual_services_kb, back_to_menu_kb

        data = await state.get_data()
        countries = data.get("virtual_countries", [])
        slug = data.get("virtual_slug", "")

        selected = next((c for c in countries if str(c.get("id")) == item_id), None)

        if selected is None:
            await callback.answer("⚠️ کشور یافت نشد.", show_alert=True)
            return

        if not selected.get("in_stock"):
            await callback.answer("⚠️ این کشور در حال حاضر موجود نیست.", show_alert=True)
            return

        final_price = selected.get("final_price", selected.get("base_price", 0))
        price_str = f"{final_price:,}".replace(",", "،")
        country_name = selected.get("country_fa", "نامشخص")

        wallet_balance = await get_wallet_balance(callback.from_user.id)
        shortage = max(0, int(final_price) - wallet_balance)
        shortage_str = f"{shortage:,}".replace(",", "،")

        await state.update_data(
            virtual_slug=slug,
            country_name=country_name,
            item_id=item_id,
            price_toman=final_price,
            base_price_toman=selected.get("base_price", final_price),
        )
        await state.set_state(VirtualNumberStates.confirm_buy)

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from utils.emojis import get_premium_id

        if shortage <= 0:
            confirm_label = "خرید از کیف پول"
        else:
            confirm_label = f"خرید — {shortage_str} تومان"

        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=confirm_label,
                                  callback_data="virtual:confirm",
                                  style="success",
                                  icon_custom_emoji_id=get_premium_id("check"))],
            [InlineKeyboardButton(text="انصراف",
                                  callback_data=f"v_page:{slug}:0",
                                  style="danger",
                                  icon_custom_emoji_id=get_premium_id("cross"))],
        ])

        wallet_line = f"{get_pe('purse')} موجودی کیف پول شما: <b>{wallet_balance:,}</b> تومان\n"
        if shortage > 0:
            pay_line = f"{get_pe('card')} مبلغ پرداختی از درگاه: <b>{shortage_str} تومان</b>\n"
        else:
            pay_line = f"{get_pe('check')} کل مبلغ از <b>کیف پول</b> کسر می‌شود.\n"

        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('key_lock')} <b>خرید شماره مجازی</b>\n\n"
                f"{get_pe('web')} کشور: <b>{country_name}</b>\n"
                f"{get_pe('money')} قیمت نهایی: <b>{price_str} تومان</b>\n"
                f"{wallet_line}{pay_line}\n"
                "پس از خرید، یک شماره مجازی دریافت خواهید کرد.\n"
                "کد تأیید ظرف چند دقیقه برای شما ارسال می‌شود.\n\n"
                "آیا مطمئن هستید؟",
                reply_markup=confirm_kb,
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"CRASH IN V_BUY: {e}", exc_info=True)
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=await virtual_services_kb(),
            )
        await callback.answer()


@router.callback_query(F.data == "virtual:confirm", VirtualNumberStates.confirm_buy)
async def cb_virtual_confirm_buy(callback: CallbackQuery, state: FSMContext) -> None:
    """User confirmed — pay the DIFFERENCE from the wallet + gateway.

    Wallet math:
        shortage = final_price - user_wallet_balance
      • shortage > 0  → Zarinpal invoice is STRICTLY for ``shortage``,
                        the wallet covers the rest.
      • shortage <= 0 → Zarinpal is bypassed entirely; the wallet pays
                        the full price and delivery runs immediately.
    """
    wallet_used = 0
    order_id = None
    try:
        await callback.answer()
        data = await state.get_data()
        slug = data.get("virtual_slug", "")
        item_id = data.get("item_id")
        country_name = data.get("country_name", "نامشخص")
        price_toman = data.get("price_toman", 0)

        if not slug or not item_id or not price_toman:
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    "⚠️ اطلاعات سفارش ناقص است. لطفاً دوباره شروع کنید.",
                    reply_markup=await main_menu_kb(),
                )
            await state.clear()
            return

        from database.db import (
            create_order,
            create_payment,
            update_payment_authority,
            update_order_status,
            get_wallet_balance,
            deduct_from_wallet,
            add_to_wallet,
        )
        from utils.zarinpal import request_payment
        from utils.delivery import deliver_product
        from keyboards.inline import pay_link_kb

        final_irt = int(price_toman)
        base_price = data.get("base_price_toman", final_irt)

        # ── Pre-purchase panel balance check (white-label) ──
        panel_balance = await get_panel_balance()
        if panel_balance < base_price:
            with contextlib.suppress(Exception):
                await callback.message.edit_text(
                    f"{get_pe('warning')} <b>ارتباط با سرور موقتاً دچار اختلال شده است.</b>\n\n"
                    "لطفاً دقایقی بعد دوباره تلاش کنید.",
                    reply_markup=back_to_menu_kb(),
                )
            await state.clear()

            # Silently alert admins with full details
            from config import config as _cfg
            for admin_id in _cfg.ADMIN_IDS:
                with contextlib.suppress(Exception):
                    await callback.message.bot.send_message(
                        admin_id,
                        f"🚨 <b>هشدار فوری:</b>\n"
                        f"موجودی پنل برای خرید شماره مجازی کافی نیست!\n\n"
                        f"💰 موجودی فعلی: <b>{panel_balance:,}</b> تومان\n"
                        f"💵 مبلغ مورد نیاز: <b>{base_price:,}</b> تومان\n"
                        f"🌍 سرویس: {slug} | آیتم: {item_id}\n"
                        f"👤 کاربر: <code>{callback.from_user.id}</code>"
                    )
            return

        user_wallet_balance = await get_wallet_balance(callback.from_user.id)
        shortage = final_irt - user_wallet_balance
        order_details = f"سرویس: {slug} | آیتم: {item_id}"

        if shortage <= 0:
            # ── Wallet covers everything — bypass Zarinpal entirely ──
            if not await deduct_from_wallet(callback.from_user.id, final_irt):
                with contextlib.suppress(TelegramBadRequest):
                    await callback.message.edit_text(
                        f"{get_pe('cross')} موجودی کیف پول شما کافی نیست.\n"
                        "لطفاً کیف پول خود را شارژ کنید یا دوباره تلاش کنید.",
                        reply_markup=back_to_menu_kb(),
                    )
                await state.clear()
                return

            order_id = await create_order(
                user_id=callback.from_user.id,
                product=f"شماره مجازی: {country_name}",
                details=order_details,
                amount_irt=final_irt,
            )
            await update_order_status(order_id, "paid")

            # Confirm the wallet charge to the user, then deliver instantly.
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    f"{get_pe('purse')} <b>پرداخت از کیف پول انجام شد!</b>\n\n"
                    f"{get_pe('web')} کشور: <b>{country_name}</b>\n"
                    f"{get_pe('money')} مبلغ کسر شده: <b>{final_irt:,}</b> تومان\n\n"
                    "در حال تحویل شماره مجازی…",
                    reply_markup=None,
                )
            await deliver_product(
                bot=callback.bot,
                user_id=callback.from_user.id,
                order_id=order_id,
                product=f"شماره مجازی: {country_name}",
                details=order_details,
            )
            await state.clear()
            return

        # ── Partial wallet: the gateway charge is ONLY the shortage ──
        order_id = await create_order(
            user_id=callback.from_user.id,
            product=f"شماره مجازی: {country_name}",
            details=order_details,
            amount_irt=final_irt,
        )

        result = await request_payment(
            amount_irt=shortage,
            description=f"خرید شماره مجازی {country_name}",
        )

        if not result.success or not result.authority:
            await update_order_status(order_id, "cancelled")
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    f"{get_pe('cross')} درخواست پرداخت ناموفق بود:\n"
                    "لطفاً بعداً دوباره تلاش کنید.",
                    reply_markup=back_to_menu_kb(),
                )
            await state.clear()
            return

        wallet_used = min(user_wallet_balance, final_irt)  # == wallet here (shortage>0)
        if wallet_used > 0 and not await deduct_from_wallet(callback.from_user.id, wallet_used):
            await update_order_status(order_id, "cancelled")
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    f"{get_pe('cross')} موجودی کیف پول شما تغییر کرده است.\n"
                    "لطفاً دوباره تلاش کنید.",
                    reply_markup=back_to_menu_kb(),
                )
            await state.clear()
            return

        payment_id = await create_payment(order_id, shortage)
        await update_payment_authority(payment_id, result.authority)
        await state.update_data(
            order_id=order_id, payment_id=payment_id,
            authority=result.authority, amount_irt=shortage,
            wallet_used=wallet_used,
        )
        await state.set_state(VirtualNumberStates.waiting_code)

        shortage_str = f"{shortage:,}".replace(",", "،")
        price_str = f"{final_irt:,}".replace(",", "،")
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('card')} <b>پرداخت: شماره مجازی {country_name}</b>\n\n"
                f"{get_pe('money')} مبلغ نهایی: <b>{price_str} تومان</b>\n"
                f"{get_pe('purse')} موجودی کیف پول شما: {user_wallet_balance:,} تومان\n"
                f"{get_pe('card')} مبلغ پرداختی از درگاه: <b>{shortage_str} تومان</b>\n\n"
                "برای پرداخت روی دکمه زیر کلیک کنید:\n"
                "<i>پس از پرداخت موفق، شماره مجازی و کد تأیید برای شما ارسال خواهد شد.</i>",
                reply_markup=pay_link_kb(result.start_pay_url),
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"CRASH IN VIRTUAL CONFIRM: {e}", exc_info=True)
        # Refund the wallet portion so a failed setup never eats credit.
        if wallet_used > 0:
            with contextlib.suppress(Exception):
                await add_to_wallet(callback.from_user.id, wallet_used)
        if order_id:
            with contextlib.suppress(Exception):
                await update_order_status(order_id, "cancelled")
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "⚠️ خطایی در فرآیند پرداخت رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=back_to_menu_kb(),
            )
        await state.clear()
        await callback.answer()


@router.callback_query(F.data == "ignore")
async def cb_ignore(callback: CallbackQuery) -> None:
    """Silently acknowledge taps on header/disabled buttons."""
    await callback.answer()


@router.callback_query(F.data.startswith("v_filter:"))
async def cb_virtual_filter(callback: CallbackQuery) -> None:
    """Placeholder for the Advanced Filter feature."""
    await callback.answer("فیلتر پیشرفته به زودی فعال می‌شود!", show_alert=True)


@router.callback_query(F.data.startswith("v_bulk:"))
async def cb_virtual_bulk(callback: CallbackQuery) -> None:
    """Placeholder for the Bulk Purchase feature."""
    await callback.answer("خرید گروهی به زودی فعال می‌شود!", show_alert=True)


@router.callback_query(F.data.startswith("v_nr:"))
async def cb_virtual_non_report(callback: CallbackQuery, state: FSMContext) -> None:
    """Toggle the non-report number filter on/off and re-render the page."""
    try:
        parts = callback.data.split(":")
        slug = parts[1]
        current_state = parts[2] if len(parts) > 2 else "off"
        new_state = "off" if current_state == "on" else "on"
        non_report = new_state == "on"

        data = await state.get_data()
        countries = data.get("virtual_countries", [])

        if not countries or data.get("virtual_slug") != slug:
            from utils.shiznumber import get_service_numbers
            countries = await get_service_numbers(slug)
            await state.update_data(virtual_slug=slug, virtual_countries=countries)

        if not countries:
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    "⚠️ لیست کشورها منقضی شده است.",
                    reply_markup=await virtual_services_kb(),
                )
            await callback.answer()
            return

        await state.update_data(non_report=non_report)

        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(
                reply_markup=virtual_country_kb(countries, slug, page=0, non_report=non_report)
            )
        label = "فعال" if non_report else "غیرفعال"
        await callback.answer(f"🔍 فیلتر غیرریپورت: {label}", show_alert=True)
    except Exception as e:
        logger.error(f"CRASH IN V_NR: {e}", exc_info=True)
        await callback.answer("⚠️ خطا در تغییر فیلتر.", show_alert=True)


# ─── Market Rates (Live Exchange Rates) ─────────────────────────────

@router.callback_query(F.data == "menu:market_rates")
async def cb_market_rates(callback: CallbackQuery) -> None:
    await callback.answer()
    from utils.pricing import get_market_data

    data = await get_market_data()
    if not data:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('warning')} دریافت اطلاعات بازار با مشکل مواجه شد.\nلطفاً دوباره تلاش کنید.",
                reply_markup=market_rates_refresh_kb(),
            )
        await callback.answer()
        return

    lines = [f"{get_pe('chart')} <b>قیمت لحظه‌ای ارزها و طلا</b>\n"]

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
            return f"  {name}: {get_pe('warning')} موجود نیست"

        price = item.get("price")
        change = as_number(item.get("change_percent"))
        change_icon = get_pe("arrow_up") if change >= 0 else get_pe("arrow_down")
        return (
            f"  {name}: <b>{format_number(price)}</b> {unit} "
            f"{change_icon} {change:+.2f}%"
        )

    # ── Popular Currencies (prices are in Toman) ──
    lines.append(f"{get_pe('money')} <b>ارزهای پرکاربرد:</b>")
    lines.append(format_item(currency, "USD", f"{get_pe('flag_us')} دلار آمریکا", "تومان"))
    lines.append(format_item(currency, "EUR", f"{get_pe('flag_eu')} یورو", "تومان"))
    lines.append(format_item(currency, "USDT_IRT", f"{get_pe('coin_new')} تتر", "تومان"))
    lines.append("")

    # ── Gold & Coins (prices are in Toman) ──
    lines.append(f"{get_pe('coin_new')} <b>طلا و سکه:</b>")
    lines.append(format_item(gold, "IR_GOLD_18K", f"{get_pe('medal_gold')} طلای ۱۸ عیار", "تومان"))
    lines.append(format_item(gold, "IR_COIN_EMAMI", f"{get_pe('coin_new')} سکه امامی", "تومان"))
    lines.append(format_item(gold, "IR_COIN_BAHAR", f"{get_pe('coin_new')} سکه بهار آزادی", "تومان"))
    lines.append("")

    # ── Cryptocurrencies (prices are in USD) ──
    lines.append(f"{get_pe('diamond')} <b>رمزارزهای اصلی:</b>")
    lines.append(format_item(cryptocurrency, "BTC", f"{get_pe('coin')} بیت‌کوین", "USD"))
    lines.append(format_item(cryptocurrency, "ETH", f"{get_pe('diamond')} اتریوم", "USD"))
    lines.append(format_item(cryptocurrency, "SOL", f"{get_pe('sparkles')} سولانا", "USD"))
    lines.append("")
    lines.append(f"{get_pe('clock')} نرخ‌ها لحظه‌ای هستند و هر ۵ دقیقه به‌روز می‌شوند.")

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=market_rates_refresh_kb(),
        )
    await callback.answer()


# ─── My Orders (پیگیری سفارشات) ─────────────────────────────────────

@router.callback_query(F.data == "menu:my_orders")
async def cb_my_orders(callback: CallbackQuery) -> None:
    await callback.answer()
    orders = await get_user_orders(callback.from_user.id)
    if not orders:
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                f"{get_pe('ticket')} <b>پیگیری سفارشات</b>\n\nشما هنوز سفارشی ثبت نکرده‌اید.",
                reply_markup=back_to_menu_kb(),
            )
    else:
        lines = [f"{get_pe('ticket')} <b>پیگیری سفارشات</b>\n"]
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
        "pending":   (get_pe("yellow_circle"), "در انتظار پرداخت"),
        "paid":      (get_pe("green_circle"), "پرداخت شده / در صف انجام"),
        "delivered": (get_pe("check"), "انجام شده"),
        "cancelled": (get_pe("cross"), "لغو شده"),
    }
    emoji, label = status_map.get(o["status"], (get_pe("question"), o["status"]))
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


@router.callback_query()
async def unhandled_callback(callback: CallbackQuery) -> None:
    """Catch-all for unrecognised callback_data — log silently, no alert."""
    logger.warning("Unhandled callback_data: %s (user=%s)", callback.data, callback.from_user.id)
    await callback.answer()
