"""
All 10 auto-posting games with Discord button Views.
Each game class has:
  - build_lobby_embed()  → initial embed shown when game opens
  - a View with buttons (join / buy ticket / spin / etc.)
  - run(channel) async   → full game lifecycle (post, animate, result)
"""

import discord
import asyncio
import random
from datetime import datetime
from database import (
    ensure_user, get_coins, add_coins, deduct_coins,
    add_win, add_played, add_item, get_top
)

COIN = "🪙"
TICK = 60          # seconds players have to join
RESULT_DELAY = 3   # seconds between animation frames

# ── prize tables ──────────────────────────────────────────────────────────────
DECORATIONS = [
    "🌟 Zlatna Zvijezda", "🔥 Vatreni Efekt", "❄️ Ledeni Efekt",
    "🌈 Rainbow Aura", "👑 Kraljevska Kruna", "⚡ Munja Efekt",
    "🦋 Butterfly Frame", "💫 Stardust Efekt", "🎭 Maskerada Okvir",
]
AVATARS = [
    "🐉 Zmaj Avatar", "🦁 Lav Avatar", "🤖 Cyber Avatar",
    "🧙 Čarobnjak Avatar", "🦊 Lisica Avatar", "🐺 Vuk Avatar",
    "🔮 Mistik Avatar", "🌊 Okean Avatar",
]
NITRO = ["💜 1 Mesec Nitro Classic", "🚀 1 Mesec Nitro Boost", "🎁 Nitro Gift Link"]

def rand_prize(tier="common"):
    if tier == "legendary":
        item = random.choice(NITRO)
        return "nitro", item
    if tier == "rare":
        if random.random() < 0.5:
            return "avatar", random.choice(AVATARS)
        return "decoration", random.choice(DECORATIONS)
    return "decoration", random.choice(DECORATIONS)

def e(title, desc, color=discord.Color.gold(), *, fields=None, footer=None):
    em = discord.Embed(title=title, description=desc, color=color)
    em.timestamp = datetime.utcnow()
    for f in (fields or []):
        em.add_field(name=f[0], value=f[1], inline=f[2] if len(f) > 2 else True)
    if footer:
        em.set_footer(text=footer)
    return em

