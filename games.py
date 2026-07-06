"""
10 auto-posting igara — moderni embedi bez code blokova,
pravi tekstovi Jala Brat & Buba Corelli.
"""

import discord
import asyncio
import random
from datetime import datetime
from database import (
    ensure_user, get_coins, add_coins, deduct_coins,
    add_win, add_played, add_item
)

COIN = "🪙"
TICK = 60

DECORATIONS = [
    "Zlatna Zvijezda", "Vatreni Efekt", "Ledeni Efekt",
    "Rainbow Aura", "Kraljevska Kruna", "Munja Efekt",
    "Butterfly Frame", "Stardust Efekt", "Maskerada Okvir",
]
AVATARS = [
    "Zmaj Avatar", "Lav Avatar", "Cyber Avatar",
    "Carobnjak Avatar", "Lisica Avatar", "Vuk Avatar",
    "Mistik Avatar", "Okean Avatar",
]
NITRO = ["Nitro Classic (1 mj.)", "Nitro Boost (1 mj.)", "Nitro Gift Link"]


def rand_prize(tier="common"):
    if tier == "legendary":
        return "nitro", random.choice(NITRO)
    if tier == "rare":
        if random.random() < 0.5:
            return "avatar", random.choice(AVATARS)
        return "decoration", random.choice(DECORATIONS)
    return "decoration", random.choice(DECORATIONS)


def emb(title: str, desc: str = None, color=discord.Color.gold(),
        fields=None, footer=None) -> discord.Embed:
    em = discord.Embed(title=title, description=desc, color=color)
    em.timestamp = datetime.utcnow()
    for f in (fields or []):
        em.add_field(name=f[0], value=f[1], inline=f[2] if len(f) > 2 else True)
    if footer:
        em.set_footer(text=footer)
    return em


