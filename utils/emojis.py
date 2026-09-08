"""
Telegram Premium custom emoji helper.

Provides a mapping from keyword → (fallback_emoji, premium_id) and a
helper function `get_pe()` that returns the plain fallback emoji.

Usage in f-strings:
    from utils.emojis import get_pe
    text = f"{get_pe('bot')} به ربات ما خوش آمدید {get_pe('sparkles')}"

Backward-compatible aliases:
    Old key names used across the codebase are preserved at the bottom
    of the dictionary so existing get_pe() calls continue to work.
"""

PREMIUM_EMOJIS: dict[str, tuple[str, str]] = {
    # ── User-provided comprehensive list ────────────────────────────
    "coin":             ("🪙", "5103047194965968549"),
    "bot_1":            ("🤖", "5985501934495207482"),
    "down":             ("⬇️", "5985492008825786028"),
    "lock":             ("🔒", "5983036958274752500"),
    "call_1":           ("📞", "5985623293091123400"),
    "card":             ("💳", "5987636254068444188"),
    "user_1":           ("👤", "5987666718271475727"),
    "user_2":           ("👤", "5987806579586502948"),
    "burger":           ("🍔", "5985359818322350039"),
    "shield_1":         ("🛡", "5985846012915224160"),
    "blue_heart":       ("💙", "6044141874606772596"),
    "anatomical_heart": ("🫀", "6044340078757548806"),
    "guitar":           ("🎸", "6043886276808019970"),
    "neutral":          ("😐", "6044001411996324261"),
    # ── User-provided premium emoji IDs ───────────────────────────
    "purse":            ("👛", "5316979275461573049"),
    "heart_simple":     ("❤️", "5316802593391916971"),
    "arrow_up":         ("⏫", "5318974936310627698"),
    "arrow_down":       ("⏬", "5316815985099946114"),
    "money_new":        ("💰", "5316711376876485361"),
    "pirate":           ("🏴‍☠️", "5316560584869690299"),
    "whale":            ("🐋", "5316709027529374004"),
    "light_blue_heart": ("🩵", "5319154611972486828"),
    "speak":            ("🗣️", "5316756151910546445"),
    "flag_us":          ("🇺🇸", "5913463998522592692"),
    "medal_gold":       ("🥇", "5440539497383087970"),
    "coin_new":         ("🪙", "5202064723922670546"),
    "dollar":           ("💵", "5201692367437974073"),
    "film":             ("🎬", None),  # no premium ID provided
    "camera":           ("📸", None),  # no premium ID provided
    "palette":          ("🎨", None),  # no premium ID provided
    "gear":             ("⚙️", "6046644354481655825"),
    "user_3":           ("👤", "6044381091400257627"),
    "check":            ("✅", "6044254523009012231"),
    "mouse":            ("🖱️", "6046496457282819707"),
    "call_2":           ("📞", "6044017041382314731"),
    "num1":             ("1⃣", "6044375357618917775"),
    "num2":             ("2⃣", "6044041827638579460"),
    "num3":             ("3⃣", "6044247981773820604"),
    "question":         ("❓", "6044177810598138618"),
    "white_circle":     ("⚪️", "5978813399105015315"),
    "store":            ("🏪", "5895288113537748673"),
    "key_lock":         ("🔐", "5897604269141398480"),
    "web_1":            ("🌐", "5343789187172670307"),
    "sparkles_1":       ("✨", "5316702099747123698"),
    "home":             ("🏠", "5839427953569567278"),
    "radio_check":      ("🔘✅", None),  # Broken ID - use fallback
    "black_circle":     ("⚫️", "5866017773976555711"),
    "bot_2":            ("🤖", "5803143039060808890"),
    "bot_3":            ("🤖", "5803385846446954748"),
    "music":            ("🎼", "5852687200512119580"),
    "planet":           ("🪐", "5980873643377299285"),
    "money_bag":        ("💰", "4972018703521547457"),
    "fire":             ("🔥", "4970075093381153851"),
    "exchange":         ("💱", "4972276324249896116"),
    "dizzy":            ("💫", "4972089334258729804"),
    "sparkles_2":       ("✨", "4972284317184033405"),
    "call_3":           ("📞", "4972085185320321969"),
    "user_4":           ("👤", "4972080847403352862"),
    "web_2":            ("🌐", "4970175617090717312"),
    "ghost":            ("👻", "4972507896001594223"),
    "star":             ("⭐️", "5469641199348363998"),
    "chart":            ("📊", "5938517659451658781"),
    "users":            ("👥", "5985401861757210746"),
    "face":             ("🥸", "6030858404048672093"),
    "yellow_circle":    ("🟡", "5805630641168977620"),
    "green_circle":     ("🟢", "5805539192725311487"),
    "cross":            ("❌", "5875208759176860365"),
    "ban":              ("🚫", "5872912021120357460"),
    "ticket":           ("🎫", "5418010521309815154"),
    "money_stack":      ("💰", "5287231198098117669"),
    "calendar":         ("🗓", "5030732809128379408"),
    "diamond":          ("💎", "5873058161677570714"),
    "wave":             ("👋", "5416004728632922564"),
    "shield_2":         ("🛡", "5197288647275071607"),
    "box":              ("📦", "5454175528921606811"),
    "medal":            ("🥇", "5280735858926822987"),
    "laptop":           ("💻", "5193177581888755275"),

    # ── Extra emojis from old dictionary not in user's list ─────────
    # (preserved for existing codebase usage)
    # These 7 IDs were tested and found broken (DOCUMENT_INVALID)
    "star_gift":        ("🌟", None),  # Broken ID - use fallback
    "rocket":           ("🚀", None),  # Broken ID - use fallback
    "gift":             ("🎁", None),  # Broken ID - use fallback
    "crown":            ("👑", None),  # Broken ID - use fallback
    "lightning":        ("⚡", None),  # Broken ID - use fallback
    "thumbsup":         ("👍", None),  # Broken ID - use fallback

    # ── Common UI emojis (fallback-only, ready for future premium IDs) ──
    "warning":          ("⚠️", None),
    "flag_eu":          ("🇪🇺", None),
    "refresh":          ("🔄", None),
    "clock":            ("⏰", None),
    "note":             ("📝", None),
    "tag":              ("🏷", None),
    "idea":             ("💡", None),
    "pointing":         ("👉", None),
    "shopping":         ("🛍", None),
    "id_icon":          ("🆔", None),
    "name_badge":       ("📛", None),
    "email_icon":       ("📧", None),
    "key_icon":         ("🔑", None),
    "writing":          ("✍️", None),
    "forbidden":        ("⛔", None),
    "comment":          ("💬", None),
    "search":           ("🔍", None),

    # ── Backward-compatible aliases ─────────────────────────────────
    # Old key → maps to the same emoji-id as the numbered variant.
    # This keeps all existing get_pe("bot"), get_pe("call"), etc. working.
    "bot":              ("🤖", "5985501934495207482"),   # same as bot_1
    "call":             ("📞", "5985623293091123400"),   # same as call_1
    "user":             ("👤", "5987666718271475727"),   # same as user_1
    "shield":           ("🛡", "5197288647275071607"),   # same as shield_2
    "web":              ("🌐", "5343789187172670307"),   # same as web_1
    "sparkles":         ("✨", "5316702099747123698"),   # same as sparkles_1
    "money":            ("💰", "5287231198098117669"),   # same as money_stack
    "heart":            ("🫀", "6044340078757548806"),   # same as anatomical_heart
}