# ─────────────────────────────────────────────────────────────────────────────
# GAME 1 — 🎱 BINGO
# ─────────────────────────────────────────────────────────────────────────────
class BingoView(discord.ui.View):
    TICKET_COST = 80

    def __init__(self):
        super().__init__(timeout=TICK)
        self.players: dict[int, list[int]] = {}   # user_id → card (15 numbers)
        self.pot = 0
        self.closed = False

    @discord.ui.button(label=f"🎟️ Kupi Listić (80 🪙)", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("⏰ Prijave su zatvorene!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("✅ Već imaš listić!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, self.TICKET_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"❌ Nemaš dovoljno coina! Imaš **{coins}** {COIN}", ephemeral=True
            )
        card = sorted(random.sample(range(1, 76), 15))
        self.players[uid] = card
        self.pot += self.TICKET_COST
        card_str = " | ".join(f"**{n}**" for n in card)
        await interaction.response.send_message(
            f"🎟️ Tvoj Bingo listić:\n{card_str}\n\n💰 Pot: **{self.pot}** {COIN}", ephemeral=True
        )

class BingoGame:
    NAME = "🎱 Bingo"
    COLOR = discord.Color.blue()

    async def run(self, channel: discord.TextChannel):
        view = BingoView()
        em = e(
            "🎱 BINGO — Kupovina Listića",
            f"Klik na dugme da kupiš listić za **{BingoView.TICKET_COST}** {COIN}!\n\n"
            f"Bot će vući brojeve 1–75. Ko prvi označi svih **15** brojeva — pobijedi!\n\n"
            f"⏳ Prijave traju **{TICK} sekundi**.",
            self.COLOR,
            footer="🎱 Bingo • Listić: 80 coina"
        )
        msg = await channel.send(embed=em, view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if len(view.players) < 2:
            await msg.edit(embed=e("🎱 Bingo — Otkazano", "Premalo igrača (min 2). Pot vraćen.", discord.Color.red()), view=None)
            for uid in view.players:
                await add_coins(uid, BingoView.TICKET_COST)
            return

        # Draw numbers
        pool = list(range(1, 76))
        random.shuffle(pool)
        marked: dict[int, set] = {uid: set() for uid in view.players}
        called = []
        winner_uid = None

        draw_em = e("🎱 Bingo — Izvlačenje!", f"Igrači: **{len(view.players)}** | Pot: **{view.pot}** {COIN}", self.COLOR)
        draw_msg = await channel.send(embed=draw_em)

        for num in pool:
            called.append(num)
            for uid, card in view.players.items():
                if num in card:
                    marked[uid].add(num)
                if len(marked[uid]) >= len(view.players[uid]):
                    winner_uid = uid
                    break

            last10 = " ".join(f"**{n}**" if n == num else str(n) for n in called[-10:])
            progress = "\n".join(
                f"<@{uid}>: {len(marked[uid])}/{len(view.players[uid])} oznaka"
                for uid in view.players
            )
            updated = e(
                f"🎱 Bingo — Broj: **{num}**",
                f"Zadnjih 10: {last10}\n\n{progress}",
                self.COLOR,
                footer=f"Izvučeno: {len(called)}/75"
            )
            await draw_msg.edit(embed=updated)
            if winner_uid:
                break
            await asyncio.sleep(4)

        if winner_uid:
            await add_coins(winner_uid, view.pot)
            await add_win(winner_uid, 80)
            _, item = rand_prize("rare")
            await add_item(winner_uid, "decoration", item)
            result = e(
                "🎉 BINGO! Pobjednik!",
                f"<@{winner_uid}> je označio sve brojeve!\n\n"
                f"💰 Dobitak: **{view.pot}** {COIN}\n"
                f"🎁 Bonus nagrada: **{item}**",
                discord.Color.green()
            )
        else:
            result = e("🎱 Bingo", "Niko nije pobijedio!", discord.Color.greyple())

        for uid in view.players:
            await add_played(uid)
        await draw_msg.edit(embed=result)
        await asyncio.sleep(10)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 2 — 🎡 KOLO SREĆE
# ─────────────────────────────────────────────────────────────────────────────
WHEEL_SEGMENTS = [
    ("💀 BANKROT",    0,    "bankrot"),
    ("🪙 100",      100,    "coins"),
    ("🪙 250",      250,    "coins"),
    ("🪙 500",      500,    "coins"),
    ("🪙 1000",    1000,    "coins"),
    ("🪙 50",        50,    "coins"),
    ("🎨 Dekoracija", 0,   "decoration"),
    ("🖼️ Avatar",   0,     "avatar"),
    ("🪙 2000",    2000,    "coins"),
    ("💜 NITRO!",    0,    "nitro"),
    ("🪙 750",      750,    "coins"),
    ("❌ Ništa",     0,    "nothing"),
]
WHEEL_WEIGHTS = [2, 10, 9, 6, 3, 12, 5, 4, 1, 1, 5, 8]

SPIN_COST = 60

def wheel_visual(highlight: int) -> str:
    segs = [s[0] for s in WHEEL_SEGMENTS]
    lines = []
    for i, seg in enumerate(segs):
        arrow = " ◄━━ 🎯" if i == highlight else ""
        lines.append(f"  {'┃' if i != highlight else '▶'} {seg}{arrow}")
    return "```\n" + "\n".join(lines) + "\n```"

class WheelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.spinners: list[int] = []
        self.closed = False

    @discord.ui.button(label=f"🎡 Zavrti Kolo (60 🪙)", style=discord.ButtonStyle.blurple)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("⏰ Kolo je zatvoreno!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.spinners:
            return await interaction.response.send_message("✅ Već si prijavljeni!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, SPIN_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"❌ Trebaš **{SPIN_COST}** {COIN}! Imaš **{coins}** {COIN}", ephemeral=True
            )
        self.spinners.append(uid)
        await interaction.response.send_message("✅ Prijavljen! Čekaj spin...", ephemeral=True)

class WheelGame:
    NAME = "🎡 Kolo Sreće"
    COLOR = discord.Color.purple()

    async def run(self, channel: discord.TextChannel):
        view = WheelView()
        em = e(
            "🎡 KOLO SREĆE — Prijavi Se!",
            f"Klikni dugme da se prijaviš za **{SPIN_COST}** {COIN}!\n\n"
            f"Svaki igrač dobiva svoj spin — kolo se vrti i otkriva nagradu!\n"
            f"Moguće nagrade: coini, dekoracije, avatari, pa čak i **💜 NITRO**!\n\n"
            f"⏳ Prijave traju **{TICK} sekundi**.",
            self.COLOR,
            footer="🎡 Kolo Sreće • Ulaznica: 60 coina"
        )
        msg = await channel.send(embed=em, view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.spinners:
            await msg.edit(embed=e("🎡 Kolo Sreće", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        results = []
        for uid in view.spinners:
            # Animate spin
            spin_msg = await channel.send(embed=e("🎡 Kolo se vrti...", "⠋⠙⠸⠴⠦⠇", self.COLOR))
            prev = -1
            for _ in range(8):
                pos = random.randint(0, len(WHEEL_SEGMENTS) - 1)
                while pos == prev:
                    pos = random.randint(0, len(WHEEL_SEGMENTS) - 1)
                prev = pos
                await spin_msg.edit(embed=e("🎡 Kolo se vrti...", wheel_visual(pos), self.COLOR))
                await asyncio.sleep(0.6)

            # Final result
            segment = random.choices(WHEEL_SEGMENTS, weights=WHEEL_WEIGHTS)[0]
            label, amount, stype = segment
            final_pos = WHEEL_SEGMENTS.index(segment)
            await spin_msg.edit(embed=e("🎡 Kolo stalo!", wheel_visual(final_pos), self.COLOR))
            await asyncio.sleep(1)

            if stype == "bankrot":
                lost = min(await get_coins(uid), random.randint(50, 300))
                await add_coins(uid, -lost)
                desc = f"<@{uid}> → **{label}** 💀\nGubiš **{lost}** {COIN}!"
                color = discord.Color.dark_red()
            elif stype == "coins":
                await add_coins(uid, amount)
                desc = f"<@{uid}> → **{label}**\n💰 +**{amount}** {COIN}!"
                color = discord.Color.green()
            elif stype in ("decoration", "avatar", "nitro"):
                tier = "legendary" if stype == "nitro" else "rare" if stype == "avatar" else "common"
                rtype, item = rand_prize(tier)
                await add_item(uid, rtype, item)
                desc = f"<@{uid}> → **{label}**\n🎁 **{item}**!"
                color = discord.Color.blurple()
            else:
                desc = f"<@{uid}> → **{label}**\nNažalost, ništa..."
                color = discord.Color.greyple()

            await add_played(uid)
            result_em = e("🎡 Rezultat Spina!", desc, color)
            await spin_msg.edit(embed=result_em)
            results.append(desc)
            await asyncio.sleep(3)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 3 — 🎰 SLOT MACHINE
# ─────────────────────────────────────────────────────────────────────────────
REELS = ["🍒", "🍋", "🍇", "⭐", "💎", "🔔", "7️⃣", "🃏", "🌟", "🍀"]
JACKPOTS = {
    ("7️⃣","7️⃣","7️⃣"): (20, "legendary"),
    ("💎","💎","💎"): (15, "rare"),
    ("⭐","⭐","⭐"): (10, "common"),
    ("🌟","🌟","🌟"): (8, "common"),
    ("🍀","🍀","🍀"): (7, "common"),
    ("🔔","🔔","🔔"): (5, "common"),
    ("🍇","🍇","🍇"): (4, "common"),
    ("🍋","🍋","🍋"): (3, "common"),
    ("🍒","🍒","🍒"): (2, "common"),
}
SLOT_COST = 50

class SlotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.players: set[int] = set()
        self.closed = False

    @discord.ui.button(label="🎰 Zaigraj (50 🪙)", style=discord.ButtonStyle.green)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("⏰ Slot je zatvoren!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("✅ Već si prijavljen!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, SLOT_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"❌ Trebaš **{SLOT_COST}** {COIN}! Imaš **{coins}**", ephemeral=True
            )
        self.players.add(uid)
        await interaction.response.send_message("🎰 Prijavljen! Čekaj vrtnju...", ephemeral=True)

class SlotGame:
    NAME = "🎰 Slot Machine"
    COLOR = discord.Color.orange()

    async def run(self, channel: discord.TextChannel):
        view = SlotView()
        em = e(
            "🎰 SLOT MACHINE — Zaigraj!",
            f"Klikni dugme i uloži **{SLOT_COST}** {COIN}!\n\n"
            f"```\n"
            f"[ 7️⃣ | 7️⃣ | 7️⃣ ] → x20 + NITRO 💜\n"
            f"[ 💎 | 💎 | 💎 ] → x15 + Nagrada\n"
            f"[ ⭐ | ⭐ | ⭐ ] → x10\n"
            f"[ XX | XX | XX ] → x2-8\n"
            f"[ 2 ista ]       → x1.5\n"
            f"```\n"
            f"⏳ Prijave: **{TICK}s**",
            self.COLOR,
            footer="🎰 Slot Machine • Ulog: 50 coina"
        )
        msg = await channel.send(embed=em, view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.players:
            await msg.edit(embed=e("🎰 Slot", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        await msg.edit(embed=e("🎰 Slot Machine", "Vrtnja počinje...", self.COLOR), view=None)

        for uid in view.players:
            # Animate reels
            frames = []
            for _ in range(6):
                r = [random.choice(REELS) for _ in range(3)]
                frames.append(r)

            spin_em = e("🎰 Vrtim...", f"[ {'  |  '.join(frames[0])} ]", self.COLOR)
            sm = await channel.send(embed=spin_em)
            for frame in frames[1:]:
                await asyncio.sleep(0.5)
                await sm.edit(embed=e("🎰 Vrtim...", f"[ {'  |  '.join(frame)} ]", self.COLOR))

            # Final spin
            final = tuple(random.choice(REELS) for _ in range(3))
            await asyncio.sleep(0.5)
            display = f"[ {'  |  '.join(final)} ]"

            jackpot = JACKPOTS.get(final)
            if jackpot:
                mult, tier = jackpot
                winnings = SLOT_COST * mult
                await add_coins(uid, winnings)
                await add_win(uid, 60)
                rtype, item = rand_prize(tier)
                await add_item(uid, rtype, item)
                result = (
                    f"**{display}**\n\n"
                    f"🎉 **JACKPOT x{mult}!** <@{uid}>\n"
                    f"💰 +**{winnings}** {COIN}\n"
                    f"🎁 **{item}**"
                )
                color = discord.Color.gold()
            elif len(set(final)) < 3:
                winnings = int(SLOT_COST * 1.5)
                await add_coins(uid, winnings)
                await add_played(uid)
                result = f"**{display}**\n\n🔸 Dva ista! <@{uid}> +**{winnings}** {COIN}"
                color = discord.Color.yellow()
            else:
                await add_played(uid)
                result = f"**{display}**\n\n❌ <@{uid}> — nema podudaranja, -{SLOT_COST} {COIN}"
                color = discord.Color.red()

            await sm.edit(embed=e("🎰 Rezultat!", result, color))
            await asyncio.sleep(4)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 4 — 🎵 KVIZ: NASTAVI PJESMU
# ─────────────────────────────────────────────────────────────────────────────
SONGS = [
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Pilula",
        "lyric": "\"Sipam ti pilulu u čašu vina, volim te ko što voli se Bosna i Hercegovina...\"",
        "answer": ["pilula"],
    },
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Limuzina",
        "lyric": "\"Doći ću po tebe, ko što kaže pjesma, u crnoj ___ kroz grad...\"",
        "answer": ["limuzina", "limuzi"],
    },
    {
        "artist": "Jala Brat",
        "title": "Žvaka",
        "lyric": "\"Žvačem ___, gledam u tavan, nema sna, sutra novo jutro, nov' dan...\"",
        "answer": ["žvaka", "zvaka"],
    },
    {
        "artist": "Buba Corelli",
        "title": "Ferrari",
        "lyric": "\"Vozim ___, puna kesa, kažu da sam lud, ali to je samo stil mog života...\"",
        "answer": ["ferrari", "ferari"],
    },
    {
        "artist": "Jala Brat",
        "title": "Litar Krvi",
        "lyric": "\"Dajem ___ za tebe, to je ljubav prava, niko drugi ne zna što to znači...\"",
        "answer": ["litar krvi", "litar", "krvi"],
    },
    {
        "artist": "Buba Corelli & Jala Brat",
        "title": "Kuna Pela",
        "lyric": "\"___, ___ — letiš kao pčela, zarađuješ kunu, srce moje voli tebe cela...\"",
        "answer": ["kuna pela", "kuna", "pela"],
    },
    {
        "artist": "Jala Brat",
        "title": "Golubica",
        "lyric": "\"Moja ___ bijela, leti visoko iznad grada, samo da si sretna...\"",
        "answer": ["golubica"],
    },
    {
        "artist": "Buba Corelli",
        "title": "Sjena",
        "lyric": "\"Pratim te ko ___, kud god kreneš, tu sam ja, ne mogu bez tebe...\"",
        "answer": ["sjena", "siena"],
    },
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Novac i Zavist",
        "lyric": "\"___ i zavist, to je njihov problem, mi samo gledamo naprijed...\"",
        "answer": ["novac", "novac i zavist"],
    },
    {
        "artist": "Jala Brat",
        "title": "Šampanjac",
        "lyric": "\"Otvori ___, slavimo večeras, sve je moguće kad si pored mene...\"",
        "answer": ["šampanjac", "sampanjac", "sampanjac"],
    },
    {
        "artist": "Buba Corelli",
        "title": "Igra",
        "lyric": "\"Ovo je samo ___, ne uzimaj srcu blizu, znaš da nisam tvoj tip...\"",
        "answer": ["igra"],
    },
    {
        "artist": "Jala Brat",
        "title": "Dijamant",
        "lyric": "\"Ti si moj ___, rijetka, skupa, ne mijenjam te ni za što...\"",
        "answer": ["dijamant"],
    },
]

QUIZ_REWARD = 300
QUIZ_TIME = 60

class QuizGame:
    NAME = "🎵 Nastavi Pjesmu"
    COLOR = discord.Color.from_rgb(255, 100, 200)

    async def run(self, channel: discord.TextChannel):
        song = random.choice(SONGS)
        winner_uid = None
        winner_answer = None

        em = e(
            f"🎵 NASTAVI PJESMU — {song['artist']}",
            f"{song['lyric']}\n\n"
            f"👆 Napiši naziv pjesme u chat!\n"
            f"✅ Nagrada: **{QUIZ_REWARD}** {COIN}\n"
            f"⏳ Imate **{QUIZ_TIME} sekundi**!",
            self.COLOR,
            footer=f"🎵 Kviz • {song['artist']} • Nagrada: {QUIZ_REWARD} coina"
        )
        msg = await channel.send(embed=em)

        def check(m: discord.Message):
            return (
                m.channel.id == channel.id
                and not m.author.bot
                and any(a in m.content.lower() for a in song["answer"])
            )

        try:
            answer_msg = await channel.bot.wait_for("message", timeout=QUIZ_TIME, check=check)
            winner_uid = answer_msg.author.id
            winner_answer = answer_msg.content
        except asyncio.TimeoutError:
            pass

        if winner_uid:
            await ensure_user(winner_uid, answer_msg.author.display_name)
            await add_coins(winner_uid, QUIZ_REWARD)
            await add_win(winner_uid, 40)
            result = e(
                "🎵 Tačan Odgovor!",
                f"🏆 <@{winner_uid}> je tačno odgovorio!\n"
                f"✉️ Odgovor: **\"{winner_answer}\"**\n"
                f"🎯 Traženo: **{song['title']}**\n\n"
                f"💰 +**{QUIZ_REWARD}** {COIN}",
                discord.Color.green(),
                footer=f"🎵 {song['artist']} — {song['title']}"
            )
        else:
            result = e(
                "⏰ Vreme Isteklo!",
                f"Niko nije pogodio pjesmu.\n\n"
                f"🎯 Odgovor je bio: **{song['title']}**\n"
                f"🎤 Izvođač: **{song['artist']}**",
                discord.Color.red(),
                footer=f"🎵 {song['artist']} — {song['title']}"
            )
        await msg.edit(embed=result)
        await asyncio.sleep(8)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 5 — 🎯 RULET (animated)
# ─────────────────────────────────────────────────────────────────────────────
ROULETTE_NUMBERS = list(range(0, 37))
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def roulette_color(n):
    if n == 0: return "🟢"
    return "🔴" if n in RED_NUMBERS else "⚫"

def roulette_wheel_art(ball_pos: int) -> str:
    nums = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
    size = len(nums)
    # Show 9 numbers around ball position
    start = (ball_pos - 4) % size
    segment = []
    for i in range(9):
        idx = (start + i) % size
        n = nums[idx]
        col = roulette_color(n)
        if i == 4:
            segment.append(f"**[{col}{n}]**")
        else:
            segment.append(f"{col}{n}")
    top_row = " ".join(segment[:4])
    mid = segment[4]
    bot_row = " ".join(segment[5:])
    return (
        f"```\n"
        f"┌────────────────────────────┐\n"
        f"│  {top_row:<26}│\n"
        f"│  ↓ KUGLA → {mid:<14} │\n"
        f"│  {bot_row:<26}│\n"
        f"└────────────────────────────┘\n"
        f"```"
    )

ROULETTE_COST = 70

class RouletteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.bets: dict[int, tuple[str, int]] = {}  # uid → (choice, amount)
        self.closed = False

    async def _place_bet(self, interaction: discord.Interaction, choice: str):
        if self.closed:
            return await interaction.response.send_message("⏰ Prijave zatvorene!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.bets:
            return await interaction.response.send_message(
                f"✅ Već si uložio na **{self.bets[uid][0]}**!", ephemeral=True
            )
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, ROULETTE_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"❌ Trebaš **{ROULETTE_COST}** {COIN}! Imaš **{coins}**", ephemeral=True
            )
        self.bets[uid] = (choice, ROULETTE_COST)
        await interaction.response.send_message(
            f"✅ Uložio si **{ROULETTE_COST}** {COIN} na **{choice}**!", ephemeral=True
        )

    @discord.ui.button(label="🔴 Crvena (x2)", style=discord.ButtonStyle.danger, row=0)
    async def bet_red(self, i, b): await self._place_bet(i, "crvena")

    @discord.ui.button(label="⚫ Crna (x2)", style=discord.ButtonStyle.secondary, row=0)
    async def bet_black(self, i, b): await self._place_bet(i, "crna")

    @discord.ui.button(label="🟢 Nula (x14)", style=discord.ButtonStyle.success, row=0)
    async def bet_zero(self, i, b): await self._place_bet(i, "nula")

    @discord.ui.button(label="🔢 Parno (x2)", style=discord.ButtonStyle.primary, row=1)
    async def bet_even(self, i, b): await self._place_bet(i, "parno")

    @discord.ui.button(label="🔢 Neparno (x2)", style=discord.ButtonStyle.primary, row=1)
    async def bet_odd(self, i, b): await self._place_bet(i, "neparno")

    @discord.ui.button(label="📉 1–18 (x2)", style=discord.ButtonStyle.secondary, row=2)
    async def bet_low(self, i, b): await self._place_bet(i, "nisko")

    @discord.ui.button(label="📈 19–36 (x2)", style=discord.ButtonStyle.secondary, row=2)
    async def bet_high(self, i, b): await self._place_bet(i, "visoko")

class RouletteGame:
    NAME = "🎡 Rulet"
    COLOR = discord.Color.from_rgb(20, 140, 40)

    async def run(self, channel: discord.TextChannel):
        view = RouletteView()
        em = e(
            "🎡 RULET — Postavi Okladu!",
            f"Odaberi okladu i uloži **{ROULETTE_COST}** {COIN}!\n\n"
            f"```\n"
            f"🔴 Crvena   → x2    ⚫ Crna     → x2\n"
            f"🔢 Parno    → x2    🔢 Neparno  → x2\n"
            f"📉 1–18     → x2    📈 19–36    → x2\n"
            f"🟢 Nula (0) → x14\n"
            f"```\n"
            f"⏳ Oklade primamo **{TICK} sekundi**!",
            self.COLOR,
            footer="🎡 Rulet • Ulog: 70 coina"
        )
        msg = await channel.send(embed=em, view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.bets:
            await msg.edit(embed=e("🎡 Rulet", "Niko nije oklado.", discord.Color.greyple()), view=None)
            return

        # Animate ball
        wheel_msg = await channel.send(
            embed=e("🎡 Rulet — Kugla se kotrlja...", roulette_wheel_art(0), self.COLOR)
        )
        ball_pos = 0
        steps = random.randint(20, 36)
        for i in range(steps):
            ball_pos = (ball_pos + 1) % 37
            delay = 0.15 + (i / steps) * 0.5  # slows down
            await wheel_msg.edit(
                embed=e("🎡 Rulet — Kugla se kotrlja...", roulette_wheel_art(ball_pos), self.COLOR)
            )
            await asyncio.sleep(delay)

        result_num = random.randint(0, 36)
        result_col = roulette_color(result_num)
        col_name = "🟢 Zelena" if result_num == 0 else ("🔴 Crvena" if result_num in RED_NUMBERS else "⚫ Crna")

        await wheel_msg.edit(
            embed=e(
                f"🎡 Rulet — Broj: **{result_num}** {result_col}",
                roulette_wheel_art(result_num % 37) + f"\n\n🏷️ Boja: **{col_name}**",
                self.COLOR
            )
        )
        await asyncio.sleep(2)

        winners = []
        losers = []
        for uid, (choice, bet) in view.bets.items():
            won = False
            mult = 0
            if choice == "nula" and result_num == 0:
                won, mult = True, 14
            elif choice == "crvena" and result_num in RED_NUMBERS:
                won, mult = True, 2
            elif choice == "crna" and result_num not in RED_NUMBERS and result_num != 0:
                won, mult = True, 2
            elif choice == "parno" and result_num != 0 and result_num % 2 == 0:
                won, mult = True, 2
            elif choice == "neparno" and result_num % 2 == 1:
                won, mult = True, 2
            elif choice == "nisko" and 1 <= result_num <= 18:
                won, mult = True, 2
            elif choice == "visoko" and 19 <= result_num <= 36:
                won, mult = True, 2

            await add_played(uid)
            if won:
                winnings = bet * mult
                await add_coins(uid, winnings)
                await add_win(uid, 30)
                winners.append(f"<@{uid}> ({choice}) → +**{winnings}** {COIN}")
            else:
                losers.append(f"<@{uid}> ({choice}) → ❌")

        win_txt = "\n".join(winners) if winners else "Niko nije pogodio."
        los_txt = "\n".join(losers) if losers else "—"
        res = e(
            f"🎡 Rulet — Rezultat: **{result_num}** {result_col}",
            f"**Pobjednici:**\n{win_txt}\n\n**Gubitnici:**\n{los_txt}",
            discord.Color.green() if winners else discord.Color.red()
        )
        await channel.send(embed=res)
        await asyncio.sleep(8)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 6 — 💣 MINES (button grid)
# ─────────────────────────────────────────────────────────────────────────────
MINES_COST = 100
MINES_COUNT = 5
MINES_COLS = 5

class MinesView(discord.ui.View):
    def __init__(self, mines: set, pot: int, player_id: int, msg_ref):
        super().__init__(timeout=120)
        self.mines = mines
        self.revealed: set = set()
        self.safe = 0
        self.pot = pot
        self.player_id = player_id
        self.msg_ref = msg_ref
        self.active = True
        for i in range(25):
            btn = discord.ui.Button(
                label="·",
                style=discord.ButtonStyle.secondary,
                row=i // MINES_COLS,
                custom_id=str(i)
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)
        cashout = discord.ui.Button(
            label="💰 Naplata", style=discord.ButtonStyle.success, row=4
        )
        cashout.callback = self.cashout_callback
        self.add_item(cashout)

    def _make_callback(self, pos: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player_id:
                return await interaction.response.send_message("❌ Ovo nije tvoja igra!", ephemeral=True)
            if not self.active:
                return await interaction.response.send_message("Igra završena.", ephemeral=True)
            if pos in self.revealed:
                return await interaction.response.send_message("Već otkriveno!", ephemeral=True)

            self.revealed.add(pos)
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id == str(pos):
                    if pos in self.mines:
                        item.label = "💣"
                        item.style = discord.ButtonStyle.danger
                        item.disabled = True
                    else:
                        item.label = "💎"
                        item.style = discord.ButtonStyle.success
                        item.disabled = True
                    break

            if pos in self.mines:
                self.active = False
                self.stop()
                for item in self.children:
                    item.disabled = True
                mult = max(1, self.safe)
                await interaction.response.edit_message(
                    embed=e("💣 BOOM! Naletio si na minu!", f"Izgubio si **{self.pot}** {COIN} 💸", discord.Color.red()),
                    view=self
                )
                await add_played(self.player_id)
            else:
                self.safe += 1
                potential = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
                await interaction.response.edit_message(
                    embed=e(
                        f"💎 Sigurno! ({self.safe} otvoreno)",
                        f"Potencijalni dobitak: **{potential}** {COIN}\n\n"
                        f"Nastavi ili klikni 💰 za naplatu!",
                        discord.Color.green()
                    ),
                    view=self
                )
        return callback

    async def cashout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        if not self.active:
            return await interaction.response.send_message("Igra već završena.", ephemeral=True)
        self.active = False
        self.stop()
        for item in self.children:
            item.disabled = True
        if self.safe == 0:
            await add_coins(self.player_id, self.pot)
            await interaction.response.edit_message(
                embed=e("↩️ Cashout", f"Nisi otvorio nijedno polje — ulog vraćen (**{self.pot}** {COIN}).", discord.Color.gold()),
                view=self
            )
            return
        winnings = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
        await add_coins(self.player_id, winnings)
        await add_win(self.player_id, 40)
        await interaction.response.edit_message(
            embed=e(
                "💰 Naplata!",
                f"Otvorio si **{self.safe}** polja bez mine!\n💰 Dobio si **{winnings}** {COIN}!",
                discord.Color.gold()
            ),
            view=self
        )

class MinesLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.player: int | None = None
        self.closed = False

    @discord.ui.button(label="💣 Zaigraj Mines (100 🪙)", style=discord.ButtonStyle.danger)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("⏰ Zatvoreno!", ephemeral=True)
        if self.player is not None:
            return await interaction.response.send_message("❌ Netko već igra! Čekaj sljedeću rundu.", ephemeral=True)
        await ensure_user(interaction.user.id, interaction.user.display_name)
        ok = await deduct_coins(interaction.user.id, MINES_COST)
        if not ok:
            return await interaction.response.send_message(f"❌ Trebaš {MINES_COST} {COIN}!", ephemeral=True)
        self.player = interaction.user.id
        self.closed = True
        self.stop()
        await interaction.response.send_message("✅ Igra počinje!", ephemeral=True)

class MinesGame:
    NAME = "💣 Mines"
    COLOR = discord.Color.from_rgb(30, 30, 30)

    async def run(self, channel: discord.TextChannel):
        lobby = MinesLobbyView()
        msg = await channel.send(
            embed=e(
                "💣 MINES — Zaigraj!",
                f"Jedan igrač otvara polja na 5×5 mreži.\n"
                f"Ima **{MINES_COUNT}** mina! Otvori što više polja bez eksplozije.\n"
                f"💎 = sigurno | 💣 = kraj!\n\n"
                f"Ulog: **{MINES_COST}** {COIN} | Naplata kad god hoćeš!\n"
                f"⏳ **{TICK}s** za prijavu.",
                self.COLOR,
                footer="💣 Mines • Ulog: 100 coina"
            ),
            view=lobby
        )
        await asyncio.sleep(TICK)
        lobby.closed = True

        if lobby.player is None:
            await msg.edit(embed=e("💣 Mines", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        mines = set(random.sample(range(25), MINES_COUNT))
        game_view = MinesView(mines, MINES_COST, lobby.player, msg)
        grid_em = e(
            "💣 Mines — Klikni Polja!",
            f"<@{lobby.player}> — Otvori polja! Izbjegni mine!\n"
            f"💰 Naplata u bilo koje vrijeme!",
            discord.Color.blue()
        )
        await msg.edit(embed=grid_em, view=game_view)
        await game_view.wait()
        await asyncio.sleep(5)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 7 — 🎟️ GREBALICA (scratch card)
# ─────────────────────────────────────────────────────────────────────────────
SCRATCH_PRIZES = [
    (0, 40), (30, 20), (60, 15), (100, 10),
    (200, 7), (500, 4), (1000, 2), (2000, 1), (5000, 0.5),
]

class ScratchCard(discord.ui.View):
    def __init__(self, owner_id: int, prize: int, item: tuple | None):
        super().__init__(timeout=30)
        self.owner_id = owner_id
        self.prize = prize
        self.item = item
        self.scratched = False

    @discord.ui.button(label="🎟️ Ogrebi!", style=discord.ButtonStyle.success)
    async def scratch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Nije tvoja grebalica!", ephemeral=True)
        if self.scratched:
            return await interaction.response.send_message("Već ogrebana!", ephemeral=True)
        self.scratched = True
        button.disabled = True
        self.stop()
        prize = self.prize
        item = self.item
        if prize > 0:
            await add_coins(self.owner_id, prize)
        if item:
            await add_item(self.owner_id, item[0], item[1])
        sym_map = {0: "❌❌❌", 30: "🍒🍒❌", 60: "🍒🍒🍒", 100: "⭐⭐🍒",
                   200: "⭐⭐⭐", 500: "💎💎⭐", 1000: "💎💎💎", 2000: "🌟🌟💎", 5000: "7️⃣7️⃣7️⃣"}
        syms = sym_map.get(prize, "❓❓❓")
        extra = f"\n🎁 **{item[1]}**" if item else ""
        color = discord.Color.green() if prize > 0 else discord.Color.greyple()
        await interaction.response.edit_message(
            embed=e("🎟️ Ogrebana!", f"**[ {syms} ]**\n\n💰 Dobitak: **{prize}** {COIN}{extra}", color),
            view=self
        )

class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.buyers: set[int] = set()
        self.closed = False

    @discord.ui.button(label="🎟️ Kupi Grebalicu (40 🪙)", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("⏰ Grebalice rasprodate!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.buyers:
            return await interaction.response.send_message("✅ Već imaš grebalicu!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, 40)
        if not ok:
            return await interaction.response.send_message("❌ Trebaš **40** {COIN}!", ephemeral=True)
        self.buyers.add(uid)
        # Determine prize
        prizes = [p for p, _ in SCRATCH_PRIZES]
        weights = [w for _, w in SCRATCH_PRIZES]
        prize = random.choices(prizes, weights=weights)[0]
        item = None
        if prize == 5000:
            item = rand_prize("legendary")
        elif prize >= 1000:
            item = rand_prize("rare")
        card_view = ScratchCard(uid, prize, item)
        await interaction.response.send_message(
            embed=e("🎟️ Tvoja Grebalica", "Klikni dugme da ogrebeš!", discord.Color.gold()),
            view=card_view,
            ephemeral=True
        )
        await add_played(uid)

class ScratchGame:
    NAME = "🎟️ Grebalica"
    COLOR = discord.Color.gold()

    async def run(self, channel: discord.TextChannel):
        view = ScratchView()
        msg = await channel.send(
            embed=e(
                "🎟️ GREBALICE — Na Rasprodaji!",
                f"Kupi grebalicu za **40** {COIN} i ogrebi je odmah!\n\n"
                f"```\n"
                f"[ ❌❌❌ ] → Ništa\n"
                f"[ 🍒🍒🍒] → 60 coina\n"
                f"[ ⭐⭐⭐ ] → 200 coina\n"
                f"[ 💎💎💎 ] → 1000 coina + Nagrada\n"
                f"[ 7️⃣7️⃣7️⃣ ] → 5000 coina + NITRO 💜\n"
                f"```\n"
                f"⏳ Dostupne **{TICK}s**!",
                self.COLOR,
                footer="🎟️ Grebalica • Cijena: 40 coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()
        await msg.edit(view=None)
        if view.buyers:
            await channel.send(embed=e("🎟️ Grebalice Završene", f"Prodato **{len(view.buyers)}** grebalica!", self.COLOR))
        await asyncio.sleep(5)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 8 — 🎲 LUTRIJA
# ─────────────────────────────────────────────────────────────────────────────
LOTTERY_COST = 60

class LotteryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.tickets: dict[int, list[int]] = {}
        self.pot = 0
        self.closed = False

    @discord.ui.button(label="🎲 Kupi Listić (60 🪙)", style=discord.ButtonStyle.primary)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("⏰ Listići rasprodati!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.tickets:
            return await interaction.response.send_message("✅ Već imaš listić!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, LOTTERY_COST)
        if not ok:
            return await interaction.response.send_message(f"❌ Trebaš {LOTTERY_COST} {COIN}!", ephemeral=True)
        nums = sorted(random.sample(range(1, 50), 6))
        self.tickets[uid] = nums
        self.pot += LOTTERY_COST
        await interaction.response.send_message(
            f"🎲 Tvoji brojevi: **{' — '.join(map(str, nums))}**\nPot: **{self.pot}** {COIN}",
            ephemeral=True
        )

class LotteryGame:
    NAME = "🎲 Lutrija"
    COLOR = discord.Color.from_rgb(255, 165, 0)

    async def run(self, channel: discord.TextChannel):
        view = LotteryView()
        msg = await channel.send(
            embed=e(
                "🎲 LUTRIJA — Kupi Listić!",
                f"Kupi listić za **{LOTTERY_COST}** {COIN}!\n"
                f"Svaki igrač dobiva 6 nasumičnih brojeva (1–49).\n"
                f"Bot izvlači 6 dobitnih — ko ima najviše podudaranja pobijedi!\n\n"
                f"⏳ Listići se prodaju **{TICK}s**!",
                self.COLOR,
                footer="🎲 Lutrija • Listić: 60 coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.tickets:
            await msg.edit(embed=e("🎲 Lutrija", "Nema igrača.", discord.Color.greyple()), view=None)
            return

        drawn = sorted(random.sample(range(1, 50), 6))
        drawn_set = set(drawn)
        draw_str = " — ".join(f"**{n}**" for n in drawn)

        draw_em = e("🎲 Lutrija — Izvlačenje!", f"Izvučeni brojevi:\n{draw_str}", self.COLOR)
        draw_msg = await channel.send(embed=draw_em)
        await asyncio.sleep(3)

        scores = {}
        for uid, nums in view.tickets.items():
            hits = len(set(nums) & drawn_set)
            scores[uid] = hits
            await add_played(uid)

        top_score = max(scores.values())
        winners = [uid for uid, s in scores.items() if s == top_score]

        if top_score == 0:
            result = e("🎲 Lutrija — Nema Pobjednika", f"Izvučeni: {draw_str}\n\nNiko nije imao pogodaka. Pot propada.", discord.Color.red())
        else:
            share = view.pot // len(winners)
            for uid in winners:
                await add_coins(uid, share)
                await add_win(uid, 50)
                if top_score >= 5:
                    rtype, item = rand_prize("rare")
                    await add_item(uid, rtype, item)
            mention = " ".join(f"<@{uid}>" for uid in winners)
            result = e(
                "🎲 Lutrija — Pobjednik!",
                f"Izvučeni: {draw_str}\n\n"
                f"🏆 {mention}\n"
                f"Pogodaka: **{top_score}/6**\n"
                f"💰 Dobitak: **{share}** {COIN} svaki",
                discord.Color.green()
            )
        await draw_msg.edit(embed=result)
        await asyncio.sleep(8)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 9 — 😀 EMOJI GUESS
# ─────────────────────────────────────────────────────────────────────────────
EMOJI_ROUNDS = [
    ("👠⏰🎃", ["stifte", "Šta je to"]),  # placeholder — override below
]
EMOJI_QUESTIONS = [
    {"emojis": "👠⏰🎃", "answers": ["kasnila", "cinderella", "pepeljuga"], "hint": "Disney bajka"},
    {"emojis": "🌊🐠🔍", "answers": ["nemo", "finding nemo", "tražeći nema"], "hint": "Animirani film"},
    {"emojis": "🦁👑🌍", "answers": ["kralj lavova", "lion king", "simba"], "hint": "Disney film"},
    {"emojis": "❄️👸✨", "answers": ["frozen", "ledeno kraljevstvo", "elsa"], "hint": "Animirani film"},
    {"emojis": "🕷️👦🏙️", "answers": ["spiderman", "spider man", "pejak"], "hint": "Superjunak"},
    {"emojis": "🦇🤵🌃", "answers": ["batman", "betmen"], "hint": "Gotham City"},
    {"emojis": "⚡🧙📚", "answers": ["harry potter", "hari poter"], "hint": "Čarobnjak"},
    {"emojis": "💍🧝🌋", "answers": ["gospodar prstenova", "lord of the rings", "lotr"], "hint": "Fantasy epic"},
    {"emojis": "🚀👨‍🚀♾️", "answers": ["interstellar", "beskonačnost", "svemir"], "hint": "Nolan film"},
    {"emojis": "🃏🤡🃏", "answers": ["joker", "džoker"], "hint": "DC vilain"},
    {"emojis": "🐉🔥⚔️", "answers": ["igra prijestolja", "game of thrones", "got"], "hint": "HBO serija"},
    {"emojis": "💊🔵🔴", "answers": ["matrix", "matriks"], "hint": "Sci-fi klasik"},
    {"emojis": "🧟‍♂️🔫🌍", "answers": ["walking dead", "hodajući mrtvi", "zombiji"], "hint": "AMC serija"},
    {"emojis": "👨‍🍳💀🧪", "answers": ["breaking bad", "valjati loše"], "hint": "AMC serija, hemičar"},
    {"emojis": "🐢🍕🥷", "answers": ["ninja kornjače", "tmnt", "teenage mutant"], "hint": "Akcioni crtić"},
    {"emojis": "🐘✈️🎪", "answers": ["dumbo", "slon leti"], "hint": "Leteći slon"},
    {"emojis": "🔫🕶️📱", "answers": ["john wick", "džon vik"], "hint": "Keanu Reeves akcija"},
]

EMOJI_REWARD = 250
EMOJI_TIME = 45

class EmojiGame:
    NAME = "😀 Emoji Guess"
    COLOR = discord.Color.from_rgb(255, 200, 0)

    async def run(self, channel: discord.TextChannel):
        q = random.choice(EMOJI_QUESTIONS)
        winner_uid = None
        winner_msg = None

        em = e(
            "😀 EMOJI GUESS — Pogodi!",
            f"**{q['emojis']}**\n\n"
            f"Napiši šta ovi emoji predstavljaju u chat!\n"
            f"💡 Hint: *{q['hint']}*\n\n"
            f"✅ Nagrada: **{EMOJI_REWARD}** {COIN}\n"
            f"⏳ Imate **{EMOJI_TIME} sekundi**!",
            self.COLOR,
            footer=f"😀 Emoji Guess • Nagrada: {EMOJI_REWARD} coina • danas u {datetime.utcnow().strftime('%H:%M')}"
        )
        msg = await channel.send(embed=em)

        def check(m: discord.Message):
            return (
                m.channel.id == channel.id
                and not m.author.bot
                and any(a in m.content.lower() for a in q["answers"])
            )

        try:
            ans = await channel.bot.wait_for("message", timeout=EMOJI_TIME, check=check)
            winner_uid = ans.author.id
            winner_msg = ans
        except asyncio.TimeoutError:
            pass

        if winner_uid:
            await ensure_user(winner_uid, winner_msg.author.display_name)
            await add_coins(winner_uid, EMOJI_REWARD)
            await add_win(winner_uid, 30)
            result = e(
                "😀 Tačan Odgovor!",
                f"🏆 <@{winner_uid}> pogodio!\n"
                f"✉️ Odgovor: **\"{winner_msg.content}\"**\n"
                f"✅ Traženo: **{q['answers'][0].title()}**\n\n"
                f"💰 +**{EMOJI_REWARD}** {COIN}",
                discord.Color.green(),
                footer=f"😀 Emoji Guess • Preostalo u špifu: {len(EMOJI_QUESTIONS)} • {EMOJI_REWARD} bodova • danas u {datetime.utcnow().strftime('%H:%M')}"
            )
        else:
            result = e(
                "⏰ Vreme Isteklo!",
                f"Niko nije pogodio.\n\n"
                f"**{q['emojis']}**\n"
                f"✅ Odgovor: **{q['answers'][0].title()}**",
                discord.Color.red(),
                footer=f"😀 Emoji Guess • Preostalo u špifu: {len(EMOJI_QUESTIONS)} • {EMOJI_REWARD} bodova"
            )
        await msg.edit(embed=result)
        await asyncio.sleep(8)

# ─────────────────────────────────────────────────────────────────────────────
# GAME 10 — 👑 JACKPOT EVENT (boss raid style pot)
# ─────────────────────────────────────────────────────────────────────────────
JACKPOT_COST = 120

class JackpotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.entrants: list[int] = []
        self.pot = 0
        self.closed = False

    @discord.ui.button(label="👑 Uloži u Jackpot (120 🪙)", style=discord.ButtonStyle.danger)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("⏰ Jackpot zatvoren!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.entrants:
            return await interaction.response.send_message(
                f"✅ Već si u igri! Pot: **{self.pot}** {COIN}", ephemeral=True
            )
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, JACKPOT_COST)
        if not ok:
            return await interaction.response.send_message(f"❌ Trebaš {JACKPOT_COST} {COIN}!", ephemeral=True)
        self.entrants.append(uid)
        self.pot += JACKPOT_COST
        await interaction.response.send_message(
            f"🎰 U igri si! Igrači: **{len(self.entrants)}** | Pot: **{self.pot}** {COIN}", ephemeral=True
        )

class JackpotGame:
    NAME = "👑 JACKPOT EVENT"
    COLOR = discord.Color.from_rgb(255, 50, 50)

    async def run(self, channel: discord.TextChannel):
        view = JackpotView()
        msg = await channel.send(
            embed=e(
                "👑 ═══ JACKPOT EVENT ═══ 👑",
                f"Svi ulaze, jedan pobijedi **SVE**!\n\n"
                f"Ulog: **{JACKPOT_COST}** {COIN} po igraču\n"
                f"🎯 Šansa = tvoja ulaganja / ukupni pot\n"
                f"🏆 Pobjednik uzima **cijeli pot** + Legendarnu nagradu!\n\n"
                f"⏳ Prijave: **{TICK}s** — Maks 20 igrača!",
                self.COLOR,
                footer="👑 Jackpot Event • Ulog: 120 coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if len(view.entrants) < 2:
            await msg.edit(embed=e("👑 Jackpot", "Premalo igrača! Ulozi vraćeni.", discord.Color.red()), view=None)
            for uid in view.entrants:
                await add_coins(uid, JACKPOT_COST)
            return

        # Dramatic countdown
        for countdown in [5, 4, 3, 2, 1]:
            await msg.edit(
                embed=e(
                    f"👑 JACKPOT — Izvlačenje za {countdown}...",
                    f"Igrači: **{len(view.entrants)}**\nPot: **{view.pot}** {COIN}\n\n"
                    f"{'🎰 ' * countdown}",
                    self.COLOR
                ),
                view=None
            )
            await asyncio.sleep(1)

        winner = random.choice(view.entrants)
        await add_coins(winner, view.pot)
        await add_win(winner, 100)
        rtype, item = rand_prize("legendary")
        await add_item(winner, rtype, item)
        for uid in view.entrants:
            await add_played(uid)

        await msg.edit(
            embed=e(
                "👑 JACKPOT POBJEDNIK!",
                f"🎉 <@{winner}> uzima SVE!\n\n"
                f"💰 Pot: **{view.pot}** {COIN}\n"
                f"🏆 Legendarni item: **{item}**\n\n"
                f"Čestitamo! 🎊",
                discord.Color.gold()
            )
        )
        await asyncio.sleep(10)

# ─────────────────────────────────────────────────────────────────────────────
# GAME REGISTRY — order of rotation
# ─────────────────────────────────────────────────────────────────────────────
ALL_GAMES = [
    EmojiGame,
    QuizGame,
    SlotGame,
    WheelGame,
    RouletteGame,
    ScratchGame,
    LotteryGame,
    BingoGame,
    MinesGame,
    JackpotGame,
]