# ─────────────────────────────────────────────────────────────────────────────
# GAME 1 — BINGO
# ─────────────────────────────────────────────────────────────────────────────
class BingoView(discord.ui.View):
    TICKET_COST = 80

    def __init__(self):
        super().__init__(timeout=TICK)
        self.players: dict[int, list[int]] = {}
        self.pot = 0
        self.closed = False

    @discord.ui.button(label="Kupi listic  —  80 coina", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Prijave su zatvorene.", ephemeral=True)
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("Vec imas listic!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, self.TICKET_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"Nemas dovoljno. Imas **{coins}** {COIN}", ephemeral=True)
        card = sorted(random.sample(range(1, 76), 15))
        self.players[uid] = card
        self.pot += self.TICKET_COST
        nums = "  ".join(f"**{n}**" for n in card)
        await interaction.response.send_message(
            embed=emb("Tvoj Bingo Listic", nums, discord.Color.green(),
                      footer=f"Pot: {self.pot} coina"),
            ephemeral=True)


class BingoGame:
    NAME = "Bingo"
    COLOR = discord.Color.blue()

    async def run(self, channel: discord.TextChannel):
        view = BingoView()
        msg = await channel.send(embed=emb(
            "BINGO",
            "Kupi listic i budi prvi koji oznaci svih **15** brojeva!",
            self.COLOR,
            fields=[
                ("Cijena listicа", f"**{BingoView.TICKET_COST}** {COIN}", True),
                ("Kako igrati", "Bot vuce brojeve 1–75 jedan po jedan. Ko prvi skupi sve pobijedi!", False),
                ("Trajanje prijava", f"**{TICK} sekundi**", True),
            ],
            footer="Bingo"
        ), view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if len(view.players) < 2:
            await msg.edit(embed=emb("BINGO — Otkazano",
                "Premalo igraca (min 2). Ulozi vraceni.", discord.Color.red()), view=None)
            for uid in view.players:
                await add_coins(uid, BingoView.TICKET_COST)
            return

        pool = list(range(1, 76))
        random.shuffle(pool)
        marked: dict[int, set] = {uid: set() for uid in view.players}
        called = []
        winner_uid = None

        draw_msg = await channel.send(embed=emb(
            "BINGO — Izvlacenje",
            None, self.COLOR,
            fields=[
                ("Igraci", str(len(view.players)), True),
                ("Pot", f"**{view.pot}** {COIN}", True),
            ]))

        for num in pool:
            called.append(num)
            for uid, card in view.players.items():
                if num in card:
                    marked[uid].add(num)
                if len(marked[uid]) >= len(view.players[uid]):
                    winner_uid = uid
                    break

            last10 = "  ".join(f"**{n}**" if n == num else str(n) for n in called[-10:])
            progress = "\n".join(
                f"<@{uid}>  {len(marked[uid])}/{len(view.players[uid])}"
                for uid in view.players)
            await draw_msg.edit(embed=emb(
                f"BINGO — Broj {num}",
                progress, self.COLOR,
                fields=[("Zadnjih 10 izvucenih", last10, False)],
                footer=f"Izvuceno: {len(called)}/75"))
            if winner_uid:
                break
            await asyncio.sleep(4)

        if winner_uid:
            await add_coins(winner_uid, view.pot)
            await add_win(winner_uid, 80)
            _, item = rand_prize("rare")
            await add_item(winner_uid, "decoration", item)
            result = emb("BINGO — Pobjednik!", f"<@{winner_uid}> je skupio sve brojeve!",
                discord.Color.green(),
                fields=[
                    ("Dobitak", f"**{view.pot}** {COIN}", True),
                    ("Bonus nagrada", item, True),
                ])
        else:
            result = emb("BINGO", "Niko nije pobijedio.", discord.Color.greyple())

        for uid in view.players:
            await add_played(uid)
        await draw_msg.edit(embed=result)
        await asyncio.sleep(10)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 2 — KOLO SRECE
# ─────────────────────────────────────────────────────────────────────────────
WHEEL_SEGMENTS = [
    ("BANKROT",    0,    "bankrot"),
    ("100 coina",  100,  "coins"),
    ("250 coina",  250,  "coins"),
    ("500 coina",  500,  "coins"),
    ("1000 coina", 1000, "coins"),
    ("50 coina",   50,   "coins"),
    ("Dekoracija", 0,    "decoration"),
    ("Avatar",     0,    "avatar"),
    ("2000 coina", 2000, "coins"),
    ("NITRO",      0,    "nitro"),
    ("750 coina",  750,  "coins"),
    ("Nista",      0,    "nothing"),
]
WHEEL_WEIGHTS = [2, 10, 9, 6, 3, 12, 5, 4, 1, 1, 5, 8]
SPIN_COST = 60


def wheel_text(highlight: int) -> str:
    lines = []
    for i, (label, _, _) in enumerate(WHEEL_SEGMENTS):
        arrow = "  ◄" if i == highlight else ""
        lines.append(f"{'▶' if i == highlight else '·'}  {label}{arrow}")
    return "\n".join(lines)


class WheelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.spinners: list[int] = []
        self.closed = False

    @discord.ui.button(label="Zavrti kolo  —  60 coina", style=discord.ButtonStyle.blurple)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Kolo je zatvoreno.", ephemeral=True)
        uid = interaction.user.id
        if uid in self.spinners:
            return await interaction.response.send_message("Vec si prijavljen!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, SPIN_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"Trebas **{SPIN_COST}** {COIN}. Imas **{coins}** {COIN}", ephemeral=True)
        self.spinners.append(uid)
        await interaction.response.send_message("Prijavljen! Cekaj spin...", ephemeral=True)


class WheelGame:
    NAME = "Kolo Srece"
    COLOR = discord.Color.purple()

    async def run(self, channel: discord.TextChannel):
        view = WheelView()
        nagrade = "\n".join(f"• {label}" for label, _, _ in WHEEL_SEGMENTS)
        msg = await channel.send(embed=emb(
            "KOLO SRECE",
            "Klikni dugme i uloži da dobijes spin na kolu!",
            self.COLOR,
            fields=[
                ("Cijena spina", f"**{SPIN_COST}** {COIN}", True),
                ("Trajanje prijava", f"**{TICK} sekundi**", True),
                ("Moguce nagrade", nagrade, False),
            ],
            footer="Kolo Srece"
        ), view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.spinners:
            await msg.edit(embed=emb("KOLO SRECE", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        for uid in view.spinners:
            spin_msg = await channel.send(embed=emb(
                "Kolo se vrti...", wheel_text(0), self.COLOR))
            prev = -1
            for _ in range(10):
                pos = random.randint(0, len(WHEEL_SEGMENTS) - 1)
                while pos == prev:
                    pos = random.randint(0, len(WHEEL_SEGMENTS) - 1)
                prev = pos
                await spin_msg.edit(embed=emb("Kolo se vrti...", wheel_text(pos), self.COLOR))
                await asyncio.sleep(0.5)

            segment = random.choices(WHEEL_SEGMENTS, weights=WHEEL_WEIGHTS)[0]
            label, amount, stype = segment
            final_pos = WHEEL_SEGMENTS.index(segment)
            await spin_msg.edit(embed=emb("Kolo stalo!", wheel_text(final_pos), self.COLOR))
            await asyncio.sleep(1)

            if stype == "bankrot":
                lost = min(await get_coins(uid), random.randint(50, 300))
                await add_coins(uid, -lost)
                result_em = emb("Kolo Srece — Rezultat",
                    f"<@{uid}> — **{label}**\nGubiš **{lost}** {COIN}!",
                    discord.Color.dark_red())
            elif stype == "coins":
                await add_coins(uid, amount)
                result_em = emb("Kolo Srece — Rezultat", None,
                    discord.Color.green(),
                    fields=[
                        ("Igrac", f"<@{uid}>", True),
                        ("Nagrada", f"**{amount}** {COIN}", True),
                    ])
            elif stype in ("decoration", "avatar", "nitro"):
                tier = "legendary" if stype == "nitro" else "rare" if stype == "avatar" else "common"
                rtype, item = rand_prize(tier)
                await add_item(uid, rtype, item)
                result_em = emb("Kolo Srece — Rezultat", None,
                    discord.Color.blurple(),
                    fields=[
                        ("Igrac", f"<@{uid}>", True),
                        ("Nagrada", item, True),
                    ])
            else:
                result_em = emb("Kolo Srece — Rezultat",
                    f"<@{uid}> — nista ovaj put.", discord.Color.greyple())

            await add_played(uid)
            await spin_msg.edit(embed=result_em)
            await asyncio.sleep(3)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 3 — SLOT MACHINE
# ─────────────────────────────────────────────────────────────────────────────
REEL_NAMES = ["Cherry", "Lemon", "Grape", "Star", "Diamond", "Bell", "Seven", "Wild", "Crown", "Clover"]
REEL_EMO = {
    "Cherry": "🍒", "Lemon": "🍋", "Grape": "🍇", "Star": "⭐",
    "Diamond": "💎", "Bell": "🔔", "Seven": "7️⃣", "Wild": "🃏", "Crown": "👑", "Clover": "🍀"
}
JACKPOTS = {
    ("Seven",   "Seven",   "Seven"):   (20, "legendary"),
    ("Diamond", "Diamond", "Diamond"): (15, "rare"),
    ("Star",    "Star",    "Star"):    (10, "common"),
    ("Crown",   "Crown",   "Crown"):   (8,  "common"),
    ("Clover",  "Clover",  "Clover"):  (7,  "common"),
    ("Bell",    "Bell",    "Bell"):    (5,  "common"),
    ("Grape",   "Grape",   "Grape"):   (4,  "common"),
    ("Lemon",   "Lemon",   "Lemon"):   (3,  "common"),
    ("Cherry",  "Cherry",  "Cherry"):  (2,  "common"),
}
SLOT_COST = 50


def slot_display(reels) -> str:
    return "  |  ".join(REEL_EMO.get(r, "❓") for r in reels)


class SlotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.players: set[int] = set()
        self.closed = False

    @discord.ui.button(label="Zaigraj  —  50 coina", style=discord.ButtonStyle.green)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Slot je zatvoren.", ephemeral=True)
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("Vec si prijavljen!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, SLOT_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"Trebas **{SLOT_COST}** {COIN}. Imas **{coins}** {COIN}", ephemeral=True)
        self.players.add(uid)
        await interaction.response.send_message("Prijavljen! Cekaj vrtnju...", ephemeral=True)


class SlotGame:
    NAME = "Slot Machine"
    COLOR = discord.Color.orange()

    async def run(self, channel: discord.TextChannel):
        view = SlotView()
        msg = await channel.send(embed=emb(
            "SLOT MACHINE",
            "Klikni dugme i ulozi. Reeli se vrte — pokusaj skupiti tri ista!",
            self.COLOR,
            fields=[
                ("Cijena", f"**{SLOT_COST}** {COIN}", True),
                ("Trajanje prijava", f"**{TICK}s**", True),
                ("Kombinacije",
                 "7️⃣ 7️⃣ 7️⃣  →  x20 + Nitro\n"
                 "💎 💎 💎  →  x15 + Nagrada\n"
                 "⭐ ⭐ ⭐  →  x10\n"
                 "Ostale tri iste  →  x2 – x8\n"
                 "Dva ista  →  x1.5", False),
            ],
            footer="Slot Machine"
        ), view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.players:
            await msg.edit(embed=emb("SLOT MACHINE", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        await msg.edit(embed=emb("SLOT MACHINE", "Vrtnja pocinje...", self.COLOR), view=None)

        for uid in view.players:
            sm = await channel.send(embed=emb("Vrtim...", "🎰  ·  ·  ·", self.COLOR))
            for _ in range(6):
                r = [random.choice(REEL_NAMES) for _ in range(3)]
                await asyncio.sleep(0.45)
                await sm.edit(embed=emb("Vrtim...", slot_display(r), self.COLOR))

            final = tuple(random.choice(REEL_NAMES) for _ in range(3))
            await asyncio.sleep(0.45)
            display = slot_display(final)

            jackpot = JACKPOTS.get(final)
            if jackpot:
                mult, tier = jackpot
                winnings = SLOT_COST * mult
                await add_coins(uid, winnings)
                await add_win(uid, 60)
                rtype, item = rand_prize(tier)
                await add_item(uid, rtype, item)
                result_em = emb("JACKPOT!", display, discord.Color.gold(),
                    fields=[
                        ("Igrac", f"<@{uid}>", True),
                        ("Multiplikator", f"x{mult}", True),
                        ("Dobitak", f"**{winnings}** {COIN}", True),
                        ("Bonus nagrada", item, False),
                    ])
            elif len(set(final)) < 3:
                winnings = int(SLOT_COST * 1.5)
                await add_coins(uid, winnings)
                await add_played(uid)
                result_em = emb("Dva ista!", display, discord.Color.yellow(),
                    fields=[
                        ("Igrac", f"<@{uid}>", True),
                        ("Dobitak", f"**{winnings}** {COIN}", True),
                    ])
            else:
                await add_played(uid)
                result_em = emb("Nema podudaranja", display, discord.Color.red(),
                    fields=[
                        ("Igrac", f"<@{uid}>", True),
                        ("Gubitak", f"**{SLOT_COST}** {COIN}", True),
                    ])

            await sm.edit(embed=result_em)
            await asyncio.sleep(4)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 4 — NASTAVI PJESMU (Jala Brat & Buba Corelli — pravi tekstovi)
# ─────────────────────────────────────────────────────────────────────────────
SONGS = [
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Pilula",
        "lyric": "Sipam ti ___ u čašu vina, volim te ko što voli se Bosna i Hercegovina...",
        "answer": ["pilula", "pilulu"],
        "hint": "Ubacuje u piće",
    },
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Crni Mercedes",
        "lyric": "Doći ću po tebe u crnom ___, puna kesa, sjedi pored mene...",
        "answer": ["mercedes", "crni mercedes"],
        "hint": "Luksuzni auto",
    },
    {
        "artist": "Jala Brat",
        "title": "Za Tebe",
        "lyric": "Sve bih dao ___ moja, samo da si sretna, samo da se smjeješ...",
        "answer": ["za tebe", "tebe"],
        "hint": "Posvećeno dragoj osobi",
    },
    {
        "artist": "Buba Corelli",
        "title": "Ferrari",
        "lyric": "Vozim ___, puna kesa, kažu da sam lud, ali to je samo stil mog života...",
        "answer": ["ferrari", "ferari"],
        "hint": "Brzi talijanski auto",
    },
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Kuna Pela",
        "lyric": "___ pela, pela, pela — letiš kao pčela, zarađuješ kunu, srce moje...",
        "answer": ["kuna pela", "kuna", "pela"],
        "hint": "Radi kao pčela",
    },
    {
        "artist": "Jala Brat",
        "title": "Golubica",
        "lyric": "Moja ___ bijela, leti visoko iznad oblaka, samo ti me čekaš...",
        "answer": ["golubica"],
        "hint": "Bijela ptica",
    },
    {
        "artist": "Buba Corelli",
        "title": "Paranoja",
        "lyric": "Svuda vidim ___, u glavi mi se vrti, ne mogu da spavam noću...",
        "answer": ["paranoja"],
        "hint": "Stalna sumnja i strah",
    },
    {
        "artist": "Jala Brat",
        "title": "Cigare",
        "lyric": "Parim ___, gledam u nebo, misli idu daleko, ne znam kuda...",
        "answer": ["cigare", "cigaru"],
        "hint": "Puši ih",
    },
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Trik",
        "lyric": "To je samo ___, ne uzimaj srcu blizu, znaš pravila igre...",
        "answer": ["trik"],
        "hint": "Igra varanja",
    },
    {
        "artist": "Buba Corelli",
        "title": "Sjena",
        "lyric": "Pratim te ko ___, kud god kreneš, tu sam ja, ne mogu bez tebe...",
        "answer": ["sjena"],
        "hint": "Prati te svuda kao...",
    },
    {
        "artist": "Jala Brat",
        "title": "Pas",
        "lyric": "Vjeran ti sam ko ___, nikad neću izdati, uvijek pored tebe...",
        "answer": ["pas"],
        "hint": "Vjerna životinja",
    },
    {
        "artist": "Jala Brat & Buba Corelli",
        "title": "Bez Adrese",
        "lyric": "Živim ___, nema gdje da me nađeš, bježim od problema...",
        "answer": ["bez adrese"],
        "hint": "Nema doma ni adrese",
    },
    {
        "artist": "Jala Brat",
        "title": "Dijamant",
        "lyric": "Ti si moj ___, rijetka, skupa, nema te zamjene ni za što...",
        "answer": ["dijamant"],
        "hint": "Dragulj",
    },
    {
        "artist": "Buba Corelli",
        "title": "Novac",
        "lyric": "___ i slava, ali srece nema, sve je tu a praznina ostaje...",
        "answer": ["novac"],
        "hint": "Ima ga ali nije sretan",
    },
    {
        "artist": "Jala Brat",
        "title": "Sampanjac",
        "lyric": "Otvori ___, slavimo veceras, sve je moguce kad smo zajedno...",
        "answer": ["sampanjac", "sampanjac", "champagne"],
        "hint": "Pice za slavlje",
    },
]

QUIZ_REWARD = 300
QUIZ_TIME = 60


class QuizGame:
    NAME = "Nastavi Pjesmu"
    COLOR = discord.Color.from_rgb(220, 80, 180)

    async def run(self, channel: discord.TextChannel):
        song = random.choice(SONGS)
        winner_uid = None
        winner_answer = None

        msg = await channel.send(embed=emb(
            "NASTAVI PJESMU",
            f"*\"{song['lyric']}\"*",
            self.COLOR,
            fields=[
                ("Izvadac", song['artist'], True),
                ("Nagrada", f"**{QUIZ_REWARD}** {COIN}", True),
                ("Hint", song['hint'], True),
                ("Uputa", f"Napisi naziv pjesme u chat! Imas **{QUIZ_TIME}s**.", False),
            ],
            footer="Nastavi Pjesmu"
        ))

        def check(m: discord.Message):
            return (m.channel.id == channel.id and not m.author.bot
                    and any(a in m.content.lower() for a in song["answer"]))

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
            result = emb("Tacan Odgovor!", None, discord.Color.green(),
                fields=[
                    ("Pobjednik", f"<@{winner_uid}>", True),
                    ("Dobitak", f"**{QUIZ_REWARD}** {COIN}", True),
                    ("Pjesma", song['title'], True),
                    ("Izvadac", song['artist'], True),
                ])
        else:
            result = emb("Vrijeme Isteklo", "Niko nije pogodio.", discord.Color.red(),
                fields=[
                    ("Tacan odgovor", song['title'], True),
                    ("Izvadac", song['artist'], True),
                ])
        await msg.edit(embed=result)
        await asyncio.sleep(8)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 5 — RULET (animated)
# ─────────────────────────────────────────────────────────────────────────────
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
               30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]

ROULETTE_COST = 70


def roulette_color_label(n: int) -> str:
    if n == 0:
        return "🟢 Zelena"
    return "🔴 Crvena" if n in RED_NUMBERS else "⚫ Crna"


def roulette_wheel_embed(ball_pos: int, title: str, color) -> discord.Embed:
    """Prikazuje segment kola oko pozicije kugle kao embed field."""
    size = len(WHEEL_ORDER)
    start = (ball_pos - 3) % size
    segment = []
    for i in range(7):
        idx = (start + i) % size
        n = WHEEL_ORDER[idx]
        col = "🟢" if n == 0 else ("🔴" if n in RED_NUMBERS else "⚫")
        if i == 3:
            segment.append(f"**► {col} {n} ◄**")
        else:
            segment.append(f"{col} {n}")
    wheel_str = "   ".join(segment)
    em = discord.Embed(title=title, description=wheel_str, color=color)
    em.timestamp = datetime.utcnow()
    return em


class RouletteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.bets: dict[int, tuple[str, int]] = {}
        self.closed = False

    async def _place_bet(self, interaction: discord.Interaction, choice: str):
        if self.closed:
            return await interaction.response.send_message("Prijave zatvorene.", ephemeral=True)
        uid = interaction.user.id
        if uid in self.bets:
            return await interaction.response.send_message(
                f"Vec si ulozio na **{self.bets[uid][0]}**!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, ROULETTE_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"Trebas **{ROULETTE_COST}** {COIN}. Imas **{coins}** {COIN}", ephemeral=True)
        self.bets[uid] = (choice, ROULETTE_COST)
        await interaction.response.send_message(
            f"Ulozio si **{ROULETTE_COST}** {COIN} na **{choice}**!", ephemeral=True)

    @discord.ui.button(label="🔴 Crvena (x2)", style=discord.ButtonStyle.danger, row=0)
    async def bet_red(self, i, b): await self._place_bet(i, "crvena")

    @discord.ui.button(label="⚫ Crna (x2)", style=discord.ButtonStyle.secondary, row=0)
    async def bet_black(self, i, b): await self._place_bet(i, "crna")

    @discord.ui.button(label="🟢 Nula (x14)", style=discord.ButtonStyle.success, row=0)
    async def bet_zero(self, i, b): await self._place_bet(i, "nula")

    @discord.ui.button(label="Parno (x2)", style=discord.ButtonStyle.primary, row=1)
    async def bet_even(self, i, b): await self._place_bet(i, "parno")

    @discord.ui.button(label="Neparno (x2)", style=discord.ButtonStyle.primary, row=1)
    async def bet_odd(self, i, b): await self._place_bet(i, "neparno")

    @discord.ui.button(label="1–18 (x2)", style=discord.ButtonStyle.secondary, row=2)
    async def bet_low(self, i, b): await self._place_bet(i, "nisko")

    @discord.ui.button(label="19–36 (x2)", style=discord.ButtonStyle.secondary, row=2)
    async def bet_high(self, i, b): await self._place_bet(i, "visoko")


class RouletteGame:
    NAME = "Rulet"
    COLOR = discord.Color.from_rgb(20, 140, 40)

    async def run(self, channel: discord.TextChannel):
        view = RouletteView()
        msg = await channel.send(embed=emb(
            "RULET",
            "Odaberi okladu i pritisni dugme!",
            self.COLOR,
            fields=[
                ("Ulog", f"**{ROULETTE_COST}** {COIN}", True),
                ("Trajanje prijava", f"**{TICK}s**", True),
                ("Isplate",
                 "🔴 Crvena  →  x2\n"
                 "⚫ Crna  →  x2\n"
                 "Parno  →  x2\n"
                 "Neparno  →  x2\n"
                 "1–18  →  x2\n"
                 "19–36  →  x2\n"
                 "🟢 Nula (0)  →  x14", False),
            ],
            footer="Rulet"
        ), view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.bets:
            await msg.edit(embed=emb("RULET", "Niko nije oklado.", discord.Color.greyple()), view=None)
            return

        wheel_msg = await channel.send(embed=roulette_wheel_embed(0, "Rulet — Kugla se kotrlja...", self.COLOR))
        ball_pos = 0
        steps = random.randint(24, 42)
        for i in range(steps):
            ball_pos = (ball_pos + 1) % len(WHEEL_ORDER)
            delay = 0.10 + (i / steps) * 0.55
            await wheel_msg.edit(embed=roulette_wheel_embed(ball_pos, "Rulet — Kugla se kotrlja...", self.COLOR))
            await asyncio.sleep(delay)

        result_num = WHEEL_ORDER[ball_pos]
        col_name = roulette_color_label(result_num)
        await wheel_msg.edit(embed=roulette_wheel_embed(
            ball_pos, f"Rulet — Pao broj {result_num}  {col_name}", self.COLOR))
        await asyncio.sleep(2)

        winners = []
        losers = []
        for uid, (choice, bet) in view.bets.items():
            won, mult = False, 0
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
                winners.append(f"<@{uid}>  ({choice})  →  +**{winnings}** {COIN}")
            else:
                losers.append(f"<@{uid}>  ({choice})  →  gubitak")

        win_txt = "\n".join(winners) if winners else "Niko nije pogodio."
        los_txt = "\n".join(losers) if losers else "—"
        await channel.send(embed=emb(
            f"Rulet — Rezultat: {result_num}  {col_name}",
            None,
            discord.Color.green() if winners else discord.Color.red(),
            fields=[
                ("Pobjednici", win_txt, False),
                ("Gubitnici", los_txt, False),
            ]
        ))
        await asyncio.sleep(8)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 6 — MINES
# ─────────────────────────────────────────────────────────────────────────────
MINES_COST = 100
MINES_COUNT = 5


class MinesView(discord.ui.View):
    def __init__(self, mines: set, pot: int, player_id: int):
        super().__init__(timeout=120)
        self.mines = mines
        self.revealed: set = set()
        self.safe = 0
        self.pot = pot
        self.player_id = player_id
        self.active = True
        for i in range(25):
            btn = discord.ui.Button(
                label=f"{i+1:02d}",
                style=discord.ButtonStyle.secondary,
                row=i // 5,
                custom_id=str(i)
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)
        cashout = discord.ui.Button(label="Naplata", style=discord.ButtonStyle.success, row=4)
        cashout.callback = self.cashout_callback
        self.add_item(cashout)

    def _make_callback(self, pos: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player_id:
                return await interaction.response.send_message("Ovo nije tvoja igra!", ephemeral=True)
            if not self.active:
                return await interaction.response.send_message("Igra zavrsena.", ephemeral=True)
            if pos in self.revealed:
                return await interaction.response.send_message("Vec otkriveno!", ephemeral=True)
            self.revealed.add(pos)
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id == str(pos):
                    if pos in self.mines:
                        item.label = "💣"
                        item.style = discord.ButtonStyle.danger
                        item.disabled = True
                    else:
                        item.label = "✅"
                        item.style = discord.ButtonStyle.success
                        item.disabled = True
                    break
            if pos in self.mines:
                self.active = False
                self.stop()
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(
                    embed=emb("BOOM — Mina!", f"<@{self.player_id}> je naletio na minu i izgubio **{self.pot}** {COIN}.", discord.Color.red()),
                    view=self)
                await add_played(self.player_id)
            else:
                self.safe += 1
                potential = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
                await interaction.response.edit_message(
                    embed=emb(
                        f"Sigurno!  ({self.safe} otkriveno)",
                        f"<@{self.player_id}> — nastavi ili naplati!",
                        discord.Color.green(),
                        fields=[("Potencijalni dobitak", f"**{potential}** {COIN}", True)]),
                    view=self)
        return callback

    async def cashout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("Nije tvoja igra!", ephemeral=True)
        if not self.active:
            return await interaction.response.send_message("Igra vec zavrsena.", ephemeral=True)
        self.active = False
        self.stop()
        for item in self.children:
            item.disabled = True
        if self.safe == 0:
            await add_coins(self.player_id, self.pot)
            await interaction.response.edit_message(
                embed=emb("Naplata", f"Nisi otvorio nijedno polje — ulog vracen (**{self.pot}** {COIN}).", discord.Color.gold()),
                view=self)
            return
        winnings = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
        await add_coins(self.player_id, winnings)
        await add_win(self.player_id, 40)
        await interaction.response.edit_message(
            embed=emb("Naplata!", f"<@{self.player_id}> uzima nagradu!", discord.Color.gold(),
                fields=[
                    ("Polja otvorena", str(self.safe), True),
                    ("Dobitak", f"**{winnings}** {COIN}", True),
                ]),
            view=self)


class MinesLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.player: int | None = None
        self.closed = False

    @discord.ui.button(label="Zaigraj Mines  —  100 coina", style=discord.ButtonStyle.danger)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Zatvoreno!", ephemeral=True)
        if self.player is not None:
            return await interaction.response.send_message("Netko vec igra! Cekaj sljedecu rundu.", ephemeral=True)
        await ensure_user(interaction.user.id, interaction.user.display_name)
        ok = await deduct_coins(interaction.user.id, MINES_COST)
        if not ok:
            return await interaction.response.send_message(f"Trebas {MINES_COST} {COIN}!", ephemeral=True)
        self.player = interaction.user.id
        self.closed = True
        self.stop()
        await interaction.response.send_message("Igra pocinje!", ephemeral=True)


class MinesGame:
    NAME = "Mines"
    COLOR = discord.Color.from_rgb(30, 30, 30)

    async def run(self, channel: discord.TextChannel):
        lobby = MinesLobbyView()
        msg = await channel.send(embed=emb(
            "MINES",
            "Jedan igrac otvara polja na mrezi 5×5. U mrezi ima mina — otvori sto vise bez eksplozije!",
            self.COLOR,
            fields=[
                ("Ulog", f"**{MINES_COST}** {COIN}", True),
                ("Mine", str(MINES_COUNT), True),
                ("Trajanje prijave", f"**{TICK}s**", True),
                ("Napomena", "Klikni **Naplata** bilo kad da uzmes coine i zaustavljaš igru.", False),
            ],
            footer="Mines"
        ), view=lobby)
        await asyncio.sleep(TICK)
        lobby.closed = True

        if lobby.player is None:
            await msg.edit(embed=emb("MINES", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        mines = set(random.sample(range(25), MINES_COUNT))
        game_view = MinesView(mines, MINES_COST, lobby.player)
        await msg.edit(embed=emb(
            "MINES — Igra pocela!",
            f"<@{lobby.player}> — klikni polja i izbjegni mine! Klikni **Naplata** kad hoces da uzmes coine.",
            discord.Color.blue()
        ), view=game_view)
        await game_view.wait()
        await asyncio.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 7 — GREBALICA
# ─────────────────────────────────────────────────────────────────────────────
SCRATCH_PRIZES = [
    (0, 40), (30, 20), (60, 15), (100, 10),
    (200, 7), (500, 4), (1000, 2), (2000, 1), (5000, 0.5),
]
SCRATCH_SYMBOLS = {
    0: "✗  ·  ✗  ·  ✗",
    30: "🍒 · 🍒 · ✗",
    60: "🍒 · 🍒 · 🍒",
    100: "⭐ · ⭐ · 🍒",
    200: "⭐ · ⭐ · ⭐",
    500: "💎 · 💎 · ⭐",
    1000: "💎 · 💎 · 💎",
    2000: "👑 · 👑 · 💎",
    5000: "7️⃣ · 7️⃣ · 7️⃣",
}


class ScratchCard(discord.ui.View):
    def __init__(self, owner_id: int, prize: int, item: tuple | None):
        super().__init__(timeout=30)
        self.owner_id = owner_id
        self.prize = prize
        self.item = item
        self.scratched = False

    @discord.ui.button(label="Ogrebi grebalicu!", style=discord.ButtonStyle.success)
    async def scratch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("Nije tvoja grebalica!", ephemeral=True)
        if self.scratched:
            return await interaction.response.send_message("Vec ogrebana!", ephemeral=True)
        self.scratched = True
        button.disabled = True
        self.stop()
        if self.prize > 0:
            await add_coins(self.owner_id, self.prize)
        if self.item:
            await add_item(self.owner_id, self.item[0], self.item[1])
        syms = SCRATCH_SYMBOLS.get(self.prize, "? · ? · ?")
        fields = [("Kombinacija", syms, False), ("Dobitak", f"**{self.prize}** {COIN}", True)]
        if self.item:
            fields.append(("Bonus nagrada", self.item[1], True))
        await interaction.response.edit_message(
            embed=emb("Ogrebana!", None,
                discord.Color.green() if self.prize > 0 else discord.Color.greyple(),
                fields=fields),
            view=self)


class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.buyers: set[int] = set()
        self.closed = False

    @discord.ui.button(label="Kupi Grebalicu  —  40 coina", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Grebalice rasprodate!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.buyers:
            return await interaction.response.send_message("Vec imas grebalicu!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, 40)
        if not ok:
            return await interaction.response.send_message("Trebas **40** coina!", ephemeral=True)
        self.buyers.add(uid)
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
            embed=emb("Tvoja Grebalica", "Klikni dugme da ogrebas!", discord.Color.gold()),
            view=card_view, ephemeral=True)
        await add_played(uid)


class ScratchGame:
    NAME = "Grebalica"
    COLOR = discord.Color.gold()

    async def run(self, channel: discord.TextChannel):
        view = ScratchView()
        msg = await channel.send(embed=emb(
            "GREBALICE — Na Prodaji!",
            "Kupi grebalicu i odmah je ogrebi — možeš dobiti coine, nagrade ili Nitro!",
            self.COLOR,
            fields=[
                ("Cijena", "**40** coina", True),
                ("Trajanje", f"**{TICK}s**", True),
                ("Kombinacije",
                 "🍒 🍒 🍒  →  60 coina\n"
                 "⭐ ⭐ ⭐  →  200 coina\n"
                 "💎 💎 💎  →  1000 coina + Nagrada\n"
                 "7️⃣ 7️⃣ 7️⃣  →  5000 coina + Nitro", False),
            ],
            footer="Grebalica"
        ), view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()
        await msg.edit(view=None)
        if view.buyers:
            await channel.send(embed=emb(
                "Grebalice Zavrsene",
                f"Prodato **{len(view.buyers)}** grebalica.", self.COLOR))
        await asyncio.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 8 — LUTRIJA (pravo animirano izvlacenje)
# ─────────────────────────────────────────────────────────────────────────────
LOTTERY_COST = 60


class LotteryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.tickets: dict[int, list[int]] = {}
        self.pot = 0
        self.closed = False

    @discord.ui.button(label="Kupi Listic  —  60 coina", style=discord.ButtonStyle.primary)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Listici rasprodati!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.tickets:
            return await interaction.response.send_message("Vec imas listic!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, LOTTERY_COST)
        if not ok:
            return await interaction.response.send_message(f"Trebas {LOTTERY_COST} {COIN}!", ephemeral=True)
        nums = sorted(random.sample(range(1, 50), 6))
        self.tickets[uid] = nums
        self.pot += LOTTERY_COST
        nums_str = "   ".join(f"**{n}**" for n in nums)
        await interaction.response.send_message(
            embed=emb("Tvoj Listic", nums_str, discord.Color.blue(),
                      footer=f"Pot: {self.pot} coina"),
            ephemeral=True)


class LotteryGame:
    NAME = "Lutrija"
    COLOR = discord.Color.from_rgb(255, 165, 0)

    async def run(self, channel: discord.TextChannel):
        view = LotteryView()
        msg = await channel.send(embed=emb(
            "LUTRIJA",
            "Kupi listic i cekaj izvlacenje! Ko ima vise pogodaka pobijedi!",
            self.COLOR,
            fields=[
                ("Cijena listicа", f"**{LOTTERY_COST}** {COIN}", True),
                ("Brojevi po listicu", "6 nasumicnih (1–49)", True),
                ("Trajanje prodaje", f"**{TICK}s**", True),
            ],
            footer="Lutrija"
        ), view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.tickets:
            await msg.edit(embed=emb("LUTRIJA", "Nema igraca.", discord.Color.greyple()), view=None)
            return

        await msg.edit(view=None)
        pool = list(range(1, 50))
        random.shuffle(pool)

        drawn = []
        draw_msg = await channel.send(embed=emb(
            "LUTRIJA — Izvlacenje pocinje!",
            "Bubanj se puni...",
            self.COLOR, footer="Izvuceno: 0/6"))

        for i in range(6):
            # Animacija — bubanj se vrti
            for _ in range(5):
                fake = random.randint(1, 49)
                candidates = [f"**{n}**" if j < len(drawn) else ("**??**" if j == len(drawn) else "—")
                              for j, n in enumerate(drawn + [fake] + [0] * (5 - len(drawn)))]
                spin_str = "   ".join(candidates[:6])
                await draw_msg.edit(embed=emb(
                    f"Izvlacenje broja {i+1}/6...",
                    spin_str,
                    self.COLOR, footer=f"Izvuceno: {i}/6"))
                await asyncio.sleep(0.4)

            # Pravi broj
            num = pool[i]
            drawn.append(num)
            drawn_str = "   ".join(f"**{n}**" for n in drawn)
            await draw_msg.edit(embed=emb(
                f"Broj {i+1}:  {num}",
                None, self.COLOR,
                fields=[("Izvuceni do sada", drawn_str, False)],
                footer=f"Izvuceno: {len(drawn)}/6"))
            await asyncio.sleep(1.8)

        # Rezultati
        drawn_set = set(drawn)
        drawn_final = "   ".join(f"**{n}**" for n in sorted(drawn))
        scores = {}
        for uid, nums in view.tickets.items():
            scores[uid] = len(set(nums) & drawn_set)
            await add_played(uid)

        top_score = max(scores.values())
        winners = [uid for uid, s in scores.items() if s == top_score]

        if top_score == 0:
            await draw_msg.edit(embed=emb(
                "LUTRIJA — Nema Pobjednika",
                "Niko nije imao pogodaka.", discord.Color.red(),
                fields=[("Izvuceni brojevi", drawn_final, False)]))
        else:
            share = view.pot // len(winners)
            bonus_item = None
            for uid in winners:
                await add_coins(uid, share)
                await add_win(uid, 50)
                if top_score >= 5:
                    rtype, item = rand_prize("rare")
                    await add_item(uid, rtype, item)
                    bonus_item = item
            mention = "  ".join(f"<@{uid}>" for uid in winners)
            fields = [
                ("Izvuceni brojevi", drawn_final, False),
                ("Pobjednici", mention, False),
                ("Pogodaka", f"**{top_score}/6**", True),
                ("Dobitak po osobi", f"**{share}** {COIN}", True),
            ]
            if bonus_item:
                fields.append(("Bonus nagrada", bonus_item, False))
            await draw_msg.edit(embed=emb(
                "LUTRIJA — Pobjednici!", None, discord.Color.green(), fields=fields))
        await asyncio.sleep(10)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 9 — EMOJI GUESS
# ─────────────────────────────────────────────────────────────────────────────
EMOJI_QUESTIONS = [
    {"emojis": "👠 ⏰ 🎃",  "answers": ["cinderella", "pepeljuga"],              "hint": "Disney bajka"},
    {"emojis": "🌊 🐠 🔍",  "answers": ["nemo", "finding nemo"],                 "hint": "Animirani film"},
    {"emojis": "🦁 👑 🌍",  "answers": ["kralj lavova", "lion king", "simba"],   "hint": "Disney film"},
    {"emojis": "❄️ 👸 ✨", "answers": ["frozen", "ledeno kraljevstvo", "elsa"],  "hint": "Animirani film"},
    {"emojis": "🕷️ 👦 🏙️","answers": ["spiderman", "spider-man"],               "hint": "Superjunak"},
    {"emojis": "🦇 🤵 🌃",  "answers": ["batman", "betmen"],                     "hint": "Gotham City"},
    {"emojis": "⚡ 🧙 📚",  "answers": ["harry potter", "hari poter"],           "hint": "Carobnjak"},
    {"emojis": "💍 🧝 🌋",  "answers": ["lord of the rings", "lotr", "gospodar prstenova"], "hint": "Fantasy epic"},
    {"emojis": "🚀 👨‍🚀 ♾️","answers": ["interstellar"],                          "hint": "Nolan sci-fi"},
    {"emojis": "🃏 🤡 🃏",  "answers": ["joker", "dzoker"],                      "hint": "DC vilain"},
    {"emojis": "🐉 🔥 ⚔️", "answers": ["igra prijestolja", "game of thrones"],  "hint": "HBO serija"},
    {"emojis": "💊 🔵 🔴",  "answers": ["matrix", "matriks"],                    "hint": "Sci-fi klasik"},
    {"emojis": "🧟 🔫 🌍",  "answers": ["walking dead"],                         "hint": "AMC serija"},
    {"emojis": "👨‍🍳 💀 🧪","answers": ["breaking bad"],                          "hint": "Hemicar-kriminalac"},
    {"emojis": "🔫 🕶️ 📱", "answers": ["john wick", "dzon vik"],                "hint": "Keanu Reeves akcija"},
    {"emojis": "🧠 🌀 💤",  "answers": ["inception", "san"],                     "hint": "Nolan, snovi unutar snova"},
    {"emojis": "🦈 🏖️ 🩸", "answers": ["ajkula", "jaws", "shark"],              "hint": "Spielberg horor"},
]

EMOJI_REWARD = 250
EMOJI_TIME = 45


class EmojiGame:
    NAME = "Emoji Guess"
    COLOR = discord.Color.from_rgb(255, 200, 0)

    async def run(self, channel: discord.TextChannel):
        q = random.choice(EMOJI_QUESTIONS)
        winner_uid = None
        winner_msg = None

        msg = await channel.send(embed=emb(
            "EMOJI GUESS",
            f"# {q['emojis']}\n\nNapisi u chat sta ovi emoji predstavljaju!",
            self.COLOR,
            fields=[
                ("Hint", q['hint'], True),
                ("Nagrada", f"**{EMOJI_REWARD}** {COIN}", True),
                ("Vrijeme", f"**{EMOJI_TIME}s**", True),
            ],
            footer="Emoji Guess"
        ))

        def check(m: discord.Message):
            return (m.channel.id == channel.id and not m.author.bot
                    and any(a in m.content.lower() for a in q["answers"]))

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
            result = emb("Tacan Odgovor!", None, discord.Color.green(),
                fields=[
                    ("Pobjednik", f"<@{winner_uid}>", True),
                    ("Dobitak", f"**{EMOJI_REWARD}** {COIN}", True),
                    ("Tacan odgovor", q['answers'][0].title(), True),
                ])
        else:
            result = emb("Vrijeme Isteklo", "Niko nije pogodio.", discord.Color.red(),
                fields=[("Tacan odgovor", q['answers'][0].title(), True)])
        await msg.edit(embed=result)
        await asyncio.sleep(8)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 10 — JACKPOT EVENT
# ─────────────────────────────────────────────────────────────────────────────
JACKPOT_COST = 120


class JackpotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.entrants: list[int] = []
        self.pot = 0
        self.closed = False

    @discord.ui.button(label="Ulozi u Jackpot  —  120 coina", style=discord.ButtonStyle.danger)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Jackpot zatvoren!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.entrants:
            return await interaction.response.send_message(
                f"Vec si u igri! Pot: **{self.pot}** {COIN}", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, JACKPOT_COST)
        if not ok:
            return await interaction.response.send_message(f"Trebas {JACKPOT_COST} {COIN}!", ephemeral=True)
        self.entrants.append(uid)
        self.pot += JACKPOT_COST
        await interaction.response.send_message(
            f"U igri si! Igraci: **{len(self.entrants)}**  |  Pot: **{self.pot}** {COIN}", ephemeral=True)


class JackpotGame:
    NAME = "Jackpot Event"
    COLOR = discord.Color.from_rgb(200, 30, 30)

    async def run(self, channel: discord.TextChannel):
        view = JackpotView()
        msg = await channel.send(embed=emb(
            "JACKPOT EVENT",
            "Svi ulaze — **jedan** pobijedi sve!",
            self.COLOR,
            fields=[
                ("Ulog", f"**{JACKPOT_COST}** {COIN}", True),
                ("Nagrada", "Cijeli pot + Legendarni item", True),
                ("Trajanje prijava", f"**{TICK}s**", True),
                ("Kako radi", "Sto vise igraca, veci pot. Jedan sretan pobijedi sve!", False),
            ],
            footer="Jackpot Event"
        ), view=view)
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if len(view.entrants) < 2:
            await msg.edit(embed=emb("JACKPOT EVENT",
                "Premalo igraca! Ulozi vraceni.", discord.Color.red()), view=None)
            for uid in view.entrants:
                await add_coins(uid, JACKPOT_COST)
            return

        for countdown in [5, 4, 3, 2, 1]:
            await msg.edit(embed=emb(
                f"JACKPOT — Izvlacenje za {countdown}...",
                None, self.COLOR,
                fields=[
                    ("Igraci", str(len(view.entrants)), True),
                    ("Pot", f"**{view.pot}** {COIN}", True),
                ]), view=None)
            await asyncio.sleep(1)

        winner = random.choice(view.entrants)
        await add_coins(winner, view.pot)
        await add_win(winner, 100)
        rtype, item = rand_prize("legendary")
        await add_item(winner, rtype, item)
        for uid in view.entrants:
            await add_played(uid)

        await msg.edit(embed=emb(
            "JACKPOT — Pobjednik!",
            f"<@{winner}> uzima sve!",
            discord.Color.gold(),
            fields=[
                ("Pot", f"**{view.pot}** {COIN}", True),
                ("Legendarni item", item, True),
            ]
        ))
        await asyncio.sleep(10)


# ─────────────────────────────────────────────────────────────────────────────
# GAME REGISTRY
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
