"""
Shiznumber API service for virtual numbers (شماره مجازی).

Replaces the old Ozvinoo API with the new Shiznumber REST API.

Authentication: X-API-KEY header
Services are identified by slugs (e.g. 'telegram', 'whatsapp')
Numbers are identified by a unique `id` returned from the numbers list.

Endpoints:
    GET  /api/services/{slug}/numbers        → list available countries/numbers
    POST /api/order/{item_id}                → purchase a virtual number
    GET  /api/code/{order_id}                → fetch the SMS verification code
    GET  /api/balance                        → fetch panel balance
"""

import logging
from typing import Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.shiznumber.com/api"


def _get_api_key() -> str:
    """Get the Shiznumber API key from config."""
    return getattr(config, "SHIZ_API_KEY", "")


def _get_headers() -> dict:
    """Build request headers with API key authentication."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-KEY": _get_api_key(),
    }


# ══════════════════════════════════════════════════════════════════════
#  VIRTUAL NUMBERS (شماره مجازی)
# ══════════════════════════════════════════════════════════════════════

async def get_service_numbers(slug: str) -> list[dict]:
    """GET /services/{slug}/numbers — fetch available countries for a service.

    Applies a 30% profit margin on top of the base price.

    Returns:
        List of dicts with keys:
            id, country_fa, count, base_price, final_price, in_stock
    """
    url = f"{BASE_URL}/services/{slug}/numbers"
    margin = 1.30  # 30% profit margin
    result = []

    try:
        headers = _get_headers()
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        for item in data:
                            price = int(item.get("price", 0))
                            country_data = item.get("country", {})
                            count = int(item.get("count", 0))
                            result.append({
                                "id": str(item.get("id")),
                                "country_fa": country_data.get("fa_name", "نامشخص"),
                                "country_en": country_data.get("en_name", "Unknown"),
                                "count": count,
                                "base_price": price,
                                "final_price": int(price * margin),
                                "in_stock": count > 0,
                            })
                else:
                    logger.warning(
                        "Shiznumber GET %s returned HTTP %s", slug, resp.status
                    )
    except Exception as e:
        logger.error("Shiznumber API Error (get_service_numbers): %s", e)

    return result


async def buy_virtual_number(item_id: str) -> Optional[dict]:
    """POST /order/{item_id} — purchase a virtual number by its unique item ID.

    The item_id is the unique `id` returned from get_service_numbers().

    Returns:
        Raw JSON dict with 'order_id', 'number', 'price', etc.
        Or {'error': '...'} on failure. None on connection errors.
    """
    url = f"{BASE_URL}/order/{item_id}"
    try:
        headers = _get_headers()
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers) as resp:
                return await resp.json()
    except Exception as exc:
        logger.error("Shiznumber buy failed (item_id=%s): %s", item_id, exc)
        return None


async def get_number_code(order_id: str) -> Optional[dict]:
    """GET /code/{order_id} — fetch the SMS verification code for an ordered number.

    Returns:
        Raw JSON dict with 'code' if ready,
        or {'status': 'waiting', ...} if still waiting.
        None on connection errors.
    """
    url = f"{BASE_URL}/code/{order_id}"
    try:
        headers = _get_headers()
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
    except Exception as exc:
        logger.error("Shiznumber getCode failed (order_id=%s): %s", order_id, exc)
        return None


async def get_panel_balance() -> int:
    """GET /balance — fetch the Shiznumber panel balance.

    Returns the balance as an integer, or 0 if the request fails.
    """
    url = f"{BASE_URL}/balance"
    try:
        headers = _get_headers()
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                if isinstance(data, dict) and "balance" in data:
                    return int(data["balance"])
                elif isinstance(data, (int, float, str)):
                    return int(data)
                return 0
    except Exception as e:
        logger.error("Error fetching Shiznumber balance: %s", e)
        return 0
