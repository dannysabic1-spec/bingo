"""
Discord Game Bot — kompletan sistem: XP/Level, streak, work, shop, profil, achievements.
"""

import discord
from discord.ext import commands
import asyncio
import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
import sys
sys.path.insert(0, os.path.dirname(__file__))

from database import (
    init_db, ensure_user, get_user, get_coins,
    add_coins, deduct_coins, add_win, add_played, add_item,
    get_top, get_inventory, get_daily, set_daily,
    get_work, set_work, get_achievements, check_achievements,
    award_achievement, ACHIEVEMENT_DEFS,
)
from games import ALL_GAMES

TOKEN           = os.environ.get("DISCORD_TOKEN")
GAME_CHANNEL_ID = int(os.environ.get("GAME_CHANNEL_ID", 0))
GAME_INTERVAL   = int(os.environ.get("GAME_INTERVAL", 180))
BOT_OWNER_ID    = int(os.environ.get("BOT_OWNER_ID", 0))
COIN = "🪙"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

game_index  = 0
game_running = False

# ── Helpers ────────────────────────────────────────────────────────────────────
def emb(title: str, desc: str = None,
        color=discord.Color.gold(),
        fields: list = None,
        footer: str = None,
        thumbnail: str = None) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.utcnow()
    for f in (fields or []):
        e.add_field(name=f[0], value=f[1], inline=f[2] if len(f) > 2 else True)
    if footer:
        e.set_footer(text=footer)
    if thumbnail:
        e.set_thumbnail(url=thumbnail)
    return e

def get_level(xp: int) -> int:
    return 1 + xp // 500

def xp_to_next(xp: int) -> int:
    return 500 - (xp % 500)

def progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int(length * current / total)
    return "█" * filled + "░" * (length - filled)

def get_rank(level: int) -> str:
    if level >= 50: return "🚀 Legenda"
    if level >= 25: return "🔮 Master"
    if level >= 15: return "👑 Elite"
    if level >= 10: return "🌟 Pro"
    if level >=  5: return "🎮 Veteran"
    return "🥉 Početnik"

async def get_channel() -> discord.TextChannel | None:
    ch = bot.get_channel(GAME_CHANNEL_ID)
    if ch is None:
        try:
            ch = await bot.fetch_channel(GAME_CHANNEL_ID)
        except Exception as e:
            print(f"[ERROR] fetch_channel({GAME_CHANNEL_ID}) failed: {type(e).__name__}: {e}")
            ch = None
    return ch

async def notify_levelup(channel, uid: int, old_lvl: int, new_lvl: int):
    rank = get_rank(new_lvl)
    bonus = new_lvl * 100
    await add_coins(uid, bonus)
    await channel.send(embed=emb(
        "⬆️  Level Up!",
        f"<@{uid}> — Level **{old_lvl}** → **{new_lvl}**!",
        discord.Color.from_rgb(100, 200, 255),
        fields=[
            ("Novi level", str(new_lvl), True),
            ("Rang",       rank,         True),
            ("Bonus",      f"+**{bonus}** {COIN}", True),
        ]
    ))

async def post_achievements(channel, uid: int):
    new_ach = await check_achievements(uid)
    for ach in new_ach:
        await channel.send(embed=emb(
            "🏆  Achievement Otključan!",
            f"<@{uid}> — **{ach}**",
            discord.Color.from_rgb(255, 215, 0)
        ))


