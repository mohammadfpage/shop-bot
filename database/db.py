"""
Async SQLite database layer (aiosqlite).

Tables:
    users           – registered Telegram users
    orders          – every purchase / request
    payments        – Zarinpal transaction records
    product_prices  – admin-managed base USD prices per product
"""

import aiosqlite
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import config

_db: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(config.DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
    return _db


async def init_db() -> None:
    """Create tables if they don't exist and seed default prices."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            is_admin    INTEGER DEFAULT 0,
            joined_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            product     TEXT NOT NULL,
            details     TEXT,
            amount_irt  INTEGER DEFAULT 0,
            status      TEXT DEFAULT 'pending',   -- pending | paid | delivered | cancelled
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS payments (
            payment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        INTEGER NOT NULL,
            authority       TEXT,
            ref_id          TEXT,
            amount_irt      INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'init',  -- init | verified | failed
            verified_at     TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );

        CREATE TABLE IF NOT EXISTS product_prices (
            product_key TEXT PRIMARY KEY,
            label       TEXT,
            usd_price   REAL NOT NULL
        );
    """)
    await db.commit()

    # Seed default prices if table is empty
    rows = await db.execute_fetchall("SELECT COUNT(*) FROM product_prices")
    if rows[0][0] == 0:
        for key, usd in config.PRICES.items():
            label = config.PRICE_LABELS.get(key, key)
            await db.execute(
                "INSERT INTO product_prices (product_key, label, usd_price) VALUES (?, ?, ?)",
                (key, label, usd),
            )
        await db.commit()


# ─── Product Price helpers ──────────────────────────────────────────

async def get_product_price(product_key: str) -> Optional[float]:
    """Return the USD price for a product from the DB, or None."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT usd_price FROM product_prices WHERE product_key = ?", (product_key,)
    )
    return rows[0][0] if rows else None


async def get_all_product_prices() -> list[aiosqlite.Row]:
    """Return all product prices."""
    db = await get_db()
    return await db.execute_fetchall(
        "SELECT product_key, label, usd_price FROM product_prices ORDER BY product_key"
    )


async def update_product_price(product_key: str, new_usd_price: float) -> bool:
    """Update a product's USD price. Returns True if a row was updated."""
    db = await get_db()
    cursor = await db.execute(
        "UPDATE product_prices SET usd_price = ? WHERE product_key = ?",
        (new_usd_price, product_key),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_price_or_default(product_key: str) -> float:
    """Return the USD price from DB, falling back to config.PRICES."""
    price = await get_product_price(product_key)
    if price is not None:
        return price
    return config.PRICES.get(product_key, 0.0)


# ─── User helpers ────────────────────────────────────────────────────

async def get_or_create_user(
    user_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
) -> aiosqlite.Row:
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM users WHERE user_id = ?", (user_id,)
    )
    if row:
        return row[0]
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name, is_admin, joined_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, full_name, 1 if user_id in config.ADMIN_IDS else 0, _now()),
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return rows[0]


async def set_admin(user_id: int, is_admin: bool = True) -> None:
    db = await get_db()
    await db.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (int(is_admin), user_id))
    await db.commit()


async def get_all_users() -> list[aiosqlite.Row]:
    """Return all registered users (for broadcast)."""
    db = await get_db()
    return await db.execute_fetchall("SELECT user_id FROM users")


# ─── Order helpers ───────────────────────────────────────────────────

async def create_order(user_id: int, product: str, details: str = "", amount_irt: int = 0) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO orders (user_id, product, details, amount_irt, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, product, details, amount_irt, "pending", _now()),
    )
    await db.commit()
    return cursor.lastrowid


async def update_order_status(order_id: int, status: str) -> None:
    db = await get_db()
    await db.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
    await db.commit()


async def get_order(order_id: int) -> Optional[aiosqlite.Row]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    return rows[0] if rows else None


