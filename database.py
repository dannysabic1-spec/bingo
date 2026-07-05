import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "economy.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                coins      INTEGER DEFAULT 500,
                xp         INTEGER DEFAULT 0,
                wins       INTEGER DEFAULT 0,
                played     INTEGER DEFAULT 0,
                daily_last TEXT    DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                item_type  TEXT,
                item_name  TEXT,
                won_at     TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def ensure_user(user_id: int, username: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        if username:
            await db.execute(
                "UPDATE users SET username = ? WHERE user_id = ?",
                (username, user_id)
            )
        await db.commit()

async def get_user(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

async def get_coins(user_id: int) -> int:
    u = await get_user(user_id)
    return u["coins"] if u else 0

async def add_coins(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = MAX(0, coins + ?) WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def deduct_coins(user_id: int, amount: int) -> bool:
    """Returns True if successful, False if not enough coins."""
    u = await get_user(user_id)
    if not u or u["coins"] < amount:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()
    return True

async def add_win(user_id: int, xp: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET wins = wins + 1, played = played + 1, xp = xp + ? WHERE user_id = ?",
            (xp, user_id)
        )
        await db.commit()

async def add_played(user_id: int, xp: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET played = played + 1, xp = xp + ? WHERE user_id = ?",
            (xp, user_id)
        )
        await db.commit()

async def add_item(user_id: int, item_type: str, item_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO inventory (user_id, item_type, item_name) VALUES (?, ?, ?)",
            (user_id, item_type, item_name)
        )
        await db.commit()

async def get_top(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, coins, wins, xp FROM users ORDER BY coins DESC LIMIT ?",
            (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def get_inventory(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_type, item_name, won_at FROM inventory WHERE user_id = ? ORDER BY won_at DESC",
            (user_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def get_daily(user_id: int) -> str | None:
    u = await get_user(user_id)
    return u["daily_last"] if u else None

async def set_daily(user_id: int, ts: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET daily_last = ? WHERE user_id = ?", (ts, user_id))
        await db.commit()
