"""
Async PostgreSQL database layer (asyncpg + Neon.tech).

Tables:
    users           – registered Telegram users
    orders          – every purchase / request
    payments        – Zarinpal transaction records
    product_prices  – admin-managed base USD prices per product
    tickets         – support tickets
    settings        – key/value admin settings (e.g. profit margin)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

from config import config

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


# ─── Connection Pool ────────────────────────────────────────────────

async def get_pool() -> asyncpg.Pool:
    """Return the global connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=config.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("PostgreSQL connection pool created.")
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed.")


# ─── Schema Initialization ─────────────────────────────────────────

async def init_db() -> None:
    """Create tables if they don't exist and seed default prices."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     BIGINT PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                phone_number TEXT,
                is_admin    BOOLEAN DEFAULT FALSE,
                joined_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id    SERIAL PRIMARY KEY,
                user_id     BIGINT NOT NULL,
                product     TEXT NOT NULL,
                details     TEXT,
                amount_irt  INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                payment_id      SERIAL PRIMARY KEY,
                order_id        INTEGER NOT NULL,
                authority       TEXT,
                ref_id          TEXT,
                amount_irt      INTEGER DEFAULT 0,
                status          TEXT DEFAULT 'init',
                verified_at     TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            );

            CREATE TABLE IF NOT EXISTS product_prices (
                product_key TEXT PRIMARY KEY,
                label       TEXT,
                usd_price   DOUBLE PRECISION NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id   SERIAL PRIMARY KEY,
                user_id     BIGINT NOT NULL,
                username    TEXT,
                full_name   TEXT,
                message     TEXT NOT NULL,
                status      TEXT DEFAULT 'open',
                created_at  TEXT,
                replied_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                setting_key  TEXT PRIMARY KEY,
                setting_value TEXT
            );
        """)

        # Seed default prices if table is empty
        row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM product_prices")
        if row["cnt"] == 0:
            for key, usd in config.PRICES.items():
                label = config.PRICE_LABELS.get(key, key)
                await conn.execute(
                    "INSERT INTO product_prices (product_key, label, usd_price) VALUES ($1, $2, $3)",
                    key, label, usd,
                )
        else:
            # Insert any new products that exist in config but not in DB
            for key, usd in config.PRICES.items():
                label = config.PRICE_LABELS.get(key, key)
                await conn.execute(
                    "INSERT INTO product_prices (product_key, label, usd_price) "
                    "VALUES ($1, $2, $3) ON CONFLICT (product_key) DO NOTHING",
                    key, label, usd,
                )
        # Migrate: add phone_number column if missing (idempotent)
        try:
            await conn.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number TEXT"
            )
        except Exception:
            pass  # column already exists or DB doesn't support IF NOT EXISTS

        logger.info("Database tables initialized.")


# ─── Product Price helpers ──────────────────────────────────────────

async def get_product_price(product_key: str) -> Optional[float]:
    """Return the USD price for a product from the DB, or None."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT usd_price FROM product_prices WHERE product_key = $1", product_key,
    )
    return float(row["usd_price"]) if row else None


async def get_all_product_prices() -> list[asyncpg.Record]:
    """Return all product prices."""
    pool = await get_pool()
    return await pool.fetch(
        "SELECT product_key, label, usd_price FROM product_prices ORDER BY product_key"
    )


async def update_product_price(product_key: str, new_usd_price: float) -> bool:
    """Update a product's USD price. Returns True if a row was updated."""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE product_prices SET usd_price = $1 WHERE product_key = $2",
        new_usd_price, product_key,
    )
    return result == "UPDATE 1"


async def get_price_or_default(product_key: str) -> float:
    """Return the USD price from DB, falling back to config.PRICES."""
    price = await get_product_price(product_key)
    if price is not None:
        return price
    return config.PRICES.get(product_key, 0.0)


# ─── Settings helpers (key/value admin settings) ─────────────────────

