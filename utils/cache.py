"""
In-memory rate cache with a background fetcher task.

Usage:
    cache = RateCache()
    # Start background loop (called from FastAPI lifespan)
    asyncio.create_task(cache.start(interval=300))
    # Read cached data (called from handlers)
    data = cache.get_data()

The fetcher runs every `interval` seconds, calls the BrsApi, and stores
the result in memory.  If the API fails, the stale cache is kept so that
users always see *something* rather than an error.
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cached payload plus the timestamp when it was stored."""
    data: Any = None
    updated_at: float = 0.0


class RateCache:
    """Thread-safe (single-event-loop) in-memory cache for exchange rates.

    Attributes:
        entry   – the current cache payload (full BrsApi JSON).
        _task   – reference to the running background asyncio task.
    """

    def __init__(self) -> None:
        self.entry: CacheEntry = CacheEntry()
        self._task: Optional[asyncio.Task] = None

    # ── Public API ────────────────────────────────────────────────────

    def get_data(self) -> Optional[dict]:
        """Return the cached BrsApi payload, or *None* if nothing is cached yet."""
        return self.entry.data

    def is_ready(self) -> bool:
        """Return *True* after the very first successful fetch."""
        return self.entry.data is not None

    def last_updated_str(self) -> str:
        """Human-friendly Persian string: 'آخرین بروزرسانی: ۳ دقیقه پیش'."""
        if not self.is_ready():
            return "—"
        seconds = int(time.time() - self.entry.updated_at)
        if seconds < 60:
            return "چند ثانیه پیش"
        minutes = seconds // 60
        return f"{minutes} دقیقه پیش"

    # ── Background loop ───────────────────────────────────────────────

    async def start(self, interval: float = 300.0) -> None:
        """Launch the background fetching loop.

        Args:
            interval: seconds between fetches (default 300 = 5 min).
        """
        logger.info("RateCache background loop starting (interval=%ss) …", interval)
        # Run the first fetch immediately so data is available ASAP.
        await self._fetch()
        while True:
            await asyncio.sleep(interval)
            await self._fetch()

    def stop(self) -> None:
        """Cancel the background task (called on shutdown)."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("RateCache background task cancelled.")

    # ── Internal ──────────────────────────────────────────────────────

    async def _fetch(self) -> None:
        """Fetch the BrsApi and update the cache.  Failures are swallowed."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.BRS_API_URL,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.entry = CacheEntry(
                            data=data,
                            updated_at=time.time(),
                        )
                        logger.info("RateCache updated successfully.")
                    else:
                        logger.warning("BrsApi returned HTTP %s", resp.status)
        except Exception as exc:
            logger.warning("RateCache fetch failed (keeping old data): %s", exc)


# ── Singleton (importable by every module) ─────────────────────────
rate_cache = RateCache()