# ── Game loop ──────────────────────────────────────────────────────────────────
async def run_game_loop():
    global game_index, game_running
    await bot.wait_until_ready()
    await asyncio.sleep(5)

    channel = await get_channel()
    if channel is None:
        print(f"[ERROR] Kanal {GAME_CHANNEL_ID} nije pronađen!")
        return
    print(f"[OK] Game loop pokrenut u #{channel.name}")

    game_names = "  •  ".join(cls().NAME for cls in ALL_GAMES)
    await channel.send(embed=emb(
        "🎮  Game Bot je Online!",
        f"Igre kreću automatski svake **{GAME_INTERVAL // 60}** minute.\n"
        f"Novi igrači dobivaju **500** {COIN} na startu.",
        discord.Color.blurple(),
        fields=[
            ("10 igara u rotaciji", game_names, False),
            ("Komande", "`!help` za listu svih komandi", False),
        ]
    ))

    order = list(range(len(ALL_GAMES)))
    random.shuffle(order)

    while True:
        game_running = True
        GameClass = ALL_GAMES[order[game_index % len(ALL_GAMES)]]
        game = GameClass()
        game_index += 1
        if game_index % len(ALL_GAMES) == 0:
            random.shuffle(order)

        await channel.send(embed=emb(
            f"⏳  Sljedeća igra: {game.NAME}",
            "Kreće za nekoliko sekundi...",
            discord.Color.from_rgb(40, 40, 60)
        ))
        await asyncio.sleep(8)

        try:
            await game.run(channel)
        except Exception as ex:
            import traceback
            print(f"[ERROR] {game.NAME}: {ex}")
            traceback.print_exc()

        game_running = False
        mins = GAME_INTERVAL // 60
        await channel.send(embed=emb(
            "⏸️  Pauza",
            f"Sljedeća igra za **{mins} minute**.\n"
            f"Iskoristi pauzu: `!daily` `!rad` `!shop`",
            discord.Color.from_rgb(30, 30, 45)
        ))
        await asyncio.sleep(GAME_INTERVAL)


# ═══════════════════════════════════════════════════════════════════════════════
#  KOMANDE
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="balans", aliases=["balance","b","coins"])
async def balance(ctx):
    await ensure_user(ctx.author.id, ctx.author.display_name)
    u = await get_user(ctx.author.id)
    lvl  = get_level(u["xp"])
    rank = get_rank(lvl)
    xp_c = u["xp"] % 500
    bar  = progress_bar(xp_c, 500, 12)
    wr   = f"{u['wins']/u['played']*100:.0f}%" if u["played"] > 0 else "—"
    await ctx.send(embed=emb(
        f"💰  {ctx.author.display_name}",
        f"**{u['coins']:,}** {COIN}",
        discord.Color.gold(),
        fields=[
            ("Level",    f"**{lvl}** — {rank}", True),
            ("Win Rate", wr,                     True),
            ("Streak",   f"🔥 {u.get('streak',0)} dana", True),
            ("XP Progress",
             f"`{bar}` {xp_c}/500\n({xp_to_next(u['xp'])} XP do Level {lvl+1})", False),
        ]
    ))


@bot.command(name="profil", aliases=["profile","p"])
async def profile(ctx, member: discord.Member = None):
    target = member or ctx.author
    await ensure_user(target.id, target.display_name)
    u   = await get_user(target.id)
    ach = await get_achievements(target.id)
    inv = await get_inventory(target.id)
    lvl  = get_level(u["xp"])
    rank = get_rank(lvl)
    xp_c = u["xp"] % 500
    bar  = progress_bar(xp_c, 500, 12)
    wr   = f"{u['wins']/u['played']*100:.0f}%" if u["played"] > 0 else "—"
    ach_str = "  ".join(a["name"].split()[0] for a in ach) or "Nema još"
    await ctx.send(embed=emb(
        f"👤  Profil — {target.display_name}",
        None,
        discord.Color.blurple(),
        fields=[
            ("💰 Coins",    f"{u['coins']:,} {COIN}",     True),
            ("🏆 Pobjede",  str(u["wins"]),                True),
            ("🎮 Odigrano", str(u["played"]),              True),
            ("📊 Win rate", wr,                            True),
            ("🔥 Streak",  f"{u.get('streak',0)} dana",   True),
            ("🎁 Items",   str(len(inv)),                  True),
            ("Level & Rang",
             f"Level **{lvl}** — {rank}\n`{bar}` {xp_c}/500 XP", False),
            ("Achievements", ach_str, False),
        ],
        thumbnail=str(target.display_avatar.url)
    ))


