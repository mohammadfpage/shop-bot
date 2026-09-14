"""
Ozvinoo API service for virtual numbers (شماره مجازی).

Base URL: https://api.ozvinoo.xyz/
The provider strictly uses the V1 /web/{token}/... format for EVERYTHING:

    GET /web/{token}/applications                  → app list; find Telegram (code == "tg")
    GET /web/{token}/get-prices/{service_id}       → countries with base prices
    GET /web/{token}/getNumber/{service_id}/{country} → buy a virtual number
    GET /web/{token}/getCode/{request_id}          → fetch the SMS verification code

Dynamic Profit Margin:
    Final_Price = Base_Price + (Base_Price × (Margin / 100))
    Margin is fetched from config.ACCOUNT_PROFIT_MARGIN_PERCENT (default 30%).
"""

import logging
import time
from typing import Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)

TOKEN = config.OZVINOO_API_KEY

# ─── Cache (5-minute TTL) ────────────────────────────────────────
_cache: dict = {}
_cache_ts: float = 0.0
_CACHE_TTL: float = 300.0  # 5 minutes


def _is_cache_valid() -> bool:
    return (time.time() - _cache_ts) < _CACHE_TTL


# ══════════════════════════════════════════════════════════════════════
#  VIRTUAL NUMBERS (V1 /web/{token}/ API — "شماره مجازی")
# ══════════════════════════════════════════════════════════════════════

async def get_telegram_countries() -> list[dict]:
    """Fetch Telegram countries and apply the profit margin.

    Step A: Resolve the Telegram service ID from /applications
    (fallback to 1). Step B: Load prices from /get-prices/{service_id}
    and mark up every base price by config.ACCOUNT_PROFIT_MARGIN_PERCENT.

    Returns:
        List of dicts: {"country", "service_id", "base_price",
                        "final_price", "in_stock"}.
    """
    if _cache.get("tg_countries") and _is_cache_valid():
        return _cache["tg_countries"]

    async with aiohttp.ClientSession() as session:
        # Step A: Get service ID for Telegram
        service_id = 1  # Fallback ID
        async with session.get(
            f"https://api.ozvinoo.xyz/web/{TOKEN}/applications"
        ) as resp:
            data = await resp.json()
            if isinstance(data, dict):
                for key, app in data.items():
                    if isinstance(app, dict) and app.get("code") == "tg":
                        service_id = app.get("id")
                        break

        # Step B: Get countries and apply margin
        async with session.get(
            f"https://api.ozvinoo.xyz/web/{TOKEN}/get-prices/{service_id}"
        ) as resp:
            countries_data = await resp.json()

            result = []
            margin = config.ACCOUNT_PROFIT_MARGIN_PERCENT / 100
            if isinstance(countries_data, list):
                for item in countries_data:
                    if not isinstance(item, dict):
                        continue
                    base_price = int(item.get("price", 0))
                    final_price = int(base_price + (base_price * margin))
                    result.append({
                        "country": item.get("country", "نامشخص"),
                        "service_id": service_id,
                        "base_price": base_price,
                        "final_price": final_price,
                        "in_stock": "موجود" in str(item.get("count", "")),
                    })

    if result:
        _cache["tg_countries"] = result
        global _cache_ts
        _cache_ts = time.time()

    return result


async def buy_virtual_number(service_id: int, country: str) -> Optional[dict]:
    """Buy a virtual number for a service and a country.

    'country' must be the exact string returned from the API
    (e.g. "لهستان 🇵🇱" or its code).

    Returns:
        Raw JSON dict with 'request_id', 'number', 'price', etc.,
        or an 'error_code' on failure. None on connection errors.
    """
    url = f"https://api.ozvinoo.xyz/web/{TOKEN}/getNumber/{service_id}/{country}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.json()
    except Exception as exc:
        logger.error("Ozvinoo getNumber failed: %s", exc)
        return None


async def get_number_code(request_id: int) -> Optional[dict]:
    """Fetch the SMS verification code for an ordered number.

    Returns:
        Raw JSON dict with 'code' if ready, or
        {'error_code': 'wait_code', ...} if still waiting.
        None on connection errors.
    """
    url = f"https://api.ozvinoo.xyz/web/{TOKEN}/getCode/{request_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.json()
    except Exception as exc:
        logger.error("Ozvinoo getCode failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════
#  CACHE INVALIDATION
# ══════════════════════════════════════════════════════════════════════

def invalidate_cache() -> None:
    """Clear all cached API responses."""
    global _cache, _cache_ts
    _cache.clear()
    _cache_ts = 0.0
    logger.info("Ozvinoo API cache invalidated.")