"""
Ozvinoo (Callinoo) API service for virtual numbers & Telegram services.

Base URL: https://api.ozvinoo.xyz/
Authentication: Token-based (API key passed in URL path or Authorization header)

API Endpoints (from OpenAPI spec):
    ── Old API (token in URL path) ─────────────────────────────────
    POST /web/{token}/get-balance          → Check wallet balance
    GET  /web/{token}/applications         → List available services
    GET  /web/{token}/get-prices/{svc_id}  → Prices per country for a service
    GET  /web/{token}/getNumber/{svc_id}/{country} → Buy a virtual number
    GET  /web/{token}/getCode/{request_id} → Get SMS verification code
    POST /web/{token}/logout/{request_id}  → Logout from the account

    ── New API (token in Authorization header) ──────────────────────
    GET  /telegram-numbers/numbers/         → List countries with prices
    POST /telegram-numbers/numbers/         → Buy number (body: {"country": id})
    GET  /telegram-numbers/number-services/ → Get code for ordered number
    POST /telegram-numbers/number-services/ → Logout from number

    GET  /telegram-services/stars/          → List stars packages
    POST /telegram-services/stars/          → Buy stars (body: {"count", "username"})
    GET  /telegram-services/premium/        → List premium packages
    POST /telegram-services/premium/        → Buy premium (body: {"id", "username"})
    GET  /telegram-services/status/         → Check order status (params: code, service)

Dynamic Profit Margin:
    Final_Price = Base_Price + (Base_Price × (Margin / 100))
    Margin is fetched from config.ACCOUNT_PROFIT_MARGIN_PERCENT (default 30%).
"""

import logging
import time
from typing import Optional
from dataclasses import dataclass, field

import aiohttp

from config import config

logger = logging.getLogger(__name__)

# ─── Cache (5-minute TTL) ────────────────────────────────────────
_cache: dict = {}
_cache_ts: float = 0.0
_CACHE_TTL: float = 300.0  # 5 minutes


def _is_cache_valid() -> bool:
    return (time.time() - _cache_ts) < _CACHE_TTL


# ─── Data classes ────────────────────────────────────────────────────

@dataclass
class OzvinooService:
    """A service category (e.g., Telegram VIP panel)."""
    service_id: int
    name: str
    code: str = ""


@dataclass
class CountryPrice:
    """Price & availability for a specific country within a service."""
    country: str
    base_price_toman: int
    final_price_toman: int  # after profit margin
    range_prefix: str
    in_stock: bool
    quality_info: str = ""


@dataclass
class VirtualNumberOrder:
    """Result of purchasing a virtual number."""
    number: str
    request_id: int
    base_price_toman: int
    final_price_toman: int
    country: str
    service_name: str
    quality_info: str = ""


@dataclass
class VerificationCode:
    """Result of fetching an SMS verification code."""
    request_id: int
    number: str
    country: str
    code: str
    is_ready: bool
    error_msg: str = ""


# ─── Low-level HTTP helper ─────────────────────────────────────────

