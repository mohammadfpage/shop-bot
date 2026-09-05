"""
Mock external API for fetching virtual phone numbers.

In production, replace the mock data with real API calls to your
virtual number provider (e.g., sms-activate, 5sim, etc.).
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Mock data ───────────────────────────────────────────────────────

_MOCK_NUMBERS: dict[str, list[str]] = {
    "iran": ["+989121234567", "+989359876543", "+989198765432"],
    "usa": ["+14155551234", "+12125559876", "+13105551111"],
    "uk": ["+447911123456", "+447700987654", "+447456123789"],
    "germany": ["+4915112345678", "+491769876543", "+491621234567"],
}


@dataclass
class VirtualNumberResult:
    success: bool
    number: Optional[str] = None
    country: Optional[str] = None
    message: str = ""


async def fetch_virtual_number(country: str) -> VirtualNumberResult:
    """Fetch and return a virtual number for the requested country.

    In production, this would call a real API with proper authentication.
    """
    country = country.lower()
    numbers = _MOCK_NUMBERS.get(country)
    if not numbers:
        return VirtualNumberResult(False, message=f"No numbers available for {country}")

    # Simulate API delay / latency
    number = random.choice(numbers)

    logger.info("Mock virtual number delivered: %s (%s)", number, country)
    return VirtualNumberResult(True, number=number, country=country)
