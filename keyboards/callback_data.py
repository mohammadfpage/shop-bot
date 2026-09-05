"""
Strongly-typed CallbackData classes for inline keyboard routing.

Using aiogram's CallbackData factory ensures:
    • Type safety — no raw string splitting in handlers.
    • Automatic serialization/deserialization.
    • Prefix-based filtering — e.g. F.data.startswith("prod:").
    • Easy extensibility — add new actions without breaking old ones.

Usage in handlers:
    from keyboards.callback_data import ProductCallback

    @router.callback_query(ProductCallback.filter(F.action == "select"))
    async def on_product_select(callback: CallbackQuery, callback_data: ProductCallback):
        product_key = callback_data.product_key  # typed, not split
"""

from aiogram.filters.callback_data import CallbackData


class ProductCallback(CallbackData, prefix="prod"):
    """CallbackData for admin product management.

    Actions:
        select   — admin tapped a product button (show details)
        edit     — admin tapped "ویرایش قیمت" (enter FSM state)

    Example serialized data:
        prod:select:chatgpt_premium
        prod:edit:chatgpt_premium
    """
    action: str       # "select" | "edit"
    product_key: str  # e.g. "chatgpt_premium"


class AdminNavCallback(CallbackData, prefix="admin"):
    """CallbackData for admin panel navigation (legacy compatibility).

    This wraps existing admin:XXX callback_data strings so they
    continue to work alongside the new ProductCallback system.
    """
    action: str  # e.g. "panel", "prices", "guide"


class WelcomeCallback(CallbackData, prefix="welcome"):
    """CallbackData for the user-facing welcome inline keyboard.

    Actions:
        categories — show product categories
        deals      — show special offers / discounts
        shop       — open the main shop menu
    """
    action: str  # "categories" | "deals" | "shop"

