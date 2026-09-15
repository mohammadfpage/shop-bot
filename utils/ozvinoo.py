"""
Ozvinoo API service for virtual numbers (شماره مجازی).

Base URL: https://api.ozvinoo.xyz/
The provider strictly uses the V1 /web/{token}/... format for EVERYTHING:

    GET /web/{token}/applications                  → app list (all services)
    GET /web/{token}/get-prices/{service_id}       → countries with base prices
    GET /web/{token}/getNumber/{service_id}/{country} → buy a virtual number
    GET /web/{token}/getCode/{request_id}          → fetch the SMS verification code
    GET /web/{token}/get-balance                   → fetch panel balance

Dynamic Profit Margin:
    Final_Price = Base_Price + (Base_Price × (Margin / 100))
    Margin is fetched live from the ``settings`` table
    (key ``account_profit_margin``) so admin changes apply immediately.
    Falls back to config.ACCOUNT_PROFIT_MARGIN_PERCENT (default 30%) if unset.
"""

import json
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


def _parse_in_stock(count) -> bool:
    """Parse the ``count`` field into a boolean stock flag.

    Supports both numeric counts (0 → out of stock) and Persian/English
    presence words returned by some providers.
    """
    if count is None:
        return True
    s = str(count).strip().replace(",", "").replace("،", "")
    if not s:
        return True
    try:
        return int(float(s)) > 0
    except ValueError:
        low = s.lower()
        return ("موجود" in s) or ("available" in low) or (s not in ("", "0", "ناموجود", "unavailable"))


# ══════════════════════════════════════════════════════════════════════
#  VIRTUAL NUMBERS (V1 /web/{token}/ API — "شماره مجازی")
# ══════════════════════════════════════════════════════════════════════

async def get_panel_balance() -> int:
    """Fetch the Ozvinoo panel balance.

    Returns the balance as an integer, or 0 if the request fails.
    """
    url = f"https://api.ozvinoo.xyz/web/{TOKEN}/get-balance"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if isinstance(data, dict) and "balance" in data:
                    return int(data["balance"])
                elif isinstance(data, (int, float, str)):
                    return int(data)
                return 0
    except Exception as e:
        logger.error(f"Error fetching Ozvinoo balance: {e}")
        return 0


async def get_applications() -> Optional[list[dict]]:
    """Fetch all available services (applications) from the Ozvinoo API.

    Returns:
        List of dicts: {"id", "code", "title", "name", ...} or ``None``.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.ozvinoo.xyz/web/{TOKEN}/applications"
            async with session.get(url) as resp:
                raw = await resp.text()
                logger.warning(f"RAW APPLICATIONS RESPONSE: {raw[:1000]}")
                data = json.loads(raw)

        if isinstance(data, dict):
            apps = [app for app in data.values() if isinstance(app, dict)]
        elif isinstance(data, list):
            apps = [app for app in data if isinstance(app, dict)]
        else:
            return None

        app_list = []
        for app in apps:
            service_id = app.get("id")
            code = app.get("code", "نامشخص")
            title = app.get("title") or app.get("name") or code
            app_list.append({
                "service_id": service_id,
                "code": code,
                "name": code,
                "title": title,
            })
        return app_list or None
    except Exception as exc:
        logger.error(f"FATAL ERROR in get_applications: {exc}", exc_info=True)
        return None


async def get_telegram_countries(service_id) -> Optional[list[dict]]:
    """Fetch countries for a given service and apply the live profit margin.

    ``service_id`` may be a numeric id (e.g. 1) or a provider code
    (e.g. "tg", "change", "imo", "tg_noreport") — it is injected into the
    appropriate API URL.

    For ``tg_noreport`` (non-report Telegram numbers), a special V2 API
    endpoint is used instead of the standard V1 get-prices path.
    """
    if service_id == "tg_noreport":
        return await get_tg_noreport_countries()
    return await get_countries(service_id)


async def get_tg_noreport_countries() -> Optional[list[dict]]:
    """Fetch non-report Telegram numbers using the V2 API endpoint.

    Uses: POST https://api.ozvinoo.xyz/telegram-numbers/numbers/
    with Bearer token and ``none_report: True`` JSON body.

    Note: ``aiohttp`` does not support ``json=`` on ``.get()``,
    so we use ``.post()`` which does.
    """
    try:
        from database.db import get_profit_margin
        margin = await get_profit_margin(config.ACCOUNT_PROFIT_MARGIN_PERCENT) / 100

        url = "https://api.ozvinoo.xyz/telegram-numbers/numbers/"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {"none_report": True}

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # POST is required here — aiohttp .get() does not accept json=
            async with session.post(url, headers=headers, json=payload) as resp:
                raw = await resp.text()
                logger.warning(f"RAW TG NOREPORT RESPONSE [{resp.status}]: {raw[:1000]}")
                if resp.status != 200:
                    logger.error(f"V2 API returned HTTP {resp.status}: {raw[:500]}")
                    return None
                data = json.loads(raw)

        result = []
        if data.get("status") and "data" in data:
            for item in data["data"]:
                if not isinstance(item, dict):
                    continue
                price = int(item.get("price", 0))
                stock_raw = item.get("count", "")
                if isinstance(stock_raw, bool):
                    in_stock = stock_raw
                else:
                    in_stock = _parse_in_stock(stock_raw)

                result.append({
                    "country": item.get("country", "نامشخص"),
                    "range": str(item.get("range", "1")),
                    "base_price": price,
                    "final_price": int(price + (price * margin)),
                    "in_stock": in_stock,
                })
        return result
    except Exception as exc:
        logger.error(f"FATAL ERROR in get_tg_noreport_countries: {exc}", exc_info=True)
        return None


async def get_countries(service_id) -> Optional[list[dict]]:
    """Fetch countries for a service and apply the live profit margin.

    STRICT ERROR HANDLING build:
      * Every HTTP response is read as RAW TEXT and logged BEFORE parsing,
        so a non-JSON body (e.g. an HTML error page that would make
        ``resp.json()`` raise ``aiohttp.ContentTypeError``) is visible in
        the logs instead of crashing silently.
      * Any exception is logged with the full traceback (``exc_info=True``)
        and turned into a ``None`` return so the caller can react.

    Returns:
        List of dicts: {"country", "range", "service_id", "base_price",
                        "final_price", "in_stock"} or ``None`` on failure.
    """
    try:
        # Dynamic profit margin — live from DB, fallback to config.
        from database.db import get_profit_margin
        margin = await get_profit_margin(config.ACCOUNT_PROFIT_MARGIN_PERCENT) / 100

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url_prices = f"https://api.ozvinoo.xyz/web/{TOKEN}/get-prices/{service_id}"
            async with session.get(url_prices) as resp:
                raw_prices = await resp.text()
                logger.warning(f"RAW PRICES RESPONSE: {raw_prices[:1000]}")
                countries_data = json.loads(raw_prices)

        result = []
        if isinstance(countries_data, list):
            for item in countries_data:
                if not isinstance(item, dict):
                    continue
                base_price = int(item.get("price", 0))
                # Use 'range' field for callback_data (short prefix code)
                # Falls back to country name if range is missing
                country_range = str(item.get("range", item.get("country", "1")))
                result.append({
                    "country": item.get("country", "نامشخص"),
                    "range": country_range,
                    "service_id": service_id,
                    "base_price": base_price,
                    "final_price": int(base_price + (base_price * margin)),
                    "in_stock": _parse_in_stock(item.get("count")),
                })
        return result
    except Exception as exc:
        logger.error(f"FATAL ERROR in get_countries: {exc}", exc_info=True)
        return None


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
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
