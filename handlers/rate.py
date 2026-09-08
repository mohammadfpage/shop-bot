"""
Handler: 💵 قیمت روز ارز (Daily Exchange Rates).

When the user taps the reply-keyboard button "💵 قیمت روز ارز", the bot
immediately responds from the in-memory cache (no API call).  If the cache
is still empty (server just restarted and the first fetch hasn't completed
yet), the user sees a polite "please wait" message in Persian.

All user-facing text in Persian (فارسی).
"""

import contextlib

from aiogram import Router, F
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from keyboards.reply import main_reply_kb
from keyboards.inline import market_rates_refresh_kb
from utils.emojis import get_pe

router = Router(name="rate")


def _as_number(value: object) -> float:
    """Convert API numbers (including numeric strings) to floats."""
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("،", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _format_number(value: object) -> str:
    number = _as_number(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.8f}".rstrip("0").rstrip(".")


def _format_item(items: dict, symbol: str, name: str, unit: str) -> str:
    item = items.get(symbol)
    if not item:
        return f"  {name}: {get_pe('warning')} موجود نیست"
    price = item.get("price")
    change = _as_number(item.get("change_percent"))
    change_icon = get_pe("arrow_up") if change >= 0 else get_pe("arrow_down")
    return (
        f"  {name}: <b>{_format_number(price)}</b> {unit} "
        f"{change_icon} {change:+.2f}%"
    )


@router.message(F.text == "💵 قیمت روز ارز")
async def reply_btn_rate(message: Message) -> None:
    """Serve cached exchange rates to the user — no API call made here."""
    from utils.cache import rate_cache

    # ── Cache not ready yet? ───────────────────────────────────────
    if not rate_cache.is_ready():
        await message.answer(
            f"{get_pe('refresh')} در حال بروزرسانی قیمت‌ها... لطفاً چند ثانیه دیگر مجدداً تلاش کنید.",
            reply_markup=main_reply_kb(),
        )
        return

    data = rate_cache.get_data()

    # ── Build lookup tables from the cached JSON ───────────────────
    def build_lookup(category: str) -> dict[str, dict]:
        return {
            item["symbol"]: item
            for item in data.get(category, [])
            if isinstance(item, dict) and item.get("symbol")
        }

    currency = build_lookup("currency")
    gold = build_lookup("gold")
    cryptocurrency = build_lookup("cryptocurrency")

    # ── Compose the message ────────────────────────────────────────
    lines = [f"{get_pe('chart')} <b>قیمت لحظه‌ای ارزها و طلا</b>\n"]

    # Popular currencies
    lines.append(f"{get_pe('money')} <b>ارزهای پرکاربرد:</b>")
    lines.append(_format_item(currency, "USD", f"{get_pe('flag_us')} دلار آمریکا", "تومان"))
    lines.append(_format_item(currency, "EUR", f"{get_pe('flag_eu')} یورو", "تومان"))
    lines.append(_format_item(currency, "USDT_IRT", f"{get_pe('coin_new')} تتر", "تومان"))
    lines.append("")

    # Gold & Coins
    lines.append(f"{get_pe('coin_new')} <b>طلا و سکه:</b>")
    lines.append(_format_item(gold, "IR_GOLD_18K", f"{get_pe('medal_gold')} طلای ۱۸ عیار", "تومان"))
    lines.append(_format_item(gold, "IR_COIN_EMAMI", f"{get_pe('coin_new')} سکه امامی", "تومان"))
    lines.append(_format_item(gold, "IR_COIN_BAHAR", f"{get_pe('coin_new')} سکه بهار آزادی", "تومان"))
    lines.append("")

    # Cryptocurrencies
    lines.append(f"{get_pe('diamond')} <b>رمزارزهای اصلی:</b>")
    lines.append(_format_item(cryptocurrency, "BTC", f"{get_pe('coin')} بیت‌کوین", "USD"))
    lines.append(_format_item(cryptocurrency, "ETH", f"{get_pe('diamond')} اتریوم", "USD"))
    lines.append(_format_item(cryptocurrency, "SOL", f"{get_pe('sparkles')} سولانا", "USD"))

    lines.append("")
    lines.append(
        f"{get_pe('clock')} آخرین بروزرسانی: {rate_cache.last_updated_str()}\n"
        f"{get_pe('refresh')} قیمت‌ها هر ۵ دقیقه به‌روز می‌شوند."
    )

    await message.answer(
        "\n".join(lines),
        reply_markup=main_reply_kb(),
    )