async def _old_api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[dict] = None,
) -> Optional[dict]:
    """Request to the old /web/{token}/... API (token in URL path)."""
    token = config.OZVINOO_API_KEY
    url = f"{config.OZVINOO_BASE_URL.rstrip('/')}/web/{token}/{endpoint.lstrip('/')}"

    try:
        async with aiohttp.ClientSession() as session:
            req_method = session.get if method.upper() == "GET" else session.post
            async with req_method(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200:
                    return data
                logger.warning("Old API %s returned %s: %s", endpoint, resp.status, data)
                return data  # Return even error responses for caller to handle
    except Exception as exc:
        logger.error("Old API request failed for %s: %s", endpoint, exc)
        return None


async def _new_api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> Optional[dict]:
    """Request to the new /telegram-*/ API (token in Authorization header)."""
    token = config.OZVINOO_API_KEY
    url = f"{config.OZVINOO_BASE_URL.rstrip('/')}{endpoint}"
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(url, params=params, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    data = await resp.json(content_type=None)
                    return data
            else:
                async with session.post(url, json=json_body, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    data = await resp.json(content_type=None)
                    return data
    except Exception as exc:
        logger.error("New API request failed for %s: %s", endpoint, exc)
        return None


# ══════════════════════════════════════════════════════════════════════
#  WALLET
# ══════════════════════════════════════════════════════════════════════

async def get_balance() -> Optional[int]:
    """Check the API wallet balance in Toman.

    Returns:
        Balance in Toman, or None on error.
    """
    data = await _old_api_request("get-balance")
    if not data:
        return None
    if "balance" in data:
        return int(data["balance"])
    if data.get("success") is False:
        logger.warning("Ozvinoo balance check failed: %s", data.get("error_msg"))
    return None


# ══════════════════════════════════════════════════════════════════════
#  SERVICES (Old API — for "خرید اکانت" section)
# ══════════════════════════════════════════════════════════════════════

async def get_services() -> list[OzvinooService]:
    """Fetch available service categories from the old API.

    Endpoint: GET /web/{token}/applications
    Response: {"0": {"id": "1", "title": "Telegram Vip panel", "code": "tg"}, ...}

    Returns:
        List of OzvinooService objects.
    """
    if _cache.get("services") and _is_cache_valid():
        return _cache["services"]

    data = await _old_api_request("applications")
    if not data or not isinstance(data, dict):
        return _cache.get("services", [])

    # Error check
    if data.get("success") is False:
        logger.warning("Ozvinoo applications error: %s", data.get("error_msg"))
        return _cache.get("services", [])

    services = []
    for key, item in data.items():
        if isinstance(item, dict):
            services.append(OzvinooService(
                service_id=int(item.get("id", 0)),
                name=item.get("title", "نامشخص"),
                code=item.get("code", ""),
            ))

    _cache["services"] = services
    _cache_ts_val = time.time()
    global _cache_ts
    _cache_ts = _cache_ts_val

    logger.info("Fetched %d services from Ozvinoo", len(services))
    return services


async def get_country_prices(service_id: int) -> list[CountryPrice]:
    """Fetch country-level pricing for a given service.

    Endpoint: GET /web/{token}/get-prices/{service_id}
    Response: [{"country": "لهستان 🇵🇱", "price": 12000, "range": 48, "count": "✅ موجود"}]

    Returns:
        List of CountryPrice with profit margin applied.
    """
    cache_key = f"prices_{service_id}"
    if _cache.get(cache_key) and _is_cache_valid():
        return _cache[cache_key]

    data = await _old_api_request(f"get-prices/{service_id}")
    if not data or not isinstance(data, list):
        return _cache.get(cache_key, [])

    margin = config.ACCOUNT_PROFIT_MARGIN_PERCENT / 100
    countries = []

    for item in data:
        if not isinstance(item, dict):
            continue
        base_price = int(item.get("price", 0))
        final_price = int(base_price + (base_price * margin))
        in_stock = "موجود" in str(item.get("count", ""))

        countries.append(CountryPrice(
            country=item.get("country", "نامشخص"),
            base_price_toman=base_price,
            final_price_toman=final_price,
            range_prefix=str(item.get("range", "")),
            in_stock=in_stock,
            quality_info=item.get("quality", ""),
        ))

    _cache[cache_key] = countries
    global _cache_ts
    _cache_ts = time.time()

    return countries


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
#  PURCHASE (Old API — for "خرید اکانت" section)
# ══════════════════════════════════════════════════════════════════════

async def purchase_number(
    service_id: int,
    country: str,
) -> Optional[dict]:
    """Purchase a virtual number via the old API.

    Endpoint: GET /web/{token}/getNumber/{service_id}/{country}
    Response: {"number": "+48459084705", "request_id": 242004842, "price": 12000, ...}

    Returns:
        Dict with purchase details or error dict.
    """
    data = await _old_api_request(f"getNumber/{service_id}/{country}")

    if not data:
        return {"success": False, "error_msg": "خطا در اتصال به سرور"}

    if data.get("error_code"):
        return {
            "success": False,
            "error_code": data["error_code"],
            "error_msg": data.get("error_msg", "خطای ناشناخته"),
        }

    # Success
    base_price = int(data.get("price", 0))
    margin = config.ACCOUNT_PROFIT_MARGIN_PERCENT / 100
    final_price = int(base_price + (base_price * margin))

    return {
        "success": True,
        "number": data.get("number", ""),
        "request_id": data.get("request_id", 0),
        "base_price_toman": base_price,
        "final_price_toman": final_price,
        "country": data.get("countery", data.get("country", "")),
        "service": data.get("service", ""),
        "quality": data.get("quality", ""),
    }


async def get_verification_code(request_id: int) -> Optional[dict]:
    """Get the SMS verification code via the old API.

    Endpoint: GET /web/{token}/getCode/{request_id}
    Response (ready): {"code": "80012", "number": "+48459084705", ...}
    Response (waiting): {"error_code": "wait_code", "error_msg": "Still waiting..."}

    Returns:
        Dict with code info. Check 'is_ready' key.
    """
    data = await _old_api_request(f"getCode/{request_id}")

    if not data:
        return {"is_ready": False, "error_msg": "خطا در دریافت کد"}

    error_code = data.get("error_code", "")

    if error_code == "wait_code":
        return {
            "is_ready": False,
            "error_msg": "هنوز در انتظار دریافت کد...",
            "number": data.get("number", ""),
        }

    if error_code:
        return {
            "is_ready": False,
            "error_code": error_code,
            "error_msg": data.get("error_msg", "خطای ناشناخته"),
        }

    # Success — code received
    return {
        "is_ready": True,
        "code": data.get("code", ""),
        "number": data.get("number", ""),
        "country": data.get("country", ""),
        "request_id": data.get("request_id", request_id),
    }


async def logout_old_api(request_id: int) -> bool:
    """Logout from an old-API number order."""
    data = await _old_api_request(f"logout/{request_id}")
    if data and data.get("success"):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════
#  TELEGRAM STARS & PREMIUM (New API)
# ══════════════════════════════════════════════════════════════════════

async def get_stars_packages() -> list[dict]:
    """Fetch available stars packages.

    Endpoint: GET /telegram-services/stars/
    """
    data = await _new_api_request("/telegram-services/stars/")
    if not data or not data.get("status"):
        return []
    return data.get("data", [])


async def buy_stars(count: int, username: str) -> Optional[dict]:
    """Buy stars package.

    Endpoint: POST /telegram-services/stars/
    Body: {"count": <int>, "username": "<str>"}
    """
    return await _new_api_request(
        "/telegram-services/stars/",
        method="POST",
        json_body={"count": count, "username": username},
    )


async def get_premium_packages() -> list[dict]:
    """Fetch available premium packages.

    Endpoint: GET /telegram-services/premium/
    """
    data = await _new_api_request("/telegram-services/premium/")
    if not data or not data.get("status"):
        return []
    return data.get("data", [])


async def buy_premium(package_id: int, username: str) -> Optional[dict]:
    """Buy premium package.

    Endpoint: POST /telegram-services/premium/
    Body: {"id": <int>, "username": "<str>"}
    """
    return await _new_api_request(
        "/telegram-services/premium/",
        method="POST",
        json_body={"id": package_id, "username": username},
    )


async def check_order_status(code: int, service: str) -> Optional[dict]:
    """Check order status.

    Endpoint: GET /telegram-services/status/?code={code}&service={service}
    service must be 'stars' or 'premium'
    """
    return await _new_api_request(
        "/telegram-services/status/",
        params={"code": code, "service": service},
    )


# ══════════════════════════════════════════════════════════════════════
#  CACHE INVALIDATION
# ══════════════════════════════════════════════════════════════════════

def invalidate_cache() -> None:
    """Clear all cached API responses."""
    global _cache, _cache_ts
    _cache.clear()
    _cache_ts = 0.0
    logger.info("Ozvinoo API cache invalidated.")
