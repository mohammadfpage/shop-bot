"""
Ozvinoo (Callinoo V2) API service for virtual numbers (شماره مجازی).

Base URL: https://api.ozvinoo.xyz/

API Endpoints (V2):
    GET  /telegram-numbers/numbers/         → List countries with prices
    POST /telegram-numbers/numbers/         → Buy number (body: {"country": id})
    GET  /telegram-numbers/number-services/ → Get code for ordered number
    POST /telegram-numbers/number-services/ → Logout from number

Dynamic Profit Margin:
    Final_Price = Base_Price + (Base_Price × (Margin / 100))
    Margin is fetched from config.ACCOUNT_PROFIT_MARGIN_PERCENT (default 30%).
"""

import json
import logging
import time
from typing import Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)

# ─── Cache (5-minute TTL) ────────────────────────────────────────
_cache: dict = {}
_cache_ts: float = 0.0
_CACHE_TTL: float = 300.0  # 5 minutes


def _is_cache_valid() -> bool:
    return (time.time() - _cache_ts) < _CACHE_TTL


# ─── Low-level HTTP helper ─────────────────────────────────────────

async def _parse_response(endpoint: str, resp: aiohttp.ClientResponse) -> Optional[dict]:
    """Read the raw response body, log it on failure, and parse JSON.

    The raw ``resp.text()`` is always logged for HTTP error statuses so
    authentication / connectivity issues can be debugged.
    """
    body = await resp.text()

    if resp.status >= 400:
        logger.error(
            "New API %s returned HTTP %s — body: %s",
            endpoint, resp.status, body,
        )

    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        logger.warning("New API %s returned non-JSON body: %s", endpoint, body)
        return None

    if not isinstance(data, dict):
        logger.warning("New API %s returned non-dict JSON: %r", endpoint, data)
        return None

    return data


async def _new_api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> Optional[dict]:
    """Request to the new /telegram-*/ V2 API.

    The V2 API rejects the key when sent only as ``Authorization:
    Token ...`` / ``Bearer ...``. The key is therefore sent through
    several compatible channels at once — an ``apikey`` header, a Bearer
    token, and ``token`` / ``apikey`` query parameters — so whichever
    scheme the server expects is honoured.
    """
    token = config.OZVINOO_API_KEY
    url = f"{config.OZVINOO_BASE_URL.rstrip('/')}{endpoint}"
    headers = {
        "apikey": token,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    query = dict(params or {})
    query.setdefault("token", token)
    query.setdefault("apikey", token)

    try:
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(
                    url,
                    params=query,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    return await _parse_response(endpoint, resp)
            else:
                async with session.post(
                    url,
                    params=query,
                    json=json_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    return await _parse_response(endpoint, resp)
    except Exception as exc:
        logger.error("New API request failed for %s: %s", endpoint, exc)
        return None


# ══════════════════════════════════════════════════════════════════════
#  VIRTUAL NUMBERS (New API — for "شماره مجازی" section)
# ══════════════════════════════════════════════════════════════════════

async def get_virtual_number_countries() -> list[dict]:
    """Fetch available countries for virtual numbers.

    Endpoint: GET /telegram-numbers/numbers/
    Response: {"status": true, "data": [{"country": "US 🇺🇸", "price": 3000, ...}]}

    Returns:
        List of country dicts with price and availability info.
    """
    if _cache.get("vn_countries") and _is_cache_valid():
        return _cache["vn_countries"]

    data = await _new_api_request("/telegram-numbers/numbers/")
    if not data:
        return _cache.get("vn_countries", [])

    if not data.get("status"):
        logger.warning("Virtual numbers countries error: %s", data.get("message"))
        return _cache.get("vn_countries", [])

    countries = data.get("data", [])
    margin = config.ACCOUNT_PROFIT_MARGIN_PERCENT / 100

    # Apply profit margin to prices
    for c in countries:
        base = int(c.get("price", 0))
        c["base_price"] = base
        c["final_price"] = int(base + (base * margin))
        c["in_stock"] = "موجود" in str(c.get("count", ""))

    _cache["vn_countries"] = countries
    global _cache_ts
    _cache_ts = time.time()

    return countries


async def buy_virtual_number(country_id: int) -> Optional[dict]:
    """Purchase a virtual number for a given country.

    Endpoint: POST /telegram-numbers/numbers/
    Body: {"country": <country_id>}
    Response: {"status": true, "data": {"number": "1234567890", "order_id": 987654321, ...}}

    Returns:
        Dict with order details or None/ error dict.
    """
    data = await _new_api_request(
        "/telegram-numbers/numbers/",
        method="POST",
        json_body={"country": country_id},
    )

    if not data:
        return {"success": False, "error_msg": "خطا در اتصال به سرور"}

    if data.get("status"):
        return {"success": True, **data.get("data", {})}

    return {
        "success": False,
        "error_code": data.get("message", "unknown"),
        "error_msg": data.get("message", "خطای ناشناخته"),
    }


async def get_number_code(order_id: int) -> Optional[dict]:
    """Get the SMS verification code for an ordered number.

    Endpoint: GET /telegram-numbers/number-services/?order_id={order_id}
    Response (ready): {"status": true, "status_code": 200, "data": {"code": "12345", ...}}
    Response (waiting): {"status": false, "status_code": 202, "message": "Waiting for code"}

    Returns:
        Dict with code info. Check 'is_ready' key.
    """
    data = await _new_api_request(
        "/telegram-numbers/number-services/",
        params={"order_id": order_id},
    )

    if not data:
        return {"is_ready": False, "error_msg": "خطا در دریافت کد"}

    status_code = data.get("status_code", 0)

    if data.get("status") and status_code == 200:
        d = data.get("data", {})
        return {
            "is_ready": True,
            "code": d.get("code", ""),
            "number": d.get("number", ""),
            "country": d.get("country", ""),
            "order_id": d.get("order_id", order_id),
        }

    # Still waiting or error
    return {
        "is_ready": False,
        "error_msg": data.get("message", "در انتظار دریافت کد..."),
        "status_code": status_code,
    }


async def logout_number(order_id: int) -> bool:
    """Logout from a number's Telegram account.

    Endpoint: POST /telegram-numbers/number-services/
    Body: {"order_id": <order_id>}
    """
    data = await _new_api_request(
        "/telegram-numbers/number-services/",
        method="POST",
        json_body={"order_id": order_id},
    )
    return data.get("status", False) if data else False


# ══════════════════════════════════════════════════════════════════════
#  CACHE INVALIDATION
# ══════════════════════════════════════════════════════════════════════

def invalidate_cache() -> None:
    """Clear all cached API responses."""
    global _cache, _cache_ts
    _cache.clear()
    _cache_ts = 0.0
    logger.info("Ozvinoo API cache invalidated.")
