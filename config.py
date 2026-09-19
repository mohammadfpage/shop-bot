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
    # BOT_TOKEN: str = '8494498767:AAEfmbtnX89gngZbWPjkb3mMaTFfwVhphwY'
    
    # darkan
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
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8443"))
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "https://hamrahsocial.ir")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")

    # ─── Database (PostgreSQL via Neon) ──────────────────────────────────
    # DATABASE_URL: str = os.getenv(
    #     "DATABASE_URL",
    #     "postgresql://neondb_owner:npg_Nv5Sxsnfe4Mt@ep-wispy-wind-a51dz5fb-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require",
    # )

    # Databse (local vps) 
    DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://bot_user:PixelBot%402026@127.0.0.1:5432/shopbot_db",
    ) 

    # ─── BrsApi Exchange Rate API ──────────────────────────────────────
    BRS_API_URL: str = "https://Api.BrsApi.ir/Market/Gold_Currency.php?key=BuW46kKxyFYAWKTQchxx7ajGzv3ryR8x"

    # ─── Profit Margin ──────────────────────────────────────────────────
    PROFIT_MARGIN_PERCENT: float = 20.0  # 20% on top of USD price * rate

    # ─── Shiznumber Virtual Number API ────────────────────────────────
    SHIZ_API_KEY: str = os.getenv(
        "SHIZ_API_KEY",
        "YOUR_API_KEY_HERE",
    )

    # ─── Legacy Ozvinoo (kept for backward compatibility) ──────────────
    OZVINOO_BASE_URL: str = "https://api.ozvinoo.xyz/"
    OZVINOO_API_KEY: str = os.getenv(
        "OZVINOO_API_KEY",
        "1652089506:3z6nfh74s943Bwk4Q8vRc6bBdVaKjw1962ao38cldTbA",
    )
    ACCOUNT_PROFIT_MARGIN_PERCENT: float = 30.0  # 30% margin on account purchases

    # ─── Default Product Prices (in USD) — used as seed for DB ──────────
    PRICES: dict = field(default_factory=lambda: {
        # Telegram Premium
        "telegram_premium_monthly": 5.99,
        "telegram_premium_quarterly": 14.99,
        "telegram_premium_semi_annual": 24.99,
        "telegram_premium_yearly": 35.99,

        # Telegram Stars (per 50 stars, custom quantity)
        "telegram_stars_per_50": 0.99,

        # Telegram Stars Gifts (fixed packages)
        "telegram_stars_gift_50": 0.99,
        "telegram_stars_gift_100": 1.99,
        "telegram_stars_gift_250": 4.99,
        "telegram_stars_gift_500": 9.99,
        "telegram_stars_gift_1000": 19.99,
        "telegram_stars_gift_2500": 49.99,

        # AI Accounts
        "chatgpt_premium": 19.99,
        "gemini_premium": 14.99,

        # Design Services — Video (ویدیو)
        "design_video_ai": 9.99,
        "design_video_simple": 19.99,
        "design_video_pro": 39.99,
        "design_video_special": 79.99,

        # Design Services — Photo (عکس)
        "design_photo_ai": 7.99,
        "design_photo_simple": 14.99,
        "design_photo_pro": 29.99,
        "design_photo_special": 59.99,

        # Design Services — Logo (لوگو)
        "design_logo_ai": 12.99,
        "design_logo_simple": 24.99,
        "design_logo_pro": 49.99,
        "design_logo_special": 99.99,

        # Stars Gifts (individual items — official Telegram Star Gifts)
        "stars_gift_heart_15": 0.49,
        "stars_gift_teddy_15": 0.49,
        "stars_gift_gift_25": 0.99,
        "stars_gift_rose_25": 0.99,
        "stars_gift_cake_50": 1.49,
        "stars_gift_flower_50": 1.49,
        "stars_gift_bottle_50": 1.49,
        "stars_gift_rocket_50": 1.49,
        "stars_gift_trophy_100": 2.99,
        "stars_gift_ring_100": 2.99,
        "stars_gift_diamond_100": 2.99,
    })

    # ─── Human-readable product labels (Persian) ────────────────────────
    PRICE_LABELS: dict = field(default_factory=lambda: {
        "telegram_premium_monthly": "تلگرام پرمیوم — ماهانه",
        "telegram_premium_quarterly": "تلگرام پرمیوم — سه‌ماهه",
        "telegram_premium_semi_annual": "تلگرام پرمیوم — شش‌ماهه",
        "telegram_premium_yearly": "تلگرام پرمیوم — سالانه",
        "telegram_stars_per_50": "استارز تلگرام (هر ۵۰ استارز)",
        "telegram_stars_gift_50": "گیفت ۵۰ استارز",
        "telegram_stars_gift_100": "گیفت ۱۰۰ استارز",
        "telegram_stars_gift_250": "گیفت ۲۵۰ استارز",
        "telegram_stars_gift_500": "گیفت ۵۰۰ استارز",
        "telegram_stars_gift_1000": "گیفت ۱۰۰۰ استارز",
        "telegram_stars_gift_2500": "گیفت ۲۵۰۰ استارز",
        "chatgpt_premium": "چت‌جی‌پی‌تی پلاس",
        "gemini_premium": "جمنای پیشرفته",
        # Design — Video
        "design_video_ai": "ویدیو — هوش مصنوعی",
        "design_video_simple": "ویدیو — ساده",
        "design_video_pro": "ویدیو — حرفه‌ای",
        "design_video_special": "ویدیو — ویژه",
        # Design — Photo
        "design_photo_ai": "عکس — هوش مصنوعی",
        "design_photo_simple": "عکس — ساده",
        "design_photo_pro": "عکس — حرفه‌ای",
        "design_photo_special": "عکس — ویژه",
        # Design — Logo
        "design_logo_ai": "لوگو — هوش مصنوعی",
        "design_logo_simple": "لوگو — ساده",
        "design_logo_pro": "لوگو — حرفه‌ای",
        "design_logo_special": "لوگو — ویژه",
        # Stars Gifts (individual — official Telegram Star Gifts)
        "stars_gift_heart_15": "❤️ گیفت قلب",
        "stars_gift_teddy_15": "🧸 گیفت تدی",
        "stars_gift_gift_25": "🎁 گیفت کادو",
        "stars_gift_rose_25": "🌹 گیفت گل رز",
        "stars_gift_cake_50": "🎂 گیفت کیک",
        "stars_gift_flower_50": "💐 گیفت گل",
        "stars_gift_bottle_50": "🍾 گیفت بطری",
        "stars_gift_rocket_50": "🚀 گیفت سفینه",
        "stars_gift_trophy_100": "🏆 گیفت جام",
        "stars_gift_ring_100": "💍 گیفت حلقه",
        "stars_gift_diamond_100": "💎 گیفت الماس",
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
