"""
10 auto-posting igara s Discord button Views.
Poboljšani embedi i pravo animirano izvlačenje lutrije.
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
TICK = 60
RESULT_DELAY = 3

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
        item = random.choice(NITRO)
        return "nitro", item
    if tier == "rare":
        if random.random() < 0.5:
            return "avatar", random.choice(AVATARS)
        return "decoration", random.choice(DECORATIONS)
    return "decoration", random.choice(DECORATIONS)


def embed(title: str, desc: str = "", color=discord.Color.gold(), *, fields=None, footer=None) -> discord.Embed:
    em = discord.Embed(title=title, description=desc or None, color=color)
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

    @discord.ui.button(label="Kupi listic — 80 coina", style=discord.ButtonStyle.green)
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
                f"Nemas dovoljno coina. Imas **{coins}** {COIN}", ephemeral=True
            )
        card = sorted(random.sample(range(1, 76), 15))
        self.players[uid] = card
        self.pot += self.TICKET_COST
        card_str = "  ".join(f"`{n:2d}`" for n in card)
        await interaction.response.send_message(
            embed=embed(
                "Tvoj Bingo Listic",
                card_str,
                discord.Color.green(),
                footer=f"Pot: {self.pot} coina"
            ),
            ephemeral=True
        )


class BingoGame:
    NAME = "Bingo"
    COLOR = discord.Color.blue()

    async def run(self, channel: discord.TextChannel):
        view = BingoView()
        msg = await channel.send(
            embed=embed(
                "BINGO",
                f"Kupi listic za **{BingoView.TICKET_COST}** {COIN} i pokusaj prvi oznaciti svih 15 brojeva!\n"
                f"Bot vuce brojeve 1–75 jedan po jedan. Ko prvi skupi sve — pobijedi!\n\n"
                f"Prijave traju **{TICK} sekundi**.",
                self.COLOR,
                footer=f"Bingo  •  Listic: {BingoView.TICKET_COST} coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if len(view.players) < 2:
            await msg.edit(
                embed=embed("BINGO — Otkazano", "Premalo igraca (min 2). Ulog vracen.", discord.Color.red()),
                view=None
            )
            for uid in view.players:
                await add_coins(uid, BingoView.TICKET_COST)
            return

        pool = list(range(1, 76))
        random.shuffle(pool)
        marked: dict[int, set] = {uid: set() for uid in view.players}
        called = []
        winner_uid = None

        draw_msg = await channel.send(
            embed=embed("BINGO — Izvlacenje", f"Igraci: **{len(view.players)}**  |  Pot: **{view.pot}** {COIN}", self.COLOR)
        )

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
                for uid in view.players
            )
            await draw_msg.edit(
                embed=embed(
                    f"BINGO — Broj {num}",
                    f"**Zadnjih 10:** {last10}\n\n{progress}",
                    self.COLOR,
                    footer=f"Izvuceno: {len(called)}/75"
                )
            )
            if winner_uid:
                break
            await asyncio.sleep(4)

        if winner_uid:
            await add_coins(winner_uid, view.pot)
            await add_win(winner_uid, 80)
            _, item = rand_prize("rare")
            await add_item(winner_uid, "decoration", item)
            result = embed(
                "BINGO — Pobjednik!",
                f"<@{winner_uid}> je oznacio sve brojeve!",
                discord.Color.green(),
                fields=[
                    ("Dobitak", f"**{view.pot}** {COIN}", True),
                    ("Bonus nagrada", item, True),
                ]
            )
        else:
            result = embed("BINGO", "Niko nije pobijedio.", discord.Color.greyple())

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

def wheel_visual(highlight: int) -> str:
    lines = []
    for i, (label, _, _) in enumerate(WHEEL_SEGMENTS):
        if i == highlight:
            lines.append(f"  > {label}")
        else:
            lines.append(f"    {label}")
    return "```\n" + "\n".join(lines) + "\n```"


class WheelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.spinners: list[int] = []
        self.closed = False

    @discord.ui.button(label="Zavrti kolo — 60 coina", style=discord.ButtonStyle.blurple)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Kolo je zatvoreno!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.spinners:
            return await interaction.response.send_message("Vec si prijavljen!", ephemeral=True)
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, SPIN_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"Trebas **{SPIN_COST}** {COIN}. Imas **{coins}** {COIN}", ephemeral=True
            )
        self.spinners.append(uid)
        await interaction.response.send_message("Prijavljen! Cekaj spin...", ephemeral=True)


class WheelGame:
    NAME = "Kolo Srece"
    COLOR = discord.Color.purple()

    async def run(self, channel: discord.TextChannel):
        view = WheelView()
        msg = await channel.send(
            embed=embed(
                "KOLO SRECE",
                f"Klikni dugme da se prijavis za **{SPIN_COST}** {COIN}.\n"
                f"Svaki igrac dobiva svoj spin — kolo se animira i otkriva nagradu.\n"
                f"Moguce nagrade: coini, dekoracije, avatari, ili **Nitro**!\n\n"
                f"Prijave traju **{TICK} sekundi**.",
                self.COLOR,
                footer=f"Kolo Srece  •  Ulaznica: {SPIN_COST} coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.spinners:
            await msg.edit(embed=embed("KOLO SRECE", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        for uid in view.spinners:
            spin_msg = await channel.send(embed=embed("Kolo se vrti...", wheel_visual(0), self.COLOR))
            prev = -1
            for _ in range(10):
                pos = random.randint(0, len(WHEEL_SEGMENTS) - 1)
                while pos == prev:
                    pos = random.randint(0, len(WHEEL_SEGMENTS) - 1)
                prev = pos
                await spin_msg.edit(embed=embed("Kolo se vrti...", wheel_visual(pos), self.COLOR))
                await asyncio.sleep(0.5)

            segment = random.choices(WHEEL_SEGMENTS, weights=WHEEL_WEIGHTS)[0]
            label, amount, stype = segment
            final_pos = WHEEL_SEGMENTS.index(segment)
            await spin_msg.edit(embed=embed("Kolo stalo!", wheel_visual(final_pos), self.COLOR))
            await asyncio.sleep(1)

            if stype == "bankrot":
                lost = min(await get_coins(uid), random.randint(50, 300))
                await add_coins(uid, -lost)
                result_em = embed(
                    "Kolo Srece — Rezultat",
                    f"<@{uid}> → **{label}**\nGubis **{lost}** {COIN}!",
                    discord.Color.dark_red()
                )
            elif stype == "coins":
                await add_coins(uid, amount)
                result_em = embed(
                    "Kolo Srece — Rezultat",
                    f"<@{uid}> → **{label}**",
                    discord.Color.green(),
                    fields=[("Dobitak", f"+**{amount}** {COIN}", True)]
                )
            elif stype in ("decoration", "avatar", "nitro"):
                tier = "legendary" if stype == "nitro" else "rare" if stype == "avatar" else "common"
                rtype, item = rand_prize(tier)
                await add_item(uid, rtype, item)
                result_em = embed(
                    "Kolo Srece — Rezultat",
                    f"<@{uid}> → **{label}**",
                    discord.Color.blurple(),
                    fields=[("Nagrada", item, True)]
                )
            else:
                result_em = embed("Kolo Srece — Rezultat", f"<@{uid}> — Nista ovaj put.", discord.Color.greyple())

            await add_played(uid)
            await spin_msg.edit(embed=result_em)
            await asyncio.sleep(3)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 3 — SLOT MACHINE
# ─────────────────────────────────────────────────────────────────────────────
REELS = ["Cherry", "Lemon", "Grape", "Star", "Diamond", "Bell", "Seven", "Wild", "Crown", "Clover"]
REEL_DISPLAY = {
    "Cherry": "Ch", "Lemon": "Lm", "Grape": "Gr", "Star": "St",
    "Diamond": "Di", "Bell": "Bl", "Seven": "7 ", "Wild": "Wl",
    "Crown": "Cr", "Clover": "Cv"
}
JACKPOTS = {
    ("Seven",    "Seven",    "Seven"):    (20, "legendary"),
    ("Diamond",  "Diamond",  "Diamond"):  (15, "rare"),
    ("Star",     "Star",     "Star"):     (10, "common"),
    ("Crown",    "Crown",    "Crown"):    (8,  "common"),
    ("Clover",   "Clover",   "Clover"):   (7,  "common"),
    ("Bell",     "Bell",     "Bell"):     (5,  "common"),
    ("Grape",    "Grape",    "Grape"):    (4,  "common"),
    ("Lemon",    "Lemon",    "Lemon"):    (3,  "common"),
    ("Cherry",   "Cherry",   "Cherry"):  (2,  "common"),
}
SLOT_COST = 50

def slot_display(reels: tuple | list) -> str:
    d = [REEL_DISPLAY.get(r, r[:2]) for r in reels]
    return f"```\n[ {d[0]} | {d[1]} | {d[2]} ]\n```"


class SlotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.players: set[int] = set()
        self.closed = False

    @discord.ui.button(label="Zaigraj — 50 coina", style=discord.ButtonStyle.green)
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
                f"Trebas **{SLOT_COST}** {COIN}. Imas **{coins}** {COIN}", ephemeral=True
            )
        self.players.add(uid)
        await interaction.response.send_message("Prijavljen! Cekaj vrtnju...", ephemeral=True)


class SlotGame:
    NAME = "Slot Machine"
    COLOR = discord.Color.orange()

    async def run(self, channel: discord.TextChannel):
        view = SlotView()
        paytable = (
            "```\n"
            "Seven  Seven  Seven  →  x20 + Nitro\n"
            "Diamond Diamond Diamond →  x15 + Nagrada\n"
            "Star   Star   Star   →  x10\n"
            "Ostale tri iste       →  x2 – x8\n"
            "Dva ista              →  x1.5\n"
            "```"
        )
        msg = await channel.send(
            embed=embed(
                "SLOT MACHINE",
                f"Klikni dugme i ulozi **{SLOT_COST}** {COIN}!\n\n{paytable}\n"
                f"Prijave traju **{TICK}s**.",
                self.COLOR,
                footer=f"Slot Machine  •  Ulog: {SLOT_COST} coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.players:
            await msg.edit(embed=embed("SLOT MACHINE", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        await msg.edit(embed=embed("SLOT MACHINE", "Vrtnja pocinje...", self.COLOR), view=None)

        for uid in view.players:
            sm = await channel.send(embed=embed("Vrtim...", slot_display(["?", "?", "?"]), self.COLOR))
            for _ in range(6):
                r = [random.choice(REELS) for _ in range(3)]
                await asyncio.sleep(0.45)
                await sm.edit(embed=embed("Vrtim...", slot_display(r), self.COLOR))

            final = tuple(random.choice(REELS) for _ in range(3))
            await asyncio.sleep(0.45)

            jackpot = JACKPOTS.get(final)
            if jackpot:
                mult, tier = jackpot
                winnings = SLOT_COST * mult
                await add_coins(uid, winnings)
                await add_win(uid, 60)
                rtype, item = rand_prize(tier)
                await add_item(uid, rtype, item)
                result_em = embed(
                    "JACKPOT!",
                    slot_display(final),
                    discord.Color.gold(),
                    fields=[
                        ("Igrac", f"<@{uid}>", True),
                        ("Multiplikator", f"x{mult}", True),
                        ("Dobitak", f"**{winnings}** {COIN}", True),
                        ("Bonus", item, False),
                    ]
                )
            elif len(set(final)) < 3:
                winnings = int(SLOT_COST * 1.5)
                await add_coins(uid, winnings)
                await add_played(uid)
                result_em = embed(
                    "Dva ista!",
                    slot_display(final),
                    discord.Color.yellow(),
                    fields=[("Igrac", f"<@{uid}>", True), ("Dobitak", f"**{winnings}** {COIN}", True)]
                )
            else:
                await add_played(uid)
                result_em = embed(
                    "Nema podudaranja",
                    slot_display(final),
                    discord.Color.red(),
                    fields=[("Igrac", f"<@{uid}>", True), ("Gubitak", f"**{SLOT_COST}** {COIN}", True)]
                )

            await sm.edit(embed=result_em)
            await asyncio.sleep(4)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 4 — NASTAVI PJESMU
# ─────────────────────────────────────────────────────────────────────────────
SONGS = [
    {"artist": "Jala Brat & Buba Corelli", "title": "Pilula",
     "lyric": "Sipam ti pilulu u casu vina, volim te ko sto voli se Bosna i Hercegovina...",
     "answer": ["pilula"]},
    {"artist": "Jala Brat & Buba Corelli", "title": "Limuzina",
     "lyric": "Doci cu po tebe, ko sto kaze pjesma, u crnoj ___ kroz grad...",
     "answer": ["limuzina", "limuzi"]},
    {"artist": "Jala Brat", "title": "Zvaka",
     "lyric": "Zvacim ___, gledam u tavan, nema sna, sutra novo jutro, nov' dan...",
     "answer": ["zvaka", "zvaku"]},
    {"artist": "Buba Corelli", "title": "Ferrari",
     "lyric": "Vozim ___, puna kesa, kazu da sam lud, ali to je samo stil mog zivota...",
     "answer": ["ferrari", "ferari"]},
    {"artist": "Jala Brat", "title": "Litar Krvi",
     "lyric": "Dajem ___ za tebe, to je ljubav prava, niko drugi ne zna sto to znaci...",
     "answer": ["litar krvi", "litar", "krvi"]},
    {"artist": "Buba Corelli & Jala Brat", "title": "Kuna Pela",
     "lyric": "___, ___ — letis kao pcela, zaradujes kunu, srce moje voli tebe cela...",
     "answer": ["kuna pela", "kuna", "pela"]},
    {"artist": "Jala Brat", "title": "Golubica",
     "lyric": "Moja ___ bijela, leti visoko iznad grada, samo da si sretna...",
     "answer": ["golubica"]},
    {"artist": "Buba Corelli", "title": "Sjena",
     "lyric": "Pratim te ko ___, kud god krenEs, tu sam ja, ne mogu bez tebe...",
     "answer": ["sjena", "siena"]},
    {"artist": "Jala Brat & Buba Corelli", "title": "Novac i Zavist",
     "lyric": "___ i zavist, to je njihov problem, mi samo gledamo naprijed...",
     "answer": ["novac", "novac i zavist"]},
    {"artist": "Jala Brat", "title": "Sampanjac",
     "lyric": "Otvori ___, slavimo veceras, sve je moguce kad si pored mene...",
     "answer": ["sampanjac", "sampanjac"]},
    {"artist": "Buba Corelli", "title": "Igra",
     "lyric": "Ovo je samo ___, ne uzimaj srcu blizu, znas da nisam tvoj tip...",
     "answer": ["igra"]},
    {"artist": "Jala Brat", "title": "Dijamant",
     "lyric": "Ti si moj ___, rijetka, skupa, ne mijenjam te ni za sto...",
     "answer": ["dijamant"]},
]

QUIZ_REWARD = 300
QUIZ_TIME = 60


class QuizGame:
    NAME = "Nastavi Pjesmu"
    COLOR = discord.Color.from_rgb(255, 100, 200)

    async def run(self, channel: discord.TextChannel):
        song = random.choice(SONGS)
        winner_uid = None
        winner_answer = None

        msg = await channel.send(
            embed=embed(
                "NASTAVI PJESMU",
                f"*\"{song['lyric']}\"*\n\n"
                f"Izvadac: **{song['artist']}**\n\n"
                f"Napiši naziv pjesme u chat!",
                self.COLOR,
                fields=[("Nagrada", f"**{QUIZ_REWARD}** {COIN}", True), ("Vrijeme", f"**{QUIZ_TIME}s**", True)],
                footer=f"Nastavi Pjesmu  •  {song['artist']}"
            )
        )

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
            result = embed(
                "Tacan Odgovor!",
                f"<@{winner_uid}> je pogodio!",
                discord.Color.green(),
                fields=[
                    ("Odgovor", f'"{winner_answer}"', False),
                    ("Trazeno", song['title'], True),
                    ("Dobitak", f"**{QUIZ_REWARD}** {COIN}", True),
                ],
                footer=f"{song['artist']} — {song['title']}"
            )
        else:
            result = embed(
                "Vrijeme Isteklo",
                None,
                discord.Color.red(),
                fields=[
                    ("Pjesma", song['title'], True),
                    ("Izvadac", song['artist'], True),
                ],
                footer=f"{song['artist']} — {song['title']}"
            )
        await msg.edit(embed=result)
        await asyncio.sleep(8)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 5 — RULET (animated)
# ─────────────────────────────────────────────────────────────────────────────
ROULETTE_NUMBERS = list(range(0, 37))
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]

def roulette_color_label(n: int) -> str:
    if n == 0:
        return "ZELENA"
    return "CRVENA" if n in RED_NUMBERS else "CRNA"

def roulette_wheel_art(ball_pos: int) -> str:
    size = len(WHEEL_ORDER)
    start = (ball_pos - 4) % size
    segment = []
    for i in range(9):
        idx = (start + i) % size
        n = WHEEL_ORDER[idx]
        col = "Z" if n == 0 else ("C" if n in RED_NUMBERS else "B")
        label = f"{col}{n:02d}"
        segment.append(f"[{label}]" if i == 4 else f" {label} ")
    return (
        "```\n"
        f"  {segment[0]} {segment[1]} {segment[2]} {segment[3]}\n"
        f"         {segment[4]}  <-- kugla\n"
        f"  {segment[5]} {segment[6]} {segment[7]} {segment[8]}\n"
        "```"
    )

ROULETTE_COST = 70


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
                f"Vec si ulozio na **{self.bets[uid][0]}**!", ephemeral=True
            )
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, ROULETTE_COST)
        if not ok:
            coins = await get_coins(uid)
            return await interaction.response.send_message(
                f"Trebas **{ROULETTE_COST}** {COIN}. Imas **{coins}** {COIN}", ephemeral=True
            )
        self.bets[uid] = (choice, ROULETTE_COST)
        await interaction.response.send_message(
            f"Ulozio si **{ROULETTE_COST}** {COIN} na **{choice}**!", ephemeral=True
        )

    @discord.ui.button(label="Crvena (x2)", style=discord.ButtonStyle.danger, row=0)
    async def bet_red(self, i, b): await self._place_bet(i, "crvena")

    @discord.ui.button(label="Crna (x2)", style=discord.ButtonStyle.secondary, row=0)
    async def bet_black(self, i, b): await self._place_bet(i, "crna")

    @discord.ui.button(label="Zelena/Nula (x14)", style=discord.ButtonStyle.success, row=0)
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
        paytable = (
            "```\n"
            "Crvena / Crna   →  x2\n"
            "Parno / Neparno →  x2\n"
            "1–18  /  19–36  →  x2\n"
            "Zelena (0)      →  x14\n"
            "```"
        )
        msg = await channel.send(
            embed=embed(
                "RULET",
                f"Odaberi okladu i ulozi **{ROULETTE_COST}** {COIN}!\n\n{paytable}\n"
                f"Oklade primamo **{TICK} sekundi**.",
                self.COLOR,
                footer=f"Rulet  •  Ulog: {ROULETTE_COST} coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.bets:
            await msg.edit(embed=embed("RULET", "Niko nije oklado.", discord.Color.greyple()), view=None)
            return

        wheel_msg = await channel.send(embed=embed("Rulet — Kugla se kotrlja...", roulette_wheel_art(0), self.COLOR))
        ball_pos = 0
        steps = random.randint(22, 40)
        for i in range(steps):
            ball_pos = (ball_pos + 1) % len(WHEEL_ORDER)
            delay = 0.12 + (i / steps) * 0.55
            await wheel_msg.edit(embed=embed("Rulet — Kugla se kotrlja...", roulette_wheel_art(ball_pos), self.COLOR))
            await asyncio.sleep(delay)

        result_num = random.randint(0, 36)
        col_name = roulette_color_label(result_num)

        await wheel_msg.edit(
            embed=embed(
                f"Rulet — Broj: {result_num}  ({col_name})",
                roulette_wheel_art(ball_pos),
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
                winners.append(f"<@{uid}> — {choice}  +**{winnings}** {COIN}")
            else:
                losers.append(f"<@{uid}> — {choice}  ❌")

        win_txt = "\n".join(winners) if winners else "Niko nije pogodio."
        los_txt = "\n".join(losers) if losers else "—"
        await channel.send(
            embed=embed(
                f"Rulet — Rezultat: {result_num}  {col_name}",
                None,
                discord.Color.green() if winners else discord.Color.red(),
                fields=[
                    ("Pobjednici", win_txt, False),
                    ("Gubitnici", los_txt, False),
                ]
            )
        )
        await asyncio.sleep(8)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 6 — MINES (button grid)
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
                label=f"{i+1:02d}",
                style=discord.ButtonStyle.secondary,
                row=i // MINES_COLS,
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
                        item.label = "MINA"
                        item.style = discord.ButtonStyle.danger
                        item.disabled = True
                    else:
                        item.label = "OK"
                        item.style = discord.ButtonStyle.success
                        item.disabled = True
                    break

            if pos in self.mines:
                self.active = False
                self.stop()
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(
                    embed=embed(
                        "BOOM — Naletio si na minu!",
                        f"Izgubio si **{self.pot}** {COIN}.",
                        discord.Color.red()
                    ),
                    view=self
                )
                await add_played(self.player_id)
            else:
                self.safe += 1
                potential = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
                await interaction.response.edit_message(
                    embed=embed(
                        f"Sigurno! ({self.safe} otvoreno)",
                        f"Potencijalni dobitak: **{potential}** {COIN}\n\nNastavi ili klikni **Naplata**!",
                        discord.Color.green()
                    ),
                    view=self
                )
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
                embed=embed("Naplata", f"Nisi otvorio nijedno polje — ulog vracen (**{self.pot}** {COIN}).", discord.Color.gold()),
                view=self
            )
            return
        winnings = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
        await add_coins(self.player_id, winnings)
        await add_win(self.player_id, 40)
        await interaction.response.edit_message(
            embed=embed(
                "Naplata",
                f"Otvorio si **{self.safe}** polja bez mine!",
                discord.Color.gold(),
                fields=[("Dobitak", f"**{winnings}** {COIN}", True)]
            ),
            view=self
        )


class MinesLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.player: int | None = None
        self.closed = False

    @discord.ui.button(label="Zaigraj Mines — 100 coina", style=discord.ButtonStyle.danger)
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
        msg = await channel.send(
            embed=embed(
                "MINES",
                f"Jedan igrac otvara polja na mrezi 5×5.\n"
                f"U mrezi ima **{MINES_COUNT}** mina — otvori sto vise bez eksplozije!\n\n"
                f"Ulog: **{MINES_COST}** {COIN}  |  Naplata kad god hoces.\n"
                f"Prijava traje **{TICK}s**.",
                self.COLOR,
                footer=f"Mines  •  Ulog: {MINES_COST} coina"
            ),
            view=lobby
        )
        await asyncio.sleep(TICK)
        lobby.closed = True

        if lobby.player is None:
            await msg.edit(embed=embed("MINES", "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        mines = set(random.sample(range(25), MINES_COUNT))
        game_view = MinesView(mines, MINES_COST, lobby.player, msg)
        await msg.edit(
            embed=embed(
                "MINES — Klikni Polja!",
                f"<@{lobby.player}> — Otvori polja! Izbjegni mine.\n"
                f"Klikni **Naplata** kad hoces da naplacis.",
                discord.Color.blue()
            ),
            view=game_view
        )
        await game_view.wait()
        await asyncio.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 7 — GREBALICA (scratch card)
# ─────────────────────────────────────────────────────────────────────────────
SCRATCH_PRIZES = [
    (0, 40), (30, 20), (60, 15), (100, 10),
    (200, 7), (500, 4), (1000, 2), (2000, 1), (5000, 0.5),
]

SCRATCH_SYMBOLS = {
    0: "  X  |  X  |  X  ",
    30: " Ch  | Ch  |  X  ",
    60: " Ch  | Ch  | Ch  ",
    100: " St  | St  | Ch  ",
    200: " St  | St  | St  ",
    500: " Di  | Di  | St  ",
    1000: " Di  | Di  | Di  ",
    2000: " Cr  | Cr  | Di  ",
    5000: "  7  |  7  |  7  ",
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
        prize = self.prize
        item = self.item
        if prize > 0:
            await add_coins(self.owner_id, prize)
        if item:
            await add_item(self.owner_id, item[0], item[1])
        syms = SCRATCH_SYMBOLS.get(prize, "  ?  |  ?  |  ?  ")
        extra_fields = []
        if item:
            extra_fields.append(("Bonus nagrada", item[1], False))
        color = discord.Color.green() if prize > 0 else discord.Color.greyple()
        await interaction.response.edit_message(
            embed=embed(
                "Ogrebana!",
                f"```\n[ {syms} ]\n```",
                color,
                fields=[("Dobitak", f"**{prize}** {COIN}", True)] + extra_fields
            ),
            view=self
        )


class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.buyers: set[int] = set()
        self.closed = False

    @discord.ui.button(label="Kupi Grebalicu — 40 coina", style=discord.ButtonStyle.success)
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
            embed=embed("Tvoja Grebalica", "Klikni dugme da ogrebas!", discord.Color.gold()),
            view=card_view,
            ephemeral=True
        )
        await add_played(uid)


class ScratchGame:
    NAME = "Grebalica"
    COLOR = discord.Color.gold()

    async def run(self, channel: discord.TextChannel):
        view = ScratchView()
        paytable = (
            "```\n"
            "[ X  | X  | X  ]  →  Nista\n"
            "[ Ch | Ch | Ch ]  →  60 coina\n"
            "[ St | St | St ]  →  200 coina\n"
            "[ Di | Di | Di ]  →  1000 coina + Nagrada\n"
            "[ 7  | 7  | 7  ]  →  5000 coina + Nitro\n"
            "```"
        )
        msg = await channel.send(
            embed=embed(
                "GREBALICE — Na Rasprodaji!",
                f"Kupi grebalicu za **40** {COIN} i ogrebi je odmah!\n\n{paytable}\n"
                f"Dostupne **{TICK}s**!",
                self.COLOR,
                footer="Grebalica  •  Cijena: 40 coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()
        await msg.edit(view=None)
        if view.buyers:
            await channel.send(
                embed=embed("Grebalice Zavrsene", f"Prodato **{len(view.buyers)}** grebalica.", self.COLOR)
            )
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

    @discord.ui.button(label="Kupi Listic — 60 coina", style=discord.ButtonStyle.primary)
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
        nums_display = "   ".join(f"`{n:2d}`" for n in nums)
        await interaction.response.send_message(
            embed=embed(
                "Tvoj Listic",
                nums_display,
                discord.Color.blue(),
                footer=f"Pot: {self.pot} coina"
            ),
            ephemeral=True
        )


def lottery_drum_art(revealed: list[int], spinning: bool = False) -> str:
    """Prikazuje bubanj sa do sada izvucenim brojevima."""
    slots = []
    for i in range(6):
        if i < len(revealed):
            slots.append(f"[{revealed[i]:2d}]")
        elif spinning and i == len(revealed):
            slots.append("[ ? ]")
        else:
            slots.append("[   ]")

    top =    "┌─────────────────────────────────────┐"
    mid_1 =  f"│   {slots[0]}  {slots[1]}  {slots[2]}               │"
    mid_2 =  f"│   {slots[3]}  {slots[4]}  {slots[5]}               │"
    bot =    "└─────────────────────────────────────┘"
    return f"```\n{top}\n{mid_1}\n{mid_2}\n{bot}\n```"


class LotteryGame:
    NAME = "Lutrija"
    COLOR = discord.Color.from_rgb(255, 165, 0)

    async def run(self, channel: discord.TextChannel):
        view = LotteryView()
        msg = await channel.send(
            embed=embed(
                "LUTRIJA",
                f"Kupi listic za **{LOTTERY_COST}** {COIN}!\n"
                f"Svaki igrac dobiva 6 nasumicnih brojeva (1–49).\n"
                f"Bot ce izvlaciti 6 dobitnih brojeva — ko ima vise pogodaka pobijedi!\n\n"
                f"Listici se prodaju **{TICK}s**.",
                self.COLOR,
                footer=f"Lutrija  •  Listic: {LOTTERY_COST} coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if not view.tickets:
            await msg.edit(embed=embed("LUTRIJA", "Nema igraca.", discord.Color.greyple()), view=None)
            return

        await msg.edit(view=None)

        # ── PRAVO ANIMIRANO IZVLACENJE ────────────────────────────────────────
        pool = list(range(1, 50))
        random.shuffle(pool)

        drawn = []
        draw_msg = await channel.send(
            embed=embed(
                "LUTRIJA — Izvlacenje pocinje!",
                lottery_drum_art([]),
                self.COLOR,
                footer="Izvuceno: 0/6"
            )
        )

        for i in range(6):
            # Animacija bubnja — prikazuje random brojeve prije nego padne pravi
            for _ in range(6):
                fake = random.randint(1, 49)
                while fake in drawn:
                    fake = random.randint(1, 49)
                await draw_msg.edit(
                    embed=embed(
                        f"Izvlacenje broja {i+1}/6...",
                        lottery_drum_art(drawn, spinning=True) + f"\n*Bubanj se vrti...*",
                        self.COLOR,
                        footer=f"Izvuceno: {i}/6"
                    )
                )
                await asyncio.sleep(0.4)

            # Izvuci pravi broj
            num = pool[i]
            drawn.append(num)

            # Prikazi rezultat ovog broja
            drawn_str = "   ".join(f"**{n}**" for n in drawn)
            await draw_msg.edit(
                embed=embed(
                    f"Broj {i+1}:  {num}",
                    lottery_drum_art(drawn),
                    self.COLOR,
                    fields=[("Izvuceni do sada", drawn_str, False)],
                    footer=f"Izvuceno: {len(drawn)}/6"
                )
            )
            await asyncio.sleep(1.8)

        # ── Finalni rezultat ─────────────────────────────────────────────────
        drawn_set = set(drawn)
        drawn_final = "   ".join(f"**{n}**" for n in sorted(drawn))

        scores = {}
        for uid, nums in view.tickets.items():
            hits = len(set(nums) & drawn_set)
            scores[uid] = hits
            await add_played(uid)

        top_score = max(scores.values())
        winners = [uid for uid, s in scores.items() if s == top_score]

        if top_score == 0:
            result = embed(
                "LUTRIJA — Nema Pobjednika",
                f"Niko nije imao pogodaka. Pot propada.",
                discord.Color.red(),
                fields=[("Izvuceni brojevi", drawn_final, False)]
            )
        else:
            share = view.pot // len(winners)
            bonus_items = []
            for uid in winners:
                await add_coins(uid, share)
                await add_win(uid, 50)
                if top_score >= 5:
                    rtype, item = rand_prize("rare")
                    await add_item(uid, rtype, item)
                    bonus_items.append(item)
            mention = "  ".join(f"<@{uid}>" for uid in winners)
            fields = [
                ("Izvuceni brojevi", drawn_final, False),
                ("Pobjednici", mention, False),
                ("Pogodaka", f"**{top_score}/6**", True),
                ("Dobitak po osobi", f"**{share}** {COIN}", True),
            ]
            if bonus_items:
                fields.append(("Bonus nagrada", bonus_items[0], False))
            result = embed("LUTRIJA — Pobjednici!", None, discord.Color.green(), fields=fields)

        await draw_msg.edit(embed=result)
        await asyncio.sleep(10)


# ─────────────────────────────────────────────────────────────────────────────
# GAME 9 — EMOJI GUESS
# ─────────────────────────────────────────────────────────────────────────────
EMOJI_QUESTIONS = [
    {"emojis": "👠⏰🎃",  "answers": ["cinderella", "pepeljuga"], "hint": "Disney bajka"},
    {"emojis": "🌊🐠🔍", "answers": ["nemo", "finding nemo"],    "hint": "Animirani film"},
    {"emojis": "🦁👑🌍", "answers": ["kralj lavova", "lion king", "simba"], "hint": "Disney film"},
    {"emojis": "❄️👸✨", "answers": ["frozen", "ledeno kraljevstvo", "elsa"], "hint": "Animirani film"},
    {"emojis": "🕷️👦🏙️","answers": ["spiderman", "spider-man"], "hint": "Superjunak"},
    {"emojis": "🦇🤵🌃", "answers": ["batman", "betmen"],        "hint": "Gotham City"},
    {"emojis": "⚡🧙📚", "answers": ["harry potter", "hari poter"], "hint": "Carobnjak"},
    {"emojis": "💍🧝🌋", "answers": ["gospodar prstenova", "lord of the rings", "lotr"], "hint": "Fantasy epic"},
    {"emojis": "🚀👨‍🚀♾️","answers": ["interstellar"],            "hint": "Nolan film"},
    {"emojis": "🃏🤡🃏", "answers": ["joker", "dzoker"],          "hint": "DC vilain"},
    {"emojis": "🐉🔥⚔️", "answers": ["igra prijestolja", "game of thrones", "got"], "hint": "HBO serija"},
    {"emojis": "💊🔵🔴", "answers": ["matrix", "matriks"],        "hint": "Sci-fi klasik"},
    {"emojis": "🧟‍♂️🔫🌍","answers": ["walking dead", "hodajuci mrtvi"], "hint": "AMC serija"},
    {"emojis": "👨‍🍳💀🧪","answers": ["breaking bad"],             "hint": "Hemicar"},
    {"emojis": "🐢🍕🥷", "answers": ["ninja kornjace", "tmnt"],   "hint": "Akcioni crtac"},
    {"emojis": "🔫🕶️📱", "answers": ["john wick", "dzon vik"],   "hint": "Keanu Reeves"},
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

        msg = await channel.send(
            embed=embed(
                "EMOJI GUESS — Pogodi!",
                f"**{q['emojis']}**\n\nNapisi u chat sta ovi emoji predstavljaju!",
                self.COLOR,
                fields=[
                    ("Hint", q['hint'], True),
                    ("Nagrada", f"**{EMOJI_REWARD}** {COIN}", True),
                    ("Vrijeme", f"**{EMOJI_TIME}s**", True),
                ],
                footer="Emoji Guess"
            )
        )

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
            result = embed(
                "Tacan Odgovor!",
                f"<@{winner_uid}> je pogodio!",
                discord.Color.green(),
                fields=[
                    ("Odgovor", f'"{winner_msg.content}"', False),
                    ("Tacan odgovor", q['answers'][0].title(), True),
                    ("Dobitak", f"**{EMOJI_REWARD}** {COIN}", True),
                ]
            )
        else:
            result = embed(
                "Vrijeme Isteklo",
                f"Niko nije pogodio.",
                discord.Color.red(),
                fields=[("Tacan odgovor", q['answers'][0].title(), True)]
            )
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

    @discord.ui.button(label="Ulozi u Jackpot — 120 coina", style=discord.ButtonStyle.danger)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("Jackpot zatvoren!", ephemeral=True)
        uid = interaction.user.id
        if uid in self.entrants:
            return await interaction.response.send_message(
                f"Vec si u igri! Pot: **{self.pot}** {COIN}", ephemeral=True
            )
        await ensure_user(uid, interaction.user.display_name)
        ok = await deduct_coins(uid, JACKPOT_COST)
        if not ok:
            return await interaction.response.send_message(f"Trebas {JACKPOT_COST} {COIN}!", ephemeral=True)
        self.entrants.append(uid)
        self.pot += JACKPOT_COST
        await interaction.response.send_message(
            f"U igri si! Igraci: **{len(self.entrants)}**  |  Pot: **{self.pot}** {COIN}", ephemeral=True
        )


class JackpotGame:
    NAME = "Jackpot Event"
    COLOR = discord.Color.from_rgb(200, 30, 30)

    async def run(self, channel: discord.TextChannel):
        view = JackpotView()
        msg = await channel.send(
            embed=embed(
                "JACKPOT EVENT",
                f"Svi ulaze, **jedan** pobijedi sve!\n\n"
                f"Ulog: **{JACKPOT_COST}** {COIN} po igracu\n"
                f"Pobjednik uzima cijeli pot + Legendarnu nagradu!\n\n"
                f"Prijave traju **{TICK}s** — maks 20 igraca.",
                self.COLOR,
                footer=f"Jackpot Event  •  Ulog: {JACKPOT_COST} coina"
            ),
            view=view
        )
        await asyncio.sleep(TICK)
        view.closed = True
        view.stop()

        if len(view.entrants) < 2:
            await msg.edit(
                embed=embed("JACKPOT EVENT", "Premalo igraca! Ulozi vraceni.", discord.Color.red()),
                view=None
            )
            for uid in view.entrants:
                await add_coins(uid, JACKPOT_COST)
            return

        # Dramaticni odbrojaj
        for countdown in [5, 4, 3, 2, 1]:
            await msg.edit(
                embed=embed(
                    f"JACKPOT — Izvlacenje za {countdown}...",
                    None,
                    self.COLOR,
                    fields=[
                        ("Igraci", str(len(view.entrants)), True),
                        ("Pot", f"**{view.pot}** {COIN}", True),
                    ]
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
            embed=embed(
                "JACKPOT — Pobjednik!",
                f"<@{winner}> uzima sve!",
                discord.Color.gold(),
                fields=[
                    ("Pot", f"**{view.pot}** {COIN}", True),
                    ("Legendarni item", item, True),
                ]
            )
        )
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
