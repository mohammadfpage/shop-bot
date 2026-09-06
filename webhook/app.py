"""
.. deprecated::
    This module is DEPRECATED. All functionality has been moved to ``bot.py``.

    The hybrid architecture in ``bot.py`` handles:
    • Telegram long-polling (no webhook needed)
    • FastAPI /verify endpoint for Zarinpal callbacks
    • Health/ping endpoints

    To run the bot:
        python bot.py

    This file is kept for backwards compatibility only and should not be
    used in new deployments.
"""

import warnings

warnings.warn(
    "webhook/app.py is deprecated. Use 'python bot.py' instead. "
    "All endpoints have been merged into bot.py.",
    DeprecationWarning,
    stacklevel=1,
)

# Re-export the app from bot.py so any stale references still resolve
from bot import app  # noqa: F401
