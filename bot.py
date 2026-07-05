"""
Discord Game Bot — Auto-posting game loop.
All games run automatically in the configured channel, one after another.
"""

import discord
from discord.ext import commands, tasks
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
    add_coins, deduct_coins, add_win, add_played,
    get_top, get_inventory, get_daily, set_daily
)
from games import ALL_GAMES

TOKEN           = os.environ.get("DISCORD_TOKEN")
GAME_CHANNEL_ID = int(os.environ.get("GAME_CHANNEL_ID", 0))
GAME_INTERVAL   = int(os.environ.get("GAME_INTERVAL", 180))   # seconds between games

COIN = "🪙"

# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ── Game loop state ────────────────────────────────────────────────────────────
game_index = 0
game_running = False

# ── Helpers ───────────────────────────────────────────────────────────────────
def e(title, desc, color=discord.Color.gold(), *, fields=None, footer=None):
    em = discord.Embed(title=title, description=desc, color=color)
    em.timestamp = datetime.utcnow()
    for f in (fields or []):
        em.add_field(name=f[0], value=f[1], inline=f[2] if len(f) > 2 else True)
    if footer:
        em.set_footer(text=footer)
    return em

async def get_game_channel() -> discord.TextChannel | None:
    ch = bot.get_channel(GAME_CHANNEL_ID)
    if ch is None:
        try:
            ch = await bot.fetch_channel(GAME_CHANNEL_ID)
        except Exception:
            ch = None
    return ch

# ── Auto game loop ─────────────────────────────────────────────────────────────
async def run_game_loop():
    global game_index, game_running
    await bot.wait_until_ready()
    await asyncio.sleep(5)  # short startup delay

    channel = await get_game_channel()
    if channel is None:
        print(f"[ERROR] Kanal {GAME_CHANNEL_ID} nije pronađen! Provjeri GAME_CHANNEL_ID.")
        return

    print(f"[OK] Game loop pokrenut u #{channel.name}")

    # Post welcome banner
    await channel.send(embed=e(
        "🎮 Game Bot je Online!",
        f"Igre kreću automatski svake **{GAME_INTERVAL // 60}** minute!\n\n"
        f"**10 igara u rotaciji:**\n"
        f"😀 Emoji Guess • 🎵 Nastavi Pjesmu • 🎰 Slot Machine\n"
        f"🎡 Kolo Sreće • 🎯 Rulet • 🎟️ Grebalica\n"
        f"🎲 Lutrija • 🎱 Bingo • 💣 Mines • 👑 Jackpot\n\n"
        f"💰 Novi korisnici dobivaju **500** {COIN} na startu!\n"
        f"Upiši `!balans` da vidiš stanje.",
        discord.Color.blurple(),
        footer="🎮 Game Bot • Automatski game loop"
    ))

    shuffle_order = list(range(len(ALL_GAMES)))
    random.shuffle(shuffle_order)

    while True:
        game_running = True
        GameClass = ALL_GAMES[shuffle_order[game_index % len(ALL_GAMES)]]
        game = GameClass()
        game_index += 1

        # Reshuffle when we've gone through all
        if game_index % len(ALL_GAMES) == 0:
            random.shuffle(shuffle_order)

        # Separator between games
        sep = discord.Embed(color=discord.Color.from_rgb(30, 30, 50))
        sep.set_footer(text=f"Sljedeća igra: {game.NAME} • za nekoliko sekundi...")
        await channel.send(embed=sep)
        await asyncio.sleep(8)

        try:
            await game.run(channel)
        except Exception as ex:
            print(f"[ERROR] Game {game.NAME} crashed: {ex}")
            import traceback; traceback.print_exc()

        game_running = False

        # Cooldown between games
        cd = discord.Embed(
            description=f"⏳ Sljedeća igra za **{GAME_INTERVAL}s**...",
            color=discord.Color.from_rgb(40, 40, 60)
        )
        await channel.send(embed=cd)
        await asyncio.sleep(GAME_INTERVAL)

# ── Economy commands ───────────────────────────────────────────────────────────
@bot.command(name="balans", aliases=["balance", "b"])
async def balance(ctx):
    await ensure_user(ctx.author.id, ctx.author.display_name)
    u = await get_user(ctx.author.id)
    level = 1 + u["xp"] // 500
    await ctx.send(embed=e(
        f"💰 Balans — {ctx.author.display_name}",
        f"**{u['coins']:,}** {COIN}",
        discord.Color.gold(),
        fields=[
            ("⭐ XP", f"{u['xp']:,}", True),
            ("🎮 Level", str(level), True),
            ("🏆 Pobjede", str(u["wins"]), True),
            ("🎲 Odigranih", str(u["played"]), True),
        ]
    ))

@bot.command(name="daily")
async def daily(ctx):
    await ensure_user(ctx.author.id, ctx.author.display_name)
    now = datetime.utcnow()
    last_str = await get_daily(ctx.author.id)
    if last_str:
        last = datetime.fromisoformat(last_str)
        if now - last < timedelta(hours=24):
            rem = timedelta(hours=24) - (now - last)
            h = int(rem.total_seconds()) // 3600
            m = (int(rem.total_seconds()) % 3600) // 60
            return await ctx.send(embed=e(
                "⏳ Daily", f"Već si uzeo! Sljedeći za **{h}h {m}m**.", discord.Color.red()
            ))
    reward = random.randint(200, 700)
    await add_coins(ctx.author.id, reward)
    await set_daily(ctx.author.id, now.isoformat())
    await ctx.send(embed=e("🎁 Daily Nagrada!", f"+**{reward}** {COIN}! Vrati se sutra.", discord.Color.green()))