async def get_setting(setting_key: str, default: Optional[str] = None) -> Optional[str]:
    """Return a setting value from the ``settings`` table, or *default*.

    Falls back to *default* if the table is missing or the key is absent,
    so callers are never broken by an uninitialized schema.
    """
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT setting_value FROM settings WHERE setting_key = $1",
            setting_key,
        )
        return row["setting_value"] if row else default
    except Exception:
        logger.warning("get_setting(%s) failed; using default.", setting_key)
        return default


async def set_setting(setting_key: str, setting_value: str) -> None:
    """Upsert a setting into the ``settings`` table."""
    try:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO settings (setting_key, setting_value)
            VALUES ($1, $2)
            ON CONFLICT (setting_key) DO UPDATE SET setting_value = $2
            """,
            setting_key, setting_value,
        )
    except Exception:
        logger.warning("set_setting(%s) failed.", setting_key)


async def get_profit_margin(default: float) -> float:
    """Return the admin-configured profit margin (percent).

    Source of truth is the ``settings`` table (key ``account_profit_margin``).
    If it is not set, falls back to *default* (usually config value).
    """
    value = await get_setting("account_profit_margin", str(default))
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


async def set_profit_margin(margin: float) -> None:
    """Persist the account profit margin (percent) to the settings table."""
    await set_setting("account_profit_margin", str(margin))


# ─── User helpers ────────────────────────────────────────────────────

async def get_or_create_user(
    user_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
) -> asyncpg.Record:
    """Fetch an existing user or insert a new one. Returns the user row."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id,
        )
        if row:
            return row
        await conn.execute(
            """INSERT INTO users (user_id, username, full_name, is_admin, joined_at)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (user_id) DO NOTHING""",
            user_id, username, full_name,
            user_id in config.ADMIN_IDS,
            _now(),
        )
        return await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id,
        )


async def set_admin(user_id: int, is_admin: bool = True) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET is_admin = $1 WHERE user_id = $2", is_admin, user_id,
    )


async def update_user_phone(user_id: int, phone_number: str) -> None:
    """Save the user's phone number after they share it via request_contact."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET phone_number = $1 WHERE user_id = $2",
        phone_number, user_id,
    )


async def user_has_phone(user_id: int) -> bool:
    """Return True if the user has already shared their phone number."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT phone_number FROM users WHERE user_id = $1", user_id,
    )
    return bool(row and row["phone_number"])


async def get_all_users() -> list[asyncpg.Record]:
    """Return all registered users (for broadcast)."""
    pool = await get_pool()
    return await pool.fetch("SELECT user_id FROM users")


async def get_total_users() -> int:
    """Return total number of registered users."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT COUNT(*) AS cnt FROM users")
    return row["cnt"] if row else 0


# ─── Order helpers ───────────────────────────────────────────────────

async def create_order(user_id: int, product: str, details: str = "", amount_irt: int = 0) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO orders (user_id, product, details, amount_irt, status, created_at)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING order_id""",
        user_id, product, details, amount_irt, "pending", _now(),
    )
    return row["order_id"]


async def update_order_status(order_id: int, status: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE orders SET status = $1 WHERE order_id = $2", status, order_id,
    )


async def get_order(order_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM orders WHERE order_id = $1", order_id,
    )


async def get_user_orders(user_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC", user_id,
    )


async def get_all_orders(status: Optional[str] = None) -> list[asyncpg.Record]:
    pool = await get_pool()
    if status:
        return await pool.fetch(
            "SELECT * FROM orders WHERE status = $1 ORDER BY created_at DESC", status,
        )
    return await pool.fetch("SELECT * FROM orders ORDER BY created_at DESC")


async def update_order_amount(order_id: int, amount_irt: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE orders SET amount_irt = $1 WHERE order_id = $2", amount_irt, order_id,
    )


# ─── Payment helpers ─────────────────────────────────────────────────

