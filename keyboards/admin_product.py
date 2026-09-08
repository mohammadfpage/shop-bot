"""
Dynamic admin product panel keyboards.

Builds inline keyboards from live database data using aiogram's
InlineKeyboardBuilder and the strongly-typed ProductCallback.

All labels in Persian (فارسی).
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.callback_data import ProductCallback
from utils.emojis import get_premium_id


def product_list_kb(products: list[dict]) -> InlineKeyboardMarkup:
    """Build an inline keyboard listing all products with their current prices.

    Each button shows: "🏷 Label — $XX.XX"
    Clicking it triggers ProductCallback(action="select", product_key=...).

    Args:
        products: list of dicts with keys: product_key, label, usd_price
    """
    builder = InlineKeyboardBuilder()

    for p in products:
        price_str = f"${p['usd_price']:.2f}"
        text = f"{p['label']} — {price_str}"
        builder.button(
            text=text,
            callback_data=ProductCallback(
                action="select",
                product_key=p["product_key"],
            ).pack(),
            style="primary",
            icon_custom_emoji_id=get_premium_id("box"),
        )

    # One button per row for readability
    builder.adjust(1)

    # Add "🔙 بازگشت به پنل" at the bottom
    builder.row(
        InlineKeyboardButton(
            text="بازگشت به پنل",
            callback_data="admin:panel",
            style="primary",
            icon_custom_emoji_id=get_premium_id("home"),
        )
    )

    return builder.as_markup()


def product_detail_kb(product_key: str, label: str, usd_price: float) -> InlineKeyboardMarkup:
    """Build the detail view for a single product with an edit button.

    Shows:
        📦 محصول: {label}
        💰 قیمت فعلی: ${usd_price:.2f}

    Plus an "✏️ ویرایش قیمت" button.
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="ویرایش قیمت",
        callback_data=ProductCallback(
            action="edit",
            product_key=product_key,
        ).pack(),
        style="primary",
        icon_custom_emoji_id=get_premium_id("gear"),
    )

    builder.row(
        InlineKeyboardButton(
            text="بازگشت به لیست",
            callback_data="admin:prices",
            style="primary",
            icon_custom_emoji_id=get_premium_id("down"),
        )
    )

    return builder.as_markup()


def product_edit_success_kb() -> InlineKeyboardMarkup:
    """Keyboard shown after a successful price update.

    Two navigation options:
        🔙 بازگشت به لیست — returns to the full product list (live DB prices)
        🔙 بازگشت به پنل  — returns to the admin dashboard
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="بازگشت به لیست",
            callback_data="admin:prices",
            style="primary",
            icon_custom_emoji_id=get_premium_id("down"),
        )],
        [InlineKeyboardButton(
            text="بازگشت به پنل",
            callback_data="admin:panel",
            style="primary",
            icon_custom_emoji_id=get_premium_id("home"),
        )],
    ])
