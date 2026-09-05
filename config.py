import os
from dataclasses import dataclass, field


def _parse_admin_ids() -> list[int]:
    """Parse ADMIN_IDS from the environment variable.

    Format: comma-separated Telegram user IDs, e.g. "1652089506,7174138646"

    How to set:
        .env file:    ADMIN_IDS=1652089506,7174138646
        Render:       Environment → ADMIN_IDS = 1652089506,7174138646
        Shell:        export ADMIN_IDS="1652089506,7174138646"
    """
    raw = os.getenv("ADMIN_IDS", "1652089506,7174138646")
    return [int(uid.strip()) for uid in raw.split(",") if uid.strip()]


@dataclass
class Config:
    # ─── Bot ────────────────────────────────────────────────────────────
    BOT_TOKEN: str = '8494498767:AAEfmbtnX89gngZbWPjkb3mMaTFfwVhphwY'

    # ─── Admin (read from ADMIN_IDS env var, comma-separated) ───────────
    ADMIN_IDS: list[int] = field(default_factory=_parse_admin_ids)

    # ─── Support Admin (receives tickets) ────────────────────────────────
    SUPPORT_ADMIN_ID: int = 1652089506

    # ─── Zarinpal Payment Gateway ──────────────────────────────────────
    ZARINPAL_MERCHANT_ID: str = os.getenv(
        "ZARINPAL_MERCHANT_ID",
        "b21303c7-6aa3-4f6d-98d2-4b7d39dca37f",
    )
    ZARINPAL_SANDBOX: bool = os.getenv("ZARINPAL_SANDBOX", "true").lower() == "true"
    ZARINPAL_CALLBACK_URL: str = os.getenv("ZARINPAL_CALLBACK_URL", "https://hamrahsocial.ir/verify")

    # ─── Webhook Server ────────────────────────────────────────────────
    WEBHOOK_MODE: bool = os.getenv("WEBHOOK_MODE", "false").lower() == "true"
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8443"))
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "https://yourdomain.com")

    # ─── Database (PostgreSQL via Neon) ──────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_Nv5Sxsnfe4Mt@ep-wispy-wind-a51dz5fb-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require",
    )

    # ─── BrsApi Exchange Rate API ──────────────────────────────────────
    BRS_API_URL: str = "https://Api.BrsApi.ir/Market/Gold_Currency.php?key=BuW46kKxyFYAWKTQchxx7ajGzv3ryR8x"

    # ─── Profit Margin ──────────────────────────────────────────────────
    PROFIT_MARGIN_PERCENT: float = 20.0  # 20% on top of USD price * rate

    # ─── Default Product Prices (in USD) — used as seed for DB ──────────
    PRICES: dict = field(default_factory=lambda: {
        # Telegram Premium
        "telegram_premium_monthly": 5.99,
        "telegram_premium_quarterly": 14.99,
        "telegram_premium_semi_annual": 24.99,
        "telegram_premium_yearly": 35.99,

        # Telegram Stars (per 50 stars)
        "telegram_stars_per_50": 0.99,

        # Virtual Numbers
        "virtual_number": 3.50,

        # AI Accounts
        "chatgpt_premium": 19.99,
        "gemini_premium": 14.99,

        # Design Service Tiers
        "design_ai": 9.99,
        "design_simple": 19.99,
        "design_normal": 39.99,
        "design_special": 79.99,
    })

    # ─── Human-readable product labels (Persian) ────────────────────────
    PRICE_LABELS: dict = field(default_factory=lambda: {
        "telegram_premium_monthly": "تلگرام پرمیوم — ماهانه",
        "telegram_premium_quarterly": "تلگرام پرمیوم — سه‌ماهه",
        "telegram_premium_semi_annual": "تلگرام پرمیوم — شش‌ماهه",
        "telegram_premium_yearly": "تلگرام پرمیوم — سالانه",
        "telegram_stars_per_50": "استارز تلگرام (هر ۵۰ استارز)",
        "virtual_number": "شماره مجازی",
        "chatgpt_premium": "چت‌جی‌پی‌تی پلاس",
        "gemini_premium": "جمنای پیشرفته",
        "design_ai": "طراحی هوش مصنوعی",
        "design_simple": "طراحی ساده",
        "design_normal": "طراحی حرفه‌ای",
        "design_special": "طراحی ویژه",
    })

    # ─── Service Tariffs (page security) ───────────────────────────────
    SECURITY_TARIFFS: dict = field(default_factory=lambda: {
        "basic": {"usd": 25.00, "description": "بررسی و گزارش امنیتی پایه"},
        "standard": {"usd": 50.00, "description": "امنیت استاندارد + SSL + فایروال"},
        "advanced": {"usd": 100.00, "description": "امنیت پیشرفته + مانیتورینگ مداوم"},
    })

    # ─── Pre-delivered AI Account Credentials (mock) ───────────────────
    AI_ACCOUNTS: dict = field(default_factory=lambda: {
        "chatgpt": [
            {"email": "user_chatgpt_1@domain.com", "password": "Ch@tGPT_Pass1"},
            {"email": "user_chatgpt_2@domain.com", "password": "Ch@tGPT_Pass2"},
        ],
        "gemini": [
            {"email": "user_gemini_1@domain.com", "password": "Gemin1_Pass1"},
            {"email": "user_gemini_2@domain.com", "password": "Gemin1_Pass2"},
        ],
    })


# Singleton
config = Config()