async def create_payment(order_id: int, amount_irt: int) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO payments (order_id, amount_irt, status)
           VALUES ($1, $2, $3) RETURNING payment_id""",
        order_id, amount_irt, "init",
    )
    return row["payment_id"]


async def update_payment_authority(payment_id: int, authority: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE payments SET authority = $1 WHERE payment_id = $2", authority, payment_id,
    )


async def get_payment(payment_id: int) -> Optional[asyncpg.Record]:
    """Return a payment joined to its order."""
    pool = await get_pool()
    return await pool.fetchrow(
        """
        SELECT
            p.payment_id,
            p.order_id,
            p.authority,
            p.ref_id,
            p.amount_irt AS payment_amount_irt,
            p.status AS payment_status,
            o.user_id,
            o.product,
            o.details,
            o.amount_irt AS order_amount_irt,
            o.status AS order_status
        FROM payments AS p
        JOIN orders AS o ON o.order_id = p.order_id
        WHERE p.payment_id = $1
        """,
        payment_id,
    )


async def complete_payment(payment_id: int, order_id: int, ref_id: str) -> bool:
    """Atomically mark one pending payment and its order as paid."""
    pool = await get_pool()
    now = _now()
    async with pool.acquire() as conn:
        async with conn.transaction():
            payment_result = await conn.execute(
                """UPDATE payments
                   SET ref_id = $1, status = $2, verified_at = $3
                   WHERE payment_id = $4 AND order_id = $5 AND status = $6""",
                ref_id, "verified", now, payment_id, order_id, "init",
            )
            if payment_result != "UPDATE 1":
                return False

            order_result = await conn.execute(
                """UPDATE orders SET status = $1
                   WHERE order_id = $2 AND status = $3""",
                "paid", order_id, "pending",
            )
            if order_result != "UPDATE 1":
                return False
    return True


async def fail_payment(payment_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE payments SET status = $1 WHERE payment_id = $2 AND status = $3",
        "failed", payment_id, "init",
    )


async def delete_payment(payment_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM payments WHERE payment_id = $1", payment_id,
    )


async def get_payment_by_authority(authority: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM payments WHERE authority = $1", authority,
    )


# ─── Revenue / Stats helpers ────────────────────────────────────────

async def get_revenue_by_period(period: str) -> int:
    """Return total revenue (amount_irt) for completed/paid/delivered orders."""
    pool = await get_pool()
    now = datetime.now(timezone.utc)

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)

    start_iso = start.isoformat()
    row = await pool.fetchrow(
        """SELECT COALESCE(SUM(amount_irt), 0) AS total
           FROM orders
           WHERE status IN ('completed', 'paid', 'delivered')
             AND created_at >= $1""",
        start_iso,
    )
    return row["total"] if row else 0


async def get_order_count_by_status(status: str) -> int:
    """Return count of orders with a given status."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM orders WHERE status = $1", status,
    )
    return row["cnt"] if row else 0


# ─── Ticket helpers ──────────────────────────────────────────────────

async def create_ticket(
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
    message: str,
) -> int:
    """Create a new support ticket. Returns the ticket_id."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO tickets (user_id, username, full_name, message, status, created_at)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING ticket_id""",
        user_id, username, full_name, message, "open", _now(),
    )
    return row["ticket_id"]


async def get_ticket(ticket_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM tickets WHERE ticket_id = $1", ticket_id,
    )


async def close_ticket(ticket_id: int) -> None:
    """Mark a ticket as closed."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE tickets SET status = 'closed', replied_at = $1 WHERE ticket_id = $2",
        _now(), ticket_id,
    )


async def get_open_tickets() -> list[asyncpg.Record]:
    """Return all open tickets."""
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM tickets WHERE status = 'open' ORDER BY created_at DESC"
    )


async def get_open_ticket_by_user(user_id: int) -> Optional[asyncpg.Record]:
    """Return the most recent open ticket for a user, or None."""
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM tickets WHERE user_id = $1 AND status = 'open' "
        "ORDER BY created_at DESC LIMIT 1",
        user_id,
    )


# ─── Internal ────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
