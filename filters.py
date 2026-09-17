"""
Custom aiogram filters for role-based access control.

Usage in handlers:
    from filters import IsAdmin

    @router.message(Command("admin"), IsAdmin())
    async def cmd_admin(message: Message): ...

    @router.message(IsAdmin())
    async def admin_only_text(message: Message): ...

The filter reads from config.ADMIN_IDS, which is populated from the
ADMIN_IDS environment variable.

──────────────────────────────────────────────────────────────────
 HOW TO ADD YOUR TELEGRAM ID TO THE .env FILE
──────────────────────────────────────────────────────────────────

1.  Find your Telegram user ID:
      • Open @userinfobot in Telegram and click Start.
      • Copy the numeric ID it shows (e.g. 1652089506).

2.  Set the environment variable (pick ONE method):

    Option A — .env file (recommended for local development):
      Create a file named .env in the project root and add:
          ADMIN_IDS=1652089506

      For multiple admins, separate with commas:
          ADMIN_IDS=1652089506,7174138646

    Option B — Render.com Dashboard:
      Go to your Service → Environment tab → add:
          Key:   ADMIN_IDS
          Value: 1652089506

    Option C — Export in shell:
          export ADMIN_IDS="1652089506,7174138646"

3.  Restart the bot after changing the value.
──────────────────────────────────────────────────────────────────
"""

from typing import Any, Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from config import config


class IsAdmin(BaseFilter):
    """Pass only updates from users whose Telegram ID is in ADMIN_IDS.

    Works with both Message and CallbackQuery events.

    Examples:
        # On a single handler
        @router.message(Command("admin"), IsAdmin())
        async def cmd_admin(message: Message): ...

        # On all handlers in a router (via middleware — see admin_security.py)
    """

    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        **kwargs: Any,
    ) -> bool:
        """Return True if the sender is an admin, False otherwise."""
        user_id: int | None = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return False

        return user_id in config.ADMIN_IDS


class IsDynamicService(BaseFilter):
    """Pass only for reply-keyboard taps that match a virtual-number service.

    Resolves ``message.text`` against the live Shiznumber services map
    (``get_services_map()``). On a match the handler receives the
    resolved slug as an extra keyword argument ``shiz_slug``.

    The services map is cached for one hour, so this filter stays cheap
    after the first call. It never raises — a failed fetch simply means
    the message is not treated as a service tap.
    """

    async def __call__(
        self,
        message: Message,
        **kwargs: Any,
    ) -> Union[bool, dict[str, str]]:
        if not message or not message.text:
            return False
        try:
            from utils.shiznumber import get_services_map
            services_map = await get_services_map()
            slug = services_map.get(message.text)
        except Exception:
            return False
        if not slug:
            return False
        return {"shiz_slug": slug}