def get_pe(emoji_key: str) -> str:
    """Return emoji string with HTML tag for valid premium IDs.

    For valid premium IDs: returns <tg-emoji emoji-id="...">fallback</tg-emoji>
    For broken/missing IDs: returns plain fallback emoji only.
    Falls back to 🔹 if key is unknown.
    """
    try:
        emoji_data = PREMIUM_EMOJIS.get(emoji_key)
        if emoji_data:
            fallback, premium_id = emoji_data
            if premium_id:
                return f'<tg-emoji emoji-id="{premium_id}">{fallback}</tg-emoji>'
            return fallback
    except Exception:
        pass
    return "🔹"


def get_plain_emoji(emoji_key: str) -> str:
    """Returns only the plain unicode fallback for use inside buttons.

    Telegram API forbids HTML <tg-emoji> tags inside button texts.
    This function extracts just the standard emoji for safe button use.
    Falls back to 🔹 if key is unknown.
    """
    try:
        emoji_data = PREMIUM_EMOJIS.get(emoji_key)
        if emoji_data:
            return emoji_data[0]  # Return the fallback string
    except Exception:
        pass
    return "🔹"


def get_premium_id(emoji_key: str) -> str | None:
    """Return the Telegram Premium custom emoji-id for use in InlineKeyboardButton.

    Bot API 9.4+ supports the ``icon_custom_emoji_id`` field on inline buttons.
    The button text can remain plain Unicode (fallback) while the button icon
    is rendered as the Premium custom emoji.

    Returns the numeric emoji-id as a str, or ``None`` if the key is unknown or
    the mapped ID is broken (``None`` in the table).
    """
    try:
        emoji_data = PREMIUM_EMOJIS.get(emoji_key)
        if emoji_data and emoji_data[1]:
            return emoji_data[1]
    except Exception:
        pass
    return None