async def get_user_orders(user_id: int) -> list[aiosqlite.Row]:
    db = await get_db()
    return await db.execute_fetchall(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    )


async def get_all_orders(status: Optional[str] = None) -> list[aiosqlite.Row]:
    db = await get_db()
    if status:
        return await db.execute_fetchall(
            "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC", (status,)
        )
    return await db.execute_fetchall("SELECT * FROM orders ORDER BY created_at DESC")


async def update_order_amount(order_id: int, amount_irt: int) -> None:
    db = await get_db()
    await db.execute("UPDATE orders SET amount_irt = ? WHERE order_id = ?", (amount_irt, order_id))
    await db.commit()


# ─── Payment helpers ─────────────────────────────────────────────────

async def create_payment(order_id: int, amount_irt: int) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO payments (order_id, amount_irt, status) VALUES (?, ?, ?)",
        (order_id, amount_irt, "init"),
    )
    await db.commit()
    return cursor.lastrowid


async def update_payment_authority(payment_id: int, authority: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE payments SET authority = ? WHERE payment_id = ?", (authority, payment_id)
    )
    await db.commit()


async def get_payment(payment_id: int) -> Optional[aiosqlite.Row]:
    """Return a payment joined to its order using bound parameters."""
    db = await get_db()
    rows = await db.execute_fetchall(
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
        WHERE p.payment_id = ?
        """,
        (payment_id,),
    )
    return rows[0] if rows else None


async def complete_payment(payment_id: int, order_id: int, ref_id: str) -> bool:
    """Atomically mark one pending payment and its order as paid."""
    db = await get_db()
    now = _now()
    await db.execute("BEGIN")
    try:
        payment_cursor = await db.execute(
            """
            UPDATE payments
            SET ref_id = ?, status = ?, verified_at = ?
            WHERE payment_id = ? AND order_id = ? AND status = ?
            """,
            (ref_id, "verified", now, payment_id, order_id, "init"),
        )
        if payment_cursor.rowcount != 1:
            await db.rollback()
            return False

        order_cursor = await db.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE order_id = ? AND status = ?
            """,
            ("paid", order_id, "pending"),
        )
        if order_cursor.rowcount != 1:
            await db.rollback()
            return False

        await db.commit()
        return True
    except Exception:
        await db.rollback()
        raise


async def fail_payment(payment_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE payments SET status = ? WHERE payment_id = ? AND status = ?",
        ("failed", payment_id, "init"),
    )
    await db.commit()


async def delete_payment(payment_id: int) -> None:
    """Delete a payment by primary key using a bound parameter."""
    db = await get_db()
    await db.execute("DELETE FROM payments WHERE payment_id = ?", (payment_id,))
    await db.commit()


async def get_payment_by_authority(authority: str) -> Optional[aiosqlite.Row]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM payments WHERE authority = ?", (authority,)
    )
    return rows[0] if rows else None


# ─── Revenue / Stats helpers ────────────────────────────────────────

async def get_revenue_by_period(period: str) -> int:
    """Return total revenue (amount_irt) for orders with status 'completed' or 'paid'
    or 'delivered'.

    period: 'today', 'week', 'month', or 'all'
    """
    db = await get_db()
    now = datetime.now(timezone.utc)

    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # all
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)

    start_iso = start.isoformat()
    rows = await db.execute_fetchall(
        "SELECT COALESCE(SUM(amount_irt), 0) FROM orders WHERE status IN ('completed', 'paid', 'delivered') AND created_at >= ?",
        (start_iso,)
    )
    return rows[0][0] if rows else 0


async def get_total_users() -> int:
    """Return total number of registered users."""
    db = await get_db()
    rows = await db.execute_fetchall("SELECT COUNT(*) FROM users")
    return rows[0][0] if rows else 0


async def get_order_count_by_status(status: str) -> int:
    """Return count of orders with a given status."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) FROM orders WHERE status = ?", (status,)
    )
    return rows[0][0] if rows else 0


# ─── Internal ────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