@bot.command(name="daily")
async def daily(ctx):
    await ensure_user(ctx.author.id, ctx.author.display_name)
    now  = datetime.utcnow()
    last = await get_daily(ctx.author.id)
    u    = await get_user(ctx.author.id)
    streak = u.get("streak", 0)

    if last:
        last_dt = datetime.fromisoformat(last)
        diff = now - last_dt
        if diff < timedelta(hours=20):
            rem = timedelta(hours=20) - diff
            h = int(rem.total_seconds()) // 3600
            m = (int(rem.total_seconds()) % 3600) // 60
            return await ctx.send(embed=emb(
                "⏰  Daily — Već uzeto",
                f"Sljedeći daily za **{h}h {m}m**.",
                discord.Color.red(),
                fields=[("Trenutni streak", f"🔥 {streak} dana", True)]
            ))
        # Streak reset ako je prošlo više od 48h
        if diff > timedelta(hours=48):
            streak = 0

    streak += 1
    base    = random.randint(200, 600)
    bonus   = min(streak, 30) * 20
    reward  = base + bonus

    await add_coins(ctx.author.id, reward)
    await set_daily(ctx.author.id, now.isoformat(), streak)

    # XP bonus
    lvl_before = get_level(u["xp"])
    await add_played(ctx.author.id, xp=25)
    u2 = await get_user(ctx.author.id)
    lvl_after  = get_level(u2["xp"])

    fields = [
        ("Baza",    f"**{base}** {COIN}",     True),
        ("Streak bonus", f"+**{bonus}** {COIN} (🔥 {streak}d)", True),
        ("Ukupno",  f"**{reward}** {COIN}",   True),
    ]
    if streak in (7, 14, 30, 60, 100):
        extra = streak * 50
        await add_coins(ctx.author.id, extra)
        fields.append(("🎉 Streak Milestone!", f"+**{extra}** {COIN} bonus!", False))

    await ctx.send(embed=emb(
        "🎁  Daily Nagrada",
        f"+**{reward}** {COIN}  •  Vrati se sutra!",
        discord.Color.green(), fields=fields,
        footer=f"Streak: {streak} dana"
    ))

    ch = await get_channel()
    if ch and lvl_after > lvl_before:
        await notify_levelup(ch, ctx.author.id, lvl_before, lvl_after)
    await post_achievements(ch or ctx.channel, ctx.author.id)


@bot.command(name="rad", aliases=["work","posao"])
async def work(ctx):
    await ensure_user(ctx.author.id, ctx.author.display_name)
    now  = datetime.utcnow()
    last = await get_work(ctx.author.id)

    if last:
        last_dt = datetime.fromisoformat(last)
        diff = now - last_dt
        if diff < timedelta(hours=2):
            rem = timedelta(hours=2) - diff
            m = int(rem.total_seconds()) // 60
            return await ctx.send(embed=emb(
                "😴  Trebaš odmor",
                f"Sljedeći rad za **{m} minuta**.",
                discord.Color.orange()
            ))

    jobs = [
        ("👨‍💻 Programirao web stranicu",  (80, 160)),
        ("🎵 DJ na žurci",               (60, 140)),
        ("🚕 Vozač taksija",              (50, 120)),
        ("🍕 Dostavljao pizzu",           (40, 100)),
        ("🏗️ Gradio zgradu",             (90, 180)),
        ("🎨 Crtao portret",             (70, 150)),
        ("📦 Slagao pakete",             (45, 110)),
        ("💇 Frizirao mušterije",         (55, 130)),
        ("🔧 Popravljao auto",            (75, 160)),
        ("📸 Fotografisao vjenčanje",     (100, 200)),
    ]
    job, (mn, mx) = random.choice(jobs)
    earned = random.randint(mn, mx)
    await add_coins(ctx.author.id, earned)
    await set_work(ctx.author.id, now.isoformat())

    await ctx.send(embed=emb(
        "💼  Posao Završen!",
        job,
        discord.Color.from_rgb(80, 180, 80),
        fields=[
            ("Zarada",    f"**{earned}** {COIN}", True),
            ("Cooldown",  "2 sata",               True),
        ]
    ))


