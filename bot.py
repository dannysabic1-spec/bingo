"""
Discord Game Bot — poboljšana verzija s čišćim embedima,
pravim animiranim izvlačenjem i komandom za pozivanje bota.
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
GAME_INTERVAL   = int(os.environ.get("GAME_INTERVAL", 180))

# ID naloga koji smije koristiti admin komande (postavi na svoj user ID)
BOT_OWNER_ID    = int(os.environ.get("BOT_OWNER_ID", 0))

COIN = "🪙"

# ── Bot setup ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ── Stanje game loopa ──────────────────────────────────────────────────────────
game_index = 0
game_running = False


# ── Embed helper ───────────────────────────────────────────────────────────────
def emb(title: str, desc: str = "", color=discord.Color.gold(), *, fields=None, footer=None) -> discord.Embed:
    em = discord.Embed(title=title, description=desc or None, color=color)
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
    await asyncio.sleep(5)

    channel = await get_game_channel()
    if channel is None:
        print(f"[ERROR] Kanal {GAME_CHANNEL_ID} nije pronaden! Provjeri GAME_CHANNEL_ID.")
        return

    print(f"[OK] Game loop pokrenut u #{channel.name}")

    game_list = "\n".join(f"  {g.NAME}" for g in [cls() for cls in ALL_GAMES])
    await channel.send(
        embed=emb(
            "Game Bot je Online!",
            f"Igre krecu automatski svake **{GAME_INTERVAL // 60}** minute.\n\n"
            f"**10 igara u rotaciji:**\n"
            f"```\n{game_list}\n```\n"
            f"Novi korisnici dobivaju **500** {COIN} na startu.\n"
            f"Upisi `!balans` da vidis stanje.",
            discord.Color.blurple(),
            footer="Game Bot  •  Automatski game loop"
        )
    )

    shuffle_order = list(range(len(ALL_GAMES)))
    random.shuffle(shuffle_order)

    while True:
        game_running = True
        GameClass = ALL_GAMES[shuffle_order[game_index % len(ALL_GAMES)]]
        game = GameClass()
        game_index += 1

        if game_index % len(ALL_GAMES) == 0:
            random.shuffle(shuffle_order)

        await channel.send(
            embed=emb(
                f"Sljedeca igra: {game.NAME}",
                "Krece za nekoliko sekundi...",
                discord.Color.from_rgb(30, 30, 50)
            )
        )
        await asyncio.sleep(8)

        try:
            await game.run(channel)
        except Exception as ex:
            print(f"[ERROR] Game {game.NAME} crashed: {ex}")
            import traceback
            traceback.print_exc()

        game_running = False

        minutes = GAME_INTERVAL // 60
        seconds = GAME_INTERVAL % 60
        wait_str = f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
        await channel.send(
            embed=emb(
                "Pauza",
                f"Sljedeca igra za **{wait_str}**.",
                discord.Color.from_rgb(40, 40, 60)
            )
        )
        await asyncio.sleep(GAME_INTERVAL)


# ── Economy komande ────────────────────────────────────────────────────────────
@bot.command(name="balans", aliases=["balance", "b"])
async def balance(ctx):
    await ensure_user(ctx.author.id, ctx.author.display_name)
    u = await get_user(ctx.author.id)
    level = 1 + u["xp"] // 500
    winrate = f"{u['wins'] / u['played'] * 100:.0f}%" if u["played"] > 0 else "—"
    await ctx.send(
        embed=emb(
            f"Balans — {ctx.author.display_name}",
            f"**{u['coins']:,}** {COIN}",
            discord.Color.gold(),
            fields=[
                ("XP",        f"{u['xp']:,}",  True),
                ("Level",     str(level),       True),
                ("Pobjede",   str(u["wins"]),   True),
                ("Odigranih", str(u["played"]), True),
                ("Win rate",  winrate,          True),
            ]
        )
    )


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
            return await ctx.send(
                embed=emb(
                    "Daily — vec uzeto",
                    f"Sljedeci daily za **{h}h {m}m**.",
                    discord.Color.red()
                )
            )
    reward = random.randint(200, 700)
    await add_coins(ctx.author.id, reward)
    await set_daily(ctx.author.id, now.isoformat())
    await ctx.send(
        embed=emb(
            "Daily Nagrada",
            f"+**{reward}** {COIN}\n\nVrati se sutra!",
            discord.Color.green()
        )
    )


@bot.command(name="top", aliases=["ljestvica", "leaderboard"])
async def leaderboard(ctx):
    rows = await get_top(10)
    medals = ["1.", "2.", "3."] + [f"{i}." for i in range(4, 11)]
    lines = []
    for i, row in enumerate(rows):
        name = row["username"] or f"ID {row['user_id']}"
        lines.append(f"{medals[i]} **{name}** — {row['coins']:,} {COIN}  |  {row['wins']} pobjeda")
    await ctx.send(
        embed=emb(
            "Top Lista",
            "\n".join(lines) or "Nema podataka.",
            discord.Color.gold()
        )
    )


@bot.command(name="inventar", aliases=["inv"])
async def inventory(ctx, member: discord.Member = None):
    target = member or ctx.author
    await ensure_user(target.id, target.display_name)
    items = await get_inventory(target.id)
    if not items:
        return await ctx.send(
            embed=emb("Inventar", f"{target.display_name} nema predmeta.", discord.Color.greyple())
        )
    grouped: dict[str, list] = {}
    for item in items:
        grouped.setdefault(item["item_type"], []).append(item["item_name"])
    type_labels = {"decoration": "Dekoracije", "avatar": "Avatari", "nitro": "Nitro", "role": "Uloge"}
    fields = []
    for t, names in grouped.items():
        label = type_labels.get(t, t.title())
        value = "\n".join(f"• {n}" for n in names[:10])
        fields.append((label, value, False))
    await ctx.send(
        embed=emb(f"Inventar — {target.display_name}", None, discord.Color.purple(), fields=fields)
    )


@bot.command(name="transfer", aliases=["daj", "give"])
async def transfer(ctx, member: discord.Member, amount: int):
    if member.bot or member == ctx.author:
        return await ctx.send("Ne mozes slati sebi ili botu.")
    if amount <= 0:
        return await ctx.send("Iznos mora biti pozitivan.")
    await ensure_user(ctx.author.id, ctx.author.display_name)
    await ensure_user(member.id, member.display_name)
    ok = await deduct_coins(ctx.author.id, amount)
    if not ok:
        coins = await get_coins(ctx.author.id)
        return await ctx.send(
            embed=emb("Transfer — neuspjelo", f"Nemas dovoljno. Imas **{coins:,}** {COIN}", discord.Color.red())
        )
    await add_coins(member.id, amount)
    await ctx.send(
        embed=emb(
            "Transfer",
            None,
            discord.Color.blue(),
            fields=[
                ("Od",    ctx.author.display_name, True),
                ("Za",    member.display_name,     True),
                ("Iznos", f"**{amount:,}** {COIN}", True),
            ]
        )
    )


@bot.command(name="help", aliases=["pomoc"])
async def help_cmd(ctx):
    await ctx.send(
        embed=emb(
            "Bot Komande",
            "Igre se pokrecuju **automatski** u game kanalu. Samo klikni dugmad!",
            discord.Color.blurple(),
            fields=[
                ("Ekonomija", (
                    "`!balans` — Tvoje stanje i statistike\n"
                    "`!daily` — Dnevna nagrada (200–700 coina)\n"
                    "`!top` — Ljestvica bogatih\n"
                    "`!inventar [@user]` — Nagrade u inventaru\n"
                    "`!transfer @user <iznos>` — Posalji coinse"
                ), False),
                ("Igre (automatske)", (
                    "Emoji Guess  •  Nastavi Pjesmu  •  Slot Machine\n"
                    "Kolo Srece  •  Rulet  •  Grebalica\n"
                    "Lutrija  •  Bingo  •  Mines  •  Jackpot Event"
                ), False),
            ],
            footer="Novi korisnici dobivaju 500 coina automatski!"
        )
    )


# ── Admin komande ──────────────────────────────────────────────────────────────
def is_owner():
    async def predicate(ctx):
        if BOT_OWNER_ID and ctx.author.id == BOT_OWNER_ID:
            return True
        if await bot.is_owner(ctx.author):
            return True
        return False
    return commands.check(predicate)


@bot.command(name="invite", aliases=["pozovi", "addbot"])
@is_owner()
async def invite_cmd(ctx):
    """Generira link za dodavanje bota na drugi server (samo za owner)."""
    perms = discord.Permissions(
        send_messages=True,
        embed_links=True,
        read_message_history=True,
        add_reactions=True,
        manage_roles=True,
        attach_files=True,
        use_external_emojis=True,
    )
    url = discord.utils.oauth_url(bot.user.id, permissions=perms)
    await ctx.send(
        embed=emb(
            "Bot Invite Link",
            f"[Klikni ovdje da dodas bota na server]({url})\n\n"
            f"Potrebne permisije su vec postavljene u linku.",
            discord.Color.blurple(),
            footer="Ovaj link je vidljiv samo tebi u DM-u"
        ),
        ephemeral=False
    )
    # Posalji i u DM radi sigurnosti
    try:
        await ctx.author.send(
            embed=emb(
                "Bot Invite Link (privatno)",
                f"[Dodaj bota na server]({url})",
                discord.Color.blurple()
            )
        )
    except discord.Forbidden:
        pass


@bot.command(name="stats", aliases=["info"])
@is_owner()
async def bot_stats(ctx):
    """Statistike bota (samo za owner)."""
    guilds = len(bot.guilds)
    total_members = sum(g.member_count for g in bot.guilds)
    await ctx.send(
        embed=emb(
            "Bot Statistike",
            None,
            discord.Color.blurple(),
            fields=[
                ("Serveri",   str(guilds),        True),
                ("Korisnici", str(total_members),  True),
                ("Game index", str(game_index),    True),
                ("Game running", str(game_running), True),
            ]
        )
    )


# ── Events ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await init_db()
    print(f"[OK] Prijavljen kao {bot.user} (ID: {bot.user.id})")
    print(f"[OK] Game Channel ID: {GAME_CHANNEL_ID}")
    print(f"[OK] Bot Owner ID: {BOT_OWNER_ID}")
    print(f"[OK] Servera: {len(bot.guilds)}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="Auto igre | !help"
        )
    )
    bot.loop.create_task(run_game_loop())


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("Nemas pristup ovoj komandi.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Nedostaje argument. `!help`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Pogresan argument. `!help`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"[CMD ERROR] {error}")


@bot.event
async def on_member_join(member: discord.Member):
    await ensure_user(member.id, member.display_name)
    ch = await get_game_channel()
    if ch:
        await ch.send(
            embed=emb(
                f"Dobrodosao, {member.display_name}!",
                f"Dobio si **500** {COIN} za pocetak.\nUpisi `!help` za komande.",
                discord.Color.green()
            )
        )


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("[ERROR] DISCORD_TOKEN nije postavljen!")
        exit(1)
    if not GAME_CHANNEL_ID:
        print("[ERROR] GAME_CHANNEL_ID nije postavljen!")
        exit(1)
    bot.run(TOKEN)