@bot.command(name="top", aliases=["ljestvica", "leaderboard"])
async def leaderboard(ctx):
    rows = await get_top(10)
    medals = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines = []
    for i, row in enumerate(rows):
        name = row["username"] or f"ID {row['user_id']}"
        lines.append(f"{medals[i]} **{name}** — {row['coins']:,} {COIN} | {row['wins']} pobjeda")
    await ctx.send(embed=e(
        "🏆 Top Lista", "\n".join(lines) or "Nema podataka.", discord.Color.gold()
    ))

@bot.command(name="inventar", aliases=["inv"])
async def inventory(ctx, member: discord.Member = None):
    target = member or ctx.author
    await ensure_user(target.id, target.display_name)
    items = await get_inventory(target.id)
    if not items:
        return await ctx.send(embed=e("🎒 Inventar", f"{target.display_name} nema predmeta.", discord.Color.greyple()))
    grouped = {}
    for item in items:
        grouped.setdefault(item["item_type"], []).append(item["item_name"])
    icons = {"decoration": "🎨", "avatar": "🖼️", "nitro": "💜", "role": "🏅"}
    desc = ""
    for t, names in grouped.items():
        desc += f"\n**{icons.get(t,'📦')} {t.title()}**\n" + "\n".join(f"• {n}" for n in names[:10]) + "\n"
    await ctx.send(embed=e(f"🎒 Inventar — {target.display_name}", desc.strip(), discord.Color.purple()))

@bot.command(name="transfer", aliases=["daj", "give"])
async def transfer(ctx, member: discord.Member, amount: int):
    if member.bot or member == ctx.author:
        return await ctx.send("❌ Ne možeš slati sebi ili botu!")
    if amount <= 0:
        return await ctx.send("❌ Iznos mora biti pozitivan!")
    await ensure_user(ctx.author.id, ctx.author.display_name)
    await ensure_user(member.id, member.display_name)
    ok = await deduct_coins(ctx.author.id, amount)
    if not ok:
        coins = await get_coins(ctx.author.id)
        return await ctx.send(f"❌ Nemaš dovoljno! Imaš **{coins:,}** {COIN}")
    await add_coins(member.id, amount)
    await ctx.send(embed=e(
        "💸 Transfer",
        f"**{ctx.author.display_name}** → {member.mention}\n**{amount:,}** {COIN}",
        discord.Color.blue()
    ))

@bot.command(name="help", aliases=["pomoc"])
async def help_cmd(ctx):
    await ctx.send(embed=e(
        "📖 Bot Komande",
        "Igre se pokreću **automatski** u ovom kanalu!\nSamo klikni dugmad na embedu.",
        discord.Color.blurple(),
        fields=[
            ("💰 Ekonomija", (
                "`!balans` — Tvoje stanje\n"
                "`!daily` — Dnevna nagrada (200-700 🪙)\n"
                "`!top` — Ljestvica bogatih\n"
                "`!inventar [@user]` — Nagrade u inventaru\n"
                "`!transfer @user <iznos>` — Pošalji coinse"
            ), False),
            ("🎮 Igre (automatske)", (
                "😀 **Emoji Guess** — Pogodi šta emoji prikazuju\n"
                "🎵 **Nastavi Pjesmu** — Jala Brat, Buba Corelli i još\n"
                "🎰 **Slot Machine** — Kupi i zavrti reele\n"
                "🎡 **Kolo Sreće** — Animirani spin, razne nagrade\n"
                "🎯 **Rulet** — Okladi se na boju/broj, gledaj kuglu\n"
                "🎟️ **Grebalica** — Kupi i ogrebi odmah!\n"
                "🎲 **Lutrija** — Kupi listić, izvlačenje 6 brojeva\n"
                "🎱 **Bingo** — Multiplayer, 15 brojeva, ko prvi pobijedi\n"
                "💣 **Mines** — Grid 5×5, otvori polja bez mina\n"
                "👑 **Jackpot** — Svi ulažu, jedan uzima sve!"
            ), False),
        ],
        footer="🎮 Novi korisnici dobivaju 500 🪙 automatski!"
    ))

# ── Events ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Prijavljen kao {bot.user} (ID: {bot.user.id})")
    print(f"📢 Game Channel ID: {GAME_CHANNEL_ID}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="🎮 Auto igre | !help"
        )
    )
    bot.loop.create_task(run_game_loop())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Nedostaje argument! `!help`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Pogrešan argument! `!help`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"[CMD ERROR] {error}")

@bot.event
async def on_member_join(member: discord.Member):
    await ensure_user(member.id, member.display_name)
    # Welcome message in game channel
    ch = await get_game_channel()
    if ch:
        await ch.send(embed=e(
            f"👋 Dobrodošao, {member.display_name}!",
            f"Dobio si **500** {COIN} za početak!\nPiši `!help` za komande.",
            discord.Color.green()
        ))

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("[ERROR] DISCORD_TOKEN nije postavljen!")
        exit(1)
    if not GAME_CHANNEL_ID:
        print("[ERROR] GAME_CHANNEL_ID nije postavljen!")
        exit(1)
    bot.run(TOKEN)
