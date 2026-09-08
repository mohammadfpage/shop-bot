"""
Dynamic pricing utility with live BrsApi exchange rates.

Formula:
    final_price_toman = (product_usd × live_usd_rate) × (1 + PROFIT_MARGIN / 100)

The USD rate is fetched from BrsApi and cached for 5 minutes.
"""

import logging
import time
from typing import Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)

# ─── Rate cache (5-minute TTL) ─────────────────────────────────────
_rate_cache: Optional[dict] = None  # full API response
_rate_cache_ts: float = 0.0
_CACHE_TTL: float = 300.0  # 5 minutes


async def _fetch_brs_api() -> Optional[dict]:
    """Fetch the full BrsApi response and cache it for 5 minutes."""
    global _rate_cache, _rate_cache_ts

    if _rate_cache is not None and (time.time() - _rate_cache_ts) < _CACHE_TTL:
        return _rate_cache

    # اضافه کردن هدر برای جلوگیری از خطای 403
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                config.BRS_API_URL, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _rate_cache = data
                    _rate_cache_ts = time.time()
                    logger.info("BrsApi response cached at %s", _rate_cache_ts)
                    return _rate_cache
                else:
                    logger.warning("BrsApi returned status %s", resp.status)
                    return _rate_cache
    except Exception as exc:
        logger.warning("Failed to fetch BrsApi: %s", exc)
        return _rate_cache  # return stale cache if available

async def get_usd_rate() -> float:
    """Return the live USD → Tomans exchange rate from BrsApi.

    Falls back to the last known saved rate from the shared RateCache
    (the in-memory cache) instead of a hardcoded value. If no rate is
    cached yet, returns a conservative default of 570,000 Tomans.
    """

    def _extract_usd(data: Optional[dict]) -> Optional[float]:
        if data and "currency" in data:
            for item in data["currency"]:
                if item.get("symbol") == "USD":
                    rate = item.get("price", 0)
                    if rate and float(rate) > 0:
                        return float(rate)
        return None

    data = await _fetch_brs_api()
    live = _extract_usd(data)
    if live is not None:
        logger.info("Live USD/Toman rate: %s", live)
        return live

    # No live rate → use the last known saved rate from the shared cache
    from utils.cache import rate_cache
    cached = _extract_usd(rate_cache.get_data())
    if cached is not None:
        logger.warning("Using last known cached USD rate: %s", cached)
        return cached

    # Nothing anywhere yet → conservative fallback (only right after boot)
    logger.warning("No cached rate available; using fallback USD rate: 570000")
    return 570000.0


async def get_market_data() -> Optional[dict]:
    """Return the full BrsApi market data (cached)."""
    return await _fetch_brs_api()


def calculate_final_price(product_usd: float, exchange_rate: float) -> int:
    """Return the final price in Tomans (rounded to nearest 1000).

    Formula: (product_usd × exchange_rate) × (1 + PROFIT_MARGIN%)
    """
    raw = product_usd * exchange_rate * (1 + config.PROFIT_MARGIN_PERCENT / 100)
    # Round to nearest 1000 Toman for cleaner pricing
    return int(round(raw / 1000) * 1000)


async def price_display(product_usd: float) -> str:
    """Return a formatted price string like '۵۹,۰۰۰ تومان'."""
    rate = await get_usd_rate()
    final = calculate_final_price(product_usd, rate)
    formatted = f"{final:,}".replace(",", "،")
    return f"{formatted} تومان"


async def price_display_raw(product_usd: float) -> tuple[int, float]:
    """Return (final_toman, exchange_rate) for downstream use."""
    rate = await get_usd_rate()
    final = calculate_final_price(product_usd, rate)
    return final, rate