# ── Shop ───────────────────────────────────────────────────────────────────────
SHOP_ITEMS = [
    {"id": "shield",    "name": "🛡️ Štit",         "desc": "Zaštita od gubitka na sljedećoj igri", "price": 300},
    {"id": "lucky",     "name": "🍀 Lucky Charm",   "desc": "+10% šanse na slotovima i rulet",      "price": 500},
    {"id": "xp2",       "name": "⚡ XP Booster",    "desc": "2x XP narednih 10 igara",              "price": 400},
    {"id": "deco_rand", "name": "🎨 Random Deko",   "desc": "Nasumična dekoracija za profil",        "price": 200},
    {"id": "avatar_rand","name":"👤 Random Avatar", "desc": "Nasumični avatar frame",                "price": 350},
    {"id": "coins500",  "name": "💰 500 Coina",     "desc": "Direktno na balans",                   "price": 450},
    {"id": "coins1500", "name": "💎 1500 Coina",    "desc": "Direktno na balans (popust!)",          "price": 1200},
]

@bot.command(name="shop", aliases=["prodavnica","store"])
async def shop(ctx, item_id: str = None):
    if item_id is None:
        items_str = "\n".join(
            f"`{it['id']}` — **{it['name']}**  •  {it['price']} {COIN}\n"
            f"  ↳ *{it['desc']}*"
            for it in SHOP_ITEMS
        )
        return await ctx.send(embed=emb(
            "🛒  Shop",
            items_str,
            discord.Color.from_rgb(100, 180, 255),
            footer="Koristi: !shop <id> da kupiš"
        ))

    item = next((it for it in SHOP_ITEMS if it["id"] == item_id), None)
    if item is None:
        return await ctx.send(embed=emb("❌  Nepoznat item",
            "Upisi `!shop` za listu.", discord.Color.red()))

    await ensure_user(ctx.author.id, ctx.author.display_name)
    if not await deduct_coins(ctx.author.id, item["price"]):
        c = await get_coins(ctx.author.id)
        return await ctx.send(embed=emb(
            "❌  Nedovoljno Coina",
            f"Trebaš **{item['price']}** {COIN}. Imaš **{c}** {COIN}.",
            discord.Color.red()
        ))

    # Izvrši kupovinu
    if item["id"] == "deco_rand":
        import random as rnd
        from games import DECORATIONS
        d = rnd.choice(DECORATIONS)
        await add_item(ctx.author.id, "decoration", d)
        extra = f"\nDobijena: **{d}**"
    elif item["id"] == "avatar_rand":
        import random as rnd
        from games import AVATARS
        a = rnd.choice(AVATARS)
        await add_item(ctx.author.id, "avatar", a)
        extra = f"\nDobiven: **{a}**"
    elif item["id"] == "coins500":
        await add_coins(ctx.author.id, 500)
        extra = f"\n+**500** {COIN} dodano na balans"
    elif item["id"] == "coins1500":
        await add_coins(ctx.author.id, 1500)
        extra = f"\n+**1500** {COIN} dodano na balans"
    else:
        await add_item(ctx.author.id, "powerup", item["name"])
        extra = "\nItem dodan u inventar"

    await ctx.send(embed=emb(
        "✅  Kupovina Uspješna!",
        f"**{item['name']}**{extra}",
        discord.Color.green(),
        fields=[("Plaćeno", f"**{item['price']}** {COIN}", True)]
    ))


