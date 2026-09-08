"""Zarinpal REST v4 payment gateway integration."""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)

REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
START_PAY_URL = "https://www.zarinpal.com/pg/StartPay/"


@dataclass
class PaymentRequestResult:
    success: bool
    authority: Optional[str] = None
    start_pay_url: Optional[str] = None
    message: str = ""
    code: Optional[int] = None


@dataclass
class PaymentVerifyResult:
    success: bool
    ref_id: Optional[str] = None
    message: str = ""
    code: Optional[int] = None
    amount_irt: Optional[int] = None


def _as_int(value: Any) -> Optional[int]:
    """Convert a numeric API value to ``int``.

    Accepts int, float, and numeric strings such as ``"28500000"``
    or ``"28500000.0"``.  Returns ``None`` only when the value is
    truly non-numeric or represents a non-integer fraction.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("،", "").strip())
    except (TypeError, ValueError):
        return None
    if not number.is_integer():
        return None
    return int(number)


def _response_data(response: dict[str, Any]) -> dict[str, Any]:
    """Return the v4 data object, with compatibility for flat responses."""
    data = response.get("data")
    return data if isinstance(data, dict) else response


def _response_message(response: dict[str, Any], data: dict[str, Any], code: Optional[int]) -> str:
    errors = response.get("errors")
    if isinstance(errors, dict):
        error_message = errors.get("message")
        if error_message:
            return str(error_message)
    message = data.get("message") or response.get("message")
    return str(message) if message else _zarinpal_error(code)


async def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST JSON to Zarinpal and return its decoded response."""
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            url,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        ) as response:
            return await response.json(content_type=None)


async def request_payment(
    amount_irt: int,
    description: str,
    user_email: str = "",
    user_phone: str = "",
) -> PaymentRequestResult:
    """Create a Zarinpal v4 payment using the amount directly in Tomans."""
    if not isinstance(amount_irt, int) or isinstance(amount_irt, bool) or amount_irt <= 0:
        return PaymentRequestResult(False, message="Invalid payment amount")

    payload: dict[str, Any] = {
        "merchant_id": config.ZARINPAL_MERCHANT_ID,
        "amount": amount_irt,
        "currency": "IRT",
        "description": description,
        "callback_url": config.ZARINPAL_CALLBACK_URL,
    }
    if user_email:
        payload["email"] = user_email
    if user_phone:
        payload["mobile"] = user_phone

    try:
        response = await _post_json(REQUEST_URL, payload)
        data = _response_data(response)
        code = _as_int(data.get("code", response.get("code")))
        if code == 100:
            authority = str(data.get("authority", "")).strip()
            if authority:
                logger.info("Zarinpal v4 request succeeded")
                return PaymentRequestResult(
                    success=True,
                    authority=authority,
                    start_pay_url=f"{START_PAY_URL}{authority}",
                    code=code,
                )

        message = _response_message(response, data, code)
        logger.warning("Zarinpal v4 request failed: %s (code=%s)", message, code)
        return PaymentRequestResult(False, message=message, code=code)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.error("Zarinpal v4 request error: %s", exc)
        return PaymentRequestResult(False, message="Payment gateway connection failed")


async def verify_payment(authority: str, amount_irt: int) -> PaymentVerifyResult:
    """Verify a payment with the exact persisted IRT amount."""
    if not authority or not isinstance(amount_irt, int) or isinstance(amount_irt, bool):
        return PaymentVerifyResult(False, message="Invalid payment verification data")

    payload = {
        "merchant_id": config.ZARINPAL_MERCHANT_ID,
        "amount": amount_irt,
        "currency": "IRT",
        "authority": authority,
    }

    try:
        response = await _post_json(VERIFY_URL, payload)
        data = _response_data(response)
        code = _as_int(data.get("code", response.get("code")))
        returned_amount = _as_int(data.get("amount"))
        ref_id = str(data.get("ref_id", "")).strip() or None

        if code in (100, 101):
            logger.info("Zarinpal v4 verification returned code %s", code)
            return PaymentVerifyResult(
                success=True,
                ref_id=ref_id,
                code=code,
                amount_irt=returned_amount,
            )

        message = _response_message(response, data, code)
        logger.warning("Zarinpal v4 verification failed: %s (code=%s)", message, code)
        return PaymentVerifyResult(False, message=message, code=code, amount_irt=returned_amount)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.error("Zarinpal v4 verification error: %s", exc)
        return PaymentVerifyResult(False, message="Payment gateway connection failed")


def _zarinpal_error(code: Optional[int]) -> str:
    errors = {
        -1: "پارامترهای ناقص",
        -2: "مرچنت‌کد نامعتبر است",
        -3: "مبلغ نامعتبر (حداقل ۱۰۰ تومان)",
        -4: "IP غیرمجاز",
        -5: "مرچنت فعال نیست",
        -10: "کاربر پرداخت را تأیید نکرد",
        -11: "پرداخت توسط کاربر لغو شد",
        -12: "خطا در درخواست پرداخت",
        -14: "درخواست پرداخت یافت نشد",
        -15: "تأیید پرداخت ممکن نیست",
    }
    return errors.get(code, f"خطای نامشخص (کد: {code})")
