"""
Database layer — SQLite via aiosqlite.
Tables: users, inventory, achievements
"""
import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "economy.db")

# ── Schema ────────────────────────────────────────────────────────────────────
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
                streak     INTEGER DEFAULT 0,
                last_daily TEXT,
                last_work  TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                item_type  TEXT,
                item_name  TEXT,
                won_at     TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER,
                code      TEXT,
                name      TEXT,
                earned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, code)
            )
        """)
        # Safe migrations for existing DBs
        for col, dfn in [
            ("streak",     "INTEGER DEFAULT 0"),
            ("last_work",  "TEXT"),
            ("created_at", "TEXT DEFAULT (datetime('now'))"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {dfn}")
            except Exception:
                pass
        await db.commit()

# ── Users ─────────────────────────────────────────────────────────────────────
async def ensure_user(user_id: int, username: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username))
        if username:
            await db.execute(
                "UPDATE users SET username = ? WHERE user_id = ?",
                (username, user_id))
        await db.commit()

async def get_user(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {}

async def get_coins(user_id: int) -> int:
    u = await get_user(user_id)
    return u.get("coins", 0)

async def add_coins(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = MAX(0, coins + ?) WHERE user_id = ?",
            (amount, user_id))
        await db.commit()

async def deduct_coins(user_id: int, amount: int) -> bool:
    u = await get_user(user_id)
    if not u or u.get("coins", 0) < amount:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins - ? WHERE user_id = ?",
            (amount, user_id))
        await db.commit()
    return True

async def add_win(user_id: int, xp: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET wins = wins + 1, xp = xp + ? WHERE user_id = ?",
            (xp, user_id))
        await db.commit()

async def add_played(user_id: int, xp: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET played = played + 1, xp = xp + ? WHERE user_id = ?",
            (xp, user_id))
        await db.commit()

# ── Top / inventory ────────────────────────────────────────────────────────────
async def get_top(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY coins DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def add_item(user_id: int, item_type: str, item_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO inventory (user_id, item_type, item_name) VALUES (?, ?, ?)",
            (user_id, item_type, item_name))
        await db.commit()

async def get_inventory(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM inventory WHERE user_id = ? ORDER BY won_at DESC", (user_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

# ── Daily / Work ───────────────────────────────────────────────────────────────
async def get_daily(user_id: int) -> str | None:
    u = await get_user(user_id)
    return u.get("last_daily")

async def set_daily(user_id: int, iso_str: str, new_streak: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_daily = ?, streak = ? WHERE user_id = ?",
            (iso_str, new_streak, user_id))
        await db.commit()

async def get_work(user_id: int) -> str | None:
    u = await get_user(user_id)
    return u.get("last_work")

async def set_work(user_id: int, iso_str: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_work = ? WHERE user_id = ?",
            (iso_str, user_id))
        await db.commit()

# ── Achievements ───────────────────────────────────────────────────────────────
ACHIEVEMENT_DEFS: dict[str, str] = {
    "first_win":  "🏆 Prva Pobjeda",
    "win10":      "🥇 10 Pobjeda",
    "win50":      "👑 50 Pobjeda",
    "win100":     "💎 100 Pobjeda",
    "rich":       "💰 Milijunaš (1M coina)",
    "streak7":    "🔥 7-dnevni Streak",
    "streak30":   "⚡ 30-dnevni Streak",
    "played50":   "🎮 50 Odigranih",
    "played200":  "🎲 200 Odigranih",
    "jackpot":    "🎰 Jackpot Pobjednik",
    "level10":    "🌟 Level 10",
    "level25":    "🔮 Level 25",
    "level50":    "🚀 Level 50",
    "all_games":  "🌈 Sve Igre",
}

async def award_achievement(user_id: int, code: str) -> bool:
    if code not in ACHIEVEMENT_DEFS:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO achievements (user_id, code, name) VALUES (?, ?, ?)",
                (user_id, code, ACHIEVEMENT_DEFS[code]))
            await db.commit()
            return True
        except Exception:
            return False

async def get_achievements(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM achievements WHERE user_id = ? ORDER BY earned_at ASC",
            (user_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def check_achievements(user_id: int) -> list[str]:
    """Award any newly unlocked achievements. Returns list of newly earned display names."""
    u = await get_user(user_id)
    if not u:
        return []
    lvl = 1 + u.get("xp", 0) // 500
    checks = [
        ("first_win",  u.get("wins", 0) >= 1),
        ("win10",      u.get("wins", 0) >= 10),
        ("win50",      u.get("wins", 0) >= 50),
        ("win100",     u.get("wins", 0) >= 100),
        ("rich",       u.get("coins", 0) >= 1_000_000),
        ("streak7",    u.get("streak", 0) >= 7),
        ("streak30",   u.get("streak", 0) >= 30),
        ("played50",   u.get("played", 0) >= 50),
        ("played200",  u.get("played", 0) >= 200),
        ("level10",    lvl >= 10),
        ("level25",    lvl >= 25),
        ("level50",    lvl >= 50),
    ]
    earned = []
    for code, condition in checks:
        if condition and await award_achievement(user_id, code):
            earned.append(ACHIEVEMENT_DEFS[code])
    return earned