# ── Top lista ──────────────────────────────────────────────────────────────────
@bot.command(name="top", aliases=["ljestvica","leaderboard","lb"])
async def leaderboard(ctx):
    rows = await get_top(10)
    medals = ["🥇","🥈","🥉"] + [f"`{i}.`" for i in range(4,11)]
    lines  = []
    for i, r in enumerate(rows):
        lvl  = get_level(r.get("xp",0))
        name = r["username"] or f"ID {r['user_id']}"
        lines.append(f"{medals[i]} **{name}** — {r['coins']:,} {COIN}  •  Lv.{lvl}  •  {r['wins']}W")
    await ctx.send(embed=emb(
        "🏆  Top Lista",
        "\n".join(lines) or "Nema podataka.",
        discord.Color.gold(), footer="Sortirano po coinima"
    ))


# ── Inventar ───────────────────────────────────────────────────────────────────
@bot.command(name="inventar", aliases=["inv","inventory"])
async def inventory(ctx, member: discord.Member = None):
    target = member or ctx.author
    await ensure_user(target.id, target.display_name)
    items = await get_inventory(target.id)
    if not items:
        return await ctx.send(embed=emb("🎒  Inventar",
            f"{target.display_name} nema predmeta.", discord.Color.greyple()))
    grouped: dict[str,list] = {}
    for it in items:
        grouped.setdefault(it["item_type"], []).append(it["item_name"])
    labels = {"decoration":"🎨 Dekoracije","avatar":"👤 Avatari",
               "nitro":"✨ Nitro","powerup":"⚡ Pojačanja","role":"🏅 Uloge"}
    fields = []
    for t, names in grouped.items():
        lbl = labels.get(t, t.title())
        val = "\n".join(f"• {n}" for n in names[:10])
        if len(names) > 10: val += f"\n*...i još {len(names)-10}*"
        fields.append((lbl, val, True))
    await ctx.send(embed=emb(
        f"🎒  Inventar — {target.display_name}",
        f"Ukupno **{len(items)}** predmeta",
        discord.Color.purple(), fields=fields
    ))


# ── Transfer ───────────────────────────────────────────────────────────────────
@bot.command(name="transfer", aliases=["daj","give","send"])
async def transfer(ctx, member: discord.Member, amount: int):
    if member.bot or member == ctx.author:
        return await ctx.send("Ne možeš slati sebi ili botu.", delete_after=5)
    if amount <= 0:
        return await ctx.send("Iznos mora biti pozitivan.", delete_after=5)
    await ensure_user(ctx.author.id, ctx.author.display_name)
    await ensure_user(member.id, member.display_name)
    if not await deduct_coins(ctx.author.id, amount):
        c = await get_coins(ctx.author.id)
        return await ctx.send(embed=emb("❌  Transfer",
            f"Nemaš dovoljno. Imaš **{c:,}** {COIN}", discord.Color.red()))
    await add_coins(member.id, amount)
    await ctx.send(embed=emb("💸  Transfer", None, discord.Color.blue(),
        fields=[("Od",    ctx.author.display_name, True),
                ("Za",    member.display_name,     True),
                ("Iznos", f"**{amount:,}** {COIN}", True)]))


# ── Achievements ───────────────────────────────────────────────────────────────
@bot.command(name="achievements", aliases=["ach","nagrade"])
async def achievements(ctx, member: discord.Member = None):
    target = member or ctx.author
    await ensure_user(target.id, target.display_name)
    achs   = await get_achievements(target.id)
    earned = {a["code"] for a in achs}
    all_lines = []
    for code, name in ACHIEVEMENT_DEFS.items():
        mark = "✅" if code in earned else "🔒"
        all_lines.append(f"{mark} {name}")
    await ctx.send(embed=emb(
        f"🏆  Achievements — {target.display_name}",
        "\n".join(all_lines),
        discord.Color.gold(),
        footer=f"Otključano: {len(earned)}/{len(ACHIEVEMENT_DEFS)}"
    ))


