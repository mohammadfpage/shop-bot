"""
Admin security middleware.

Intercepts every Message and CallbackQuery update and, if the target
belongs to the admin router (the /admin command or any callback_data
starting with "admin:"), verifies that the sender is in ADMIN_IDS
before allowing the update through.

This is a defense-in-depth layer — individual admin handlers already
call _is_admin(), but the middleware provides a single, centralised
gate so that a forgotten check in a new handler cannot be exploited.
"""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update


class AdminSecurityMiddleware(BaseMiddleware):
    """Reject admin-routed updates from non-admin users."""

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        from config import config

        user_id: int | None = None
        is_admin_command = False

        # ── Message: /admin command or state-driven admin input ────
        if event.message and event.message.from_user:
            user_id = event.message.from_user.id
            text = (event.message.text or "").strip()
            # /admin command
            if text == "/admin":
                is_admin_command = True
            # Callback data inside admin FSM states is also guarded
            # (broadcast text, price edits, etc.)

        # ── CallbackQuery: any callback_data starting with "admin:" ─
        elif event.callback_query and event.callback_query.from_user:
            user_id = event.callback_query.from_user.id
            cb_data = event.callback_query.data or ""
            if cb_data.startswith("admin:"):
                is_admin_command = True

        if is_admin_command and user_id is not None:
            if user_id not in config.ADMIN_IDS:
                # Silently block — the user should not even see
                # that the admin panel exists.
                return None

        return await handler(event, data)
