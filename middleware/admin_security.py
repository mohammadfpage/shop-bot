"""
Admin security middleware.

Intercepts every Message and CallbackQuery update and, if the target
belongs to the admin router (the /admin command or any callback_data
starting with "admin:"), verifies that the sender is in ADMIN_IDS
before allowing the update through.

This is a defense-in-depth layer — individual admin handlers already
use the IsAdmin filter, but the middleware provides a single, centralised
gate so that a forgotten check in a new handler cannot be exploited.
"""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

from filters import IsAdmin


class AdminSecurityMiddleware(BaseMiddleware):
    """Reject admin-routed updates from non-admin users."""

    # Reusable filter instance (stateless, safe to share)
    _is_admin = IsAdmin()

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        # Use the IsAdmin filter to check the sender
        result = await self._is_admin(event)

        if result is False:
            # Silently block — the user should not even see
            # that the admin panel exists.
            return None

        return await handler(event, data)