# ── Help ───────────────────────────────────────────────────────────────────────
@bot.command(name="help", aliases=["pomoc","?"])
async def help_cmd(ctx):
    await ctx.send(embed=emb(
        "📋  Komande",
        "Igre se pokreću **automatski** u game kanalu.",
        discord.Color.blurple(),
        fields=[
            ("👤 Profil",
             "`!profil` — Profil, level, XP, rang\n"
             "`!balans` — Coins, streak, win rate\n"
             "`!achievements` — Svi achievementi\n"
             "`!inventar` — Predmeti i nagrade", False),
            ("💰 Ekonomija",
             "`!daily` — Dnevna nagrada (streak bonus!)\n"
             "`!rad` — Zarade coins (2h cooldown)\n"
             "`!shop` — Prodavnica pojačanja\n"
             "`!transfer @user <iznos>` — Pošalji coins", False),
            ("🏆 Rang lista",
             "`!top` — Top 10 igrača po coinima", False),
            ("🎮 Automatske igre",
             "Emoji Guess  •  Nastavi Pjesmu  •  Slot Machine\n"
             "Kolo Sreće  •  Rulet  •  Grebalica\n"
             "Lutrija  •  Bingo  •  Mines  •  Jackpot", False),
        ],
        footer="Novi igrači dobivaju 500 coina automatski!"
    ))


# ── Admin komande ──────────────────────────────────────────────────────────────
def is_owner():
    async def pred(ctx):
        return (BOT_OWNER_ID and ctx.author.id == BOT_OWNER_ID) or await bot.is_owner(ctx.author)
    return commands.check(pred)

@bot.command(name="invite", aliases=["pozovi","addbot"])
@is_owner()
async def invite_cmd(ctx):
    perms = discord.Permissions(
        send_messages=True, embed_links=True,
        read_message_history=True, add_reactions=True,
        manage_roles=True, attach_files=True,
        use_external_emojis=True,
    )
    url = discord.utils.oauth_url(bot.user.id, permissions=perms)
    await ctx.send(embed=emb("🔗  Bot Invite Link",
        f"[Klikni ovdje da dodaš bota]({url})",
        discord.Color.blurple()))
    try:
        await ctx.author.send(embed=emb("🔗  Invite Link (DM)",
            f"[Dodaj bota]({url})", discord.Color.blurple()))
    except discord.Forbidden:
        pass

@bot.command(name="stats")
@is_owner()
async def bot_stats(ctx):
    members = sum(g.member_count for g in bot.guilds)
    await ctx.send(embed=emb("📊  Bot Statistike", None, discord.Color.blurple(),
        fields=[("Servera",   str(len(bot.guilds)), True),
                ("Korisnika", str(members),         True),
                ("Game #",    str(game_index),      True),
                ("Running",   str(game_running),    True)]))

@bot.command(name="givecoin")
@is_owner()
async def givecoin(ctx, member: discord.Member, amount: int):
    await ensure_user(member.id, member.display_name)
    await add_coins(member.id, amount)
    await ctx.send(embed=emb("✅  Admin Give",
        f"Dato **{amount}** {COIN} za **{member.display_name}**",
        discord.Color.green()))


# ── Events ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await init_db()
    print(f"[OK] {bot.user} (ID: {bot.user.id})")
    print(f"[OK] Kanal: {GAME_CHANNEL_ID}  |  Owner: {BOT_OWNER_ID}  |  Servera: {len(bot.guilds)}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.playing, name="Auto igre | !help"))
    bot.loop.create_task(run_game_loop())

@bot.event
async def on_member_join(member: discord.Member):
    await ensure_user(member.id, member.display_name)
    ch = await get_channel()
    if ch:
        await ch.send(embed=emb(
            f"👋  Dobrodošao, {member.display_name}!",
            f"Dobio si **500** {COIN} za početak!\n"
            f"Kucaj `!help` za listu komandi.",
            discord.Color.green()
        ))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("Nemaš pristup ovoj komandi.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Nedostaje argument. Kucaj `!help`.", delete_after=8)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Pogrešan argument. Kucaj `!help`.", delete_after=8)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"[CMD ERR] {error}")


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("[ERROR] DISCORD_TOKEN nije postavljen!"); exit(1)
    if not GAME_CHANNEL_ID:
        print("[ERROR] GAME_CHANNEL_ID nije postavljen!"); exit(1)
    bot.run(TOKEN)
