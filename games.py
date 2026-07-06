"""
10 auto-posting igara — moderni embedi, thumbnail podrška,
pravi tekstovi Jala Brat & Buba Corelli, kompaktni stil.
"""

import discord
import asyncio
import random
from datetime import datetime
from database import (
    ensure_user, get_coins, add_coins, deduct_coins,
    add_win, add_played, add_item, check_achievements
)

COIN = "🪙"
TICK = 60  # sekundi za prijave

# ── Thumbnail URLs po igri (popuni kad posaljes slike) ────────────────────────
THUMBS: dict[str, str] = {
    "EmojiGame":   "",
    "QuizGame":    "",
    "SlotGame":    "",
    "WheelGame":   "",
    "RouletteGame":"",
    "ScratchGame": "",
    "LotteryGame": "",
    "BingoGame":   "",
    "MinesGame":   "",
    "JackpotGame": "",
}

# ── Rank sistem ───────────────────────────────────────────────────────────────
def get_rank(level: int) -> str:
    if level >= 50: return "🚀 Legenda"
    if level >= 25: return "🔮 Master"
    if level >= 15: return "👑 Elite"
    if level >= 10: return "🌟 Pro"
    if level >=  5: return "🎮 Veteran"
    return "🥉 Početnik"

# ── Prize helpers ─────────────────────────────────────────────────────────────
DECORATIONS = ["Zlatna Zvijezda","Vatreni Efekt","Ledeni Efekt","Rainbow Aura",
                "Kraljevska Kruna","Munja Efekt","Butterfly Frame","Stardust Efekt"]
AVATARS      = ["Zmaj Avatar","Lav Avatar","Cyber Avatar","Carobnjak Avatar",
                "Lisica Avatar","Vuk Avatar","Mistik Avatar","Okean Avatar"]
NITRO        = ["Nitro Classic (1 mj.)","Nitro Boost (1 mj.)","Nitro Gift Link"]

def rand_prize(tier="common"):
    if tier == "legendary": return "nitro",       random.choice(NITRO)
    if tier == "rare":
        return ("avatar","decoration")[random.randint(0,1)], \
               random.choice(AVATARS if random.random()<.5 else DECORATIONS)
    return "decoration", random.choice(DECORATIONS)

# ── Embed helper ──────────────────────────────────────────────────────────────
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

def game_emb(game_cls, title, desc=None, color=discord.Color.gold(),
             fields=None, footer=None) -> discord.Embed:
    """Embed s automatskim thumbnailom igre."""
    thumb = THUMBS.get(game_cls.__name__, "")
    return emb(title, desc, color, fields, footer, thumb or None)

async def post_achievements(channel, uid: int):
    """Provjeri i objavi nove achievemente."""
    new_ach = await check_achievements(uid)
    for ach in new_ach:
        await channel.send(embed=emb(
            "Achievement Otključan!", f"<@{uid}> — **{ach}**",
            discord.Color.from_rgb(255, 215, 0)))

# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 1 — BINGO
# ═══════════════════════════════════════════════════════════════════════════════
class BingoView(discord.ui.View):
    COST = 80
    def __init__(self):
        super().__init__(timeout=TICK)
        self.players: dict[int, list[int]] = {}
        self.pot = 0
        self.closed = False

    @discord.ui.button(label="🎟  Kupi Listić  —  80 🪙", style=discord.ButtonStyle.success)
    async def buy(self, i: discord.Interaction, b):
        if self.closed:
            return await i.response.send_message("Prijave zatvorene.", ephemeral=True)
        uid = i.user.id
        if uid in self.players:
            return await i.response.send_message("Već imaš listić!", ephemeral=True)
        await ensure_user(uid, i.user.display_name)
        if not await deduct_coins(uid, self.COST):
            c = await get_coins(uid)
            return await i.response.send_message(f"Nemaš dovoljno. Imaš **{c}** {COIN}", ephemeral=True)
        card = sorted(random.sample(range(1, 76), 15))
        self.players[uid] = card
        self.pot += self.COST
        nums = "  ".join(f"`{n}`" for n in card)
        await i.response.send_message(embed=emb(
            "Tvoj Bingo Listić", nums, discord.Color.green(),
            footer=f"Pot: {self.pot} coina"), ephemeral=True)

class BingoGame:
    NAME  = "Bingo"
    COLOR = discord.Color.blue()

    async def run(self, channel):
        view = BingoView()
        msg = await channel.send(embed=game_emb(
            BingoGame, "🔵  BINGO",
            "Kupi listić i budi **prvi** koji skupi svih **15** izvučenih brojeva!",
            self.COLOR,
            fields=[
                ("Cijena",    f"**{BingoView.COST}** {COIN}", True),
                ("Prijave",   f"**{TICK}s**", True),
                ("Potrebno",  "Min. 2 igrača", True),
            ]), view=view)
        await asyncio.sleep(TICK)
        view.closed = True; view.stop()

        if len(view.players) < 2:
            await msg.edit(embed=game_emb(BingoGame, "BINGO — Otkazano",
                "Premalo igrača. Ulog vraćen.", discord.Color.red()), view=None)
            for uid in view.players: await add_coins(uid, BingoView.COST)
            return

        pool = list(range(1, 76)); random.shuffle(pool)
        marked = {uid: set() for uid in view.players}
        called, winner_uid = [], None

        dm = await channel.send(embed=game_emb(BingoGame,
            "BINGO — Izvlačenje", None, self.COLOR,
            fields=[("Igrači", str(len(view.players)), True),
                    ("Pot", f"**{view.pot}** {COIN}", True)]))

        for num in pool:
            called.append(num)
            for uid, card in view.players.items():
                if num in card: marked[uid].add(num)
                if len(marked[uid]) >= len(card): winner_uid = uid; break

            last = "  ".join(f"**{n}**" if n == num else str(n) for n in called[-8:])
            prog = "\n".join(f"<@{uid}>  {len(marked[uid])}/15" for uid in view.players)
            await dm.edit(embed=game_emb(BingoGame, f"BINGO  —  Broj **{num}**",
                prog, self.COLOR, fields=[("Zadnjih 8", last, False)],
                footer=f"Izvučeno {len(called)}/75"))
            if winner_uid: break
            await asyncio.sleep(4)

        if winner_uid:
            await add_coins(winner_uid, view.pot); await add_win(winner_uid, 80)
            _, item = rand_prize("rare"); await add_item(winner_uid, "decoration", item)
            result = game_emb(BingoGame, "🎉  BINGO — Pobjednik!",
                f"<@{winner_uid}> skupio sve brojeve!", discord.Color.green(),
                fields=[("Dobitak", f"**{view.pot}** {COIN}", True),
                        ("Bonus", item, True)])
            await post_achievements(channel, winner_uid)
        else:
            result = game_emb(BingoGame, "BINGO", "Niko nije pobijedio.", discord.Color.greyple())

        for uid in view.players: await add_played(uid)
        await dm.edit(embed=result)
        await asyncio.sleep(10)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 2 — KOLO SREĆE
# ═══════════════════════════════════════════════════════════════════════════════
WHEEL_SEGMENTS = [
    ("💥 BANKROT",    0,    "bankrot"),
    ("💰 100",        100,  "coins"),
    ("💰 250",        250,  "coins"),
    ("💰 500",        500,  "coins"),
    ("💰 1000",      1000,  "coins"),
    ("💰 50",          50,  "coins"),
    ("🎨 Dekoracija",   0,  "decoration"),
    ("👤 Avatar",       0,  "avatar"),
    ("💰 2000",      2000,  "coins"),
    ("✨ NITRO",        0,  "nitro"),
    ("💰 750",        750,  "coins"),
    ("❌ Ništa",        0,  "nothing"),
]
WHEEL_W = [2, 10, 9, 6, 3, 12, 5, 4, 1, 1, 5, 8]
SPIN_COST = 60

def wheel_text(hi: int) -> str:
    lines = []
    for i, (label, _, _) in enumerate(WHEEL_SEGMENTS):
        if i == hi: lines.append(f"**▶  {label}  ◀**")
        else:       lines.append(f"·  {label}")
    return "\n".join(lines)

class WheelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.spinners: list[int] = []
        self.closed = False

    @discord.ui.button(label="🎡  Zavrti  —  60 🪙", style=discord.ButtonStyle.blurple)
    async def spin(self, i: discord.Interaction, b):
        if self.closed:
            return await i.response.send_message("Zatvoreno.", ephemeral=True)
        uid = i.user.id
        if uid in self.spinners:
            return await i.response.send_message("Već si prijavljen!", ephemeral=True)
        await ensure_user(uid, i.user.display_name)
        if not await deduct_coins(uid, SPIN_COST):
            c = await get_coins(uid)
            return await i.response.send_message(f"Trebaš **{SPIN_COST}** {COIN}. Imaš **{c}**", ephemeral=True)
        self.spinners.append(uid)
        await i.response.send_message("Prijavljen! Čekaj spin...", ephemeral=True)

class WheelGame:
    NAME  = "Kolo Sreće"
    COLOR = discord.Color.purple()

    async def run(self, channel):
        view = WheelView()
        nagrade = "\n".join(f"{'🔸' if i%2==0 else '▫️'} {l}" for i, (l,_,_) in enumerate(WHEEL_SEGMENTS))
        msg = await channel.send(embed=game_emb(
            WheelGame, "🎡  KOLO SREĆE",
            "Pritisni dugme i plati ulaz — kolo se vrti, nagradu određuje sudbina!",
            self.COLOR,
            fields=[("Ulaz", f"**{SPIN_COST}** {COIN}", True),
                    ("Trajanje", f"**{TICK}s**", True),
                    ("Moguće nagrade", nagrade, False)]), view=view)
        await asyncio.sleep(TICK)
        view.closed = True; view.stop()

        if not view.spinners:
            await msg.edit(embed=game_emb(WheelGame, "KOLO SREĆE",
                "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return

        for uid in view.spinners:
            sm = await channel.send(embed=game_emb(WheelGame,
                "Kolo se vrti...", wheel_text(0), self.COLOR))
            prev = -1
            for _ in range(12):
                pos = random.randint(0, len(WHEEL_SEGMENTS)-1)
                while pos == prev: pos = random.randint(0, len(WHEEL_SEGMENTS)-1)
                prev = pos
                await sm.edit(embed=game_emb(WheelGame,
                    "Kolo se vrti...", wheel_text(pos), self.COLOR))
                await asyncio.sleep(0.45)

            seg = random.choices(WHEEL_SEGMENTS, weights=WHEEL_W)[0]
            label, amount, stype = seg
            fpos = WHEEL_SEGMENTS.index(seg)
            await sm.edit(embed=game_emb(WheelGame, "🛑  Stalo!", wheel_text(fpos), self.COLOR))
            await asyncio.sleep(1.2)

            if stype == "bankrot":
                lost = min(await get_coins(uid), random.randint(50, 300))
                await add_coins(uid, -lost)
                em = game_emb(WheelGame, "💥  BANKROT!",
                    f"<@{uid}> gubi **{lost}** {COIN}!", discord.Color.dark_red())
            elif stype == "coins":
                await add_coins(uid, amount)
                em = game_emb(WheelGame, f"🎉  {label}!", None, discord.Color.green(),
                    fields=[("Igrac", f"<@{uid}>", True),
                            ("Nagrada", f"**{amount}** {COIN}", True)])
            elif stype in ("decoration", "avatar", "nitro"):
                tier = "legendary" if stype=="nitro" else "rare" if stype=="avatar" else "common"
                rtype, item = rand_prize(tier)
                await add_item(uid, rtype, item)
                em = game_emb(WheelGame, "🎁  Nagrađen!", None, discord.Color.blurple(),
                    fields=[("Igrac", f"<@{uid}>", True), ("Item", item, True)])
            else:
                em = game_emb(WheelGame, "❌  Ništa ovaj put",
                    f"<@{uid}> nije imao sreće.", discord.Color.greyple())
            await add_played(uid)
            await post_achievements(channel, uid)
            await sm.edit(embed=em)
            await asyncio.sleep(3)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 3 — SLOT MACHINE
# ═══════════════════════════════════════════════════════════════════════════════
REELS = ["Cherry","Lemon","Grape","Star","Diamond","Bell","Seven","Wild","Crown","Clover"]
EMO   = {"Cherry":"🍒","Lemon":"🍋","Grape":"🍇","Star":"⭐","Diamond":"💎",
         "Bell":"🔔","Seven":"7️⃣","Wild":"🃏","Crown":"👑","Clover":"🍀"}
JPOTS = {
    ("Seven",  "Seven",  "Seven"):   (20,"legendary"),
    ("Diamond","Diamond","Diamond"): (15,"rare"),
    ("Crown",  "Crown",  "Crown"):   (10,"rare"),
    ("Star",   "Star",   "Star"):    ( 8,"common"),
    ("Bell",   "Bell",   "Bell"):    ( 5,"common"),
    ("Grape",  "Grape",  "Grape"):   ( 4,"common"),
    ("Clover", "Clover", "Clover"):  ( 3,"common"),
    ("Lemon",  "Lemon",  "Lemon"):   ( 3,"common"),
    ("Cherry", "Cherry", "Cherry"):  ( 2,"common"),
}
SLOT_COST = 50

def slot_row(r): return "  |  ".join(EMO.get(x,"❓") for x in r)

class SlotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.players: set[int] = set()
        self.closed = False

    @discord.ui.button(label="🎰  Zaigraj  —  50 🪙", style=discord.ButtonStyle.success)
    async def play(self, i: discord.Interaction, b):
        if self.closed:
            return await i.response.send_message("Slot zatvoren.", ephemeral=True)
        uid = i.user.id
        if uid in self.players:
            return await i.response.send_message("Već si prijavljen!", ephemeral=True)
        await ensure_user(uid, i.user.display_name)
        if not await deduct_coins(uid, SLOT_COST):
            c = await get_coins(uid)
            return await i.response.send_message(f"Trebaš **{SLOT_COST}** {COIN}. Imaš **{c}**", ephemeral=True)
        self.players.add(uid)
        await i.response.send_message("Prijavljen! Čekaj vrtnju...", ephemeral=True)

class SlotGame:
    NAME  = "Slot Machine"
    COLOR = discord.Color.orange()

    async def run(self, channel):
        view = SlotView()
        msg = await channel.send(embed=game_emb(
            SlotGame, "🎰  SLOT MACHINE",
            "Klikni i ulozi. Tri ista = jackpot!",
            self.COLOR,
            fields=[
                ("Ulaz", f"**{SLOT_COST}** {COIN}", True),
                ("Trajanje", f"**{TICK}s**", True),
                ("Top jackpoti",
                 "7️⃣ 7️⃣ 7️⃣  →  x20 + Nitro\n"
                 "💎 💎 💎  →  x15 + Item\n"
                 "👑 👑 👑  →  x10\n"
                 "Dva ista  →  x1.5", False),
            ]), view=view)
        await asyncio.sleep(TICK)
        view.closed = True; view.stop()

        if not view.players:
            await msg.edit(embed=game_emb(SlotGame, "SLOT MACHINE",
                "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return
        await msg.edit(view=None)

        for uid in view.players:
            sm = await channel.send(embed=game_emb(SlotGame,
                "Vrtim reele...", "🎰  · · ·", self.COLOR))
            for _ in range(7):
                r = [random.choice(REELS) for _ in range(3)]
                await sm.edit(embed=game_emb(SlotGame, "Vrtim...", slot_row(r), self.COLOR))
                await asyncio.sleep(0.4)

            final = tuple(random.choice(REELS) for _ in range(3))
            display = slot_row(final)
            jp = JPOTS.get(final)

            if jp:
                mult, tier = jp
                win = SLOT_COST * mult
                await add_coins(uid, win); await add_win(uid, 70)
                rtype, item = rand_prize(tier); await add_item(uid, rtype, item)
                em = game_emb(SlotGame, "🎉  JACKPOT!", display, discord.Color.gold(),
                    fields=[("Igrac", f"<@{uid}>", True),
                            ("x{0}".format(mult), f"**{win}** {COIN}", True),
                            ("Bonus item", item, False)])
                await post_achievements(channel, uid)
            elif len(set(final)) < 3:
                win = int(SLOT_COST * 1.5)
                await add_coins(uid, win); await add_played(uid)
                em = game_emb(SlotGame, "⭐  Dva ista!", display, discord.Color.yellow(),
                    fields=[("Igrac", f"<@{uid}>", True), ("Dobitak", f"**{win}** {COIN}", True)])
            else:
                await add_played(uid)
                em = game_emb(SlotGame, "❌  Nema podudaranja", display, discord.Color.red(),
                    fields=[("Igrac", f"<@{uid}>", True), ("Gubitak", f"**{SLOT_COST}** {COIN}", True)])

            await sm.edit(embed=em)
            await asyncio.sleep(4)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 4 — NASTAVI PJESMU
# ═══════════════════════════════════════════════════════════════════════════════
SONGS = [
    {"artist":"Jala Brat & Buba Corelli","title":"Pilula",
     "lyric":"Sipam ti ___ u čašu vina, volim te ko što voli se Bosna...",
     "answer":["pilula","pilulu"],"hint":"Stavlja u piće"},
    {"artist":"Jala Brat & Buba Corelli","title":"Crni Mercedes",
     "lyric":"Doći ću po tebe u crnom ___, puna kesa, sjedi pored mene...",
     "answer":["mercedes","crni mercedes"],"hint":"Luksuzni auto"},
    {"artist":"Jala Brat","title":"Za Tebe",
     "lyric":"Sve bih dao ___ moja, samo da si sretna, samo da se smiješ...",
     "answer":["za tebe","tebe"],"hint":"Posvećeno dragoj osobi"},
    {"artist":"Buba Corelli","title":"Ferrari",
     "lyric":"Vozim ___, puna kesa, kažu da sam lud, al' to je samo moj stil...",
     "answer":["ferrari","ferari"],"hint":"Talijanski sportski auto"},
    {"artist":"Jala Brat & Buba Corelli","title":"Kuna Pela",
     "lyric":"___ pela, pela, pela — leti kao pčela, zarađuje kunu...",
     "answer":["kuna pela","kuna","pela"],"hint":"Radi marljivo poput pčele"},
    {"artist":"Jala Brat","title":"Golubica",
     "lyric":"Moja ___ bijela, leti visoko iznad oblaka, samo ti me čekaš...",
     "answer":["golubica"],"hint":"Bijela ptica mira"},
    {"artist":"Buba Corelli","title":"Paranoja",
     "lyric":"Svuda vidim ___, u glavi mi se vrti, ne mogu spavati...",
     "answer":["paranoja"],"hint":"Stalni strah i sumnja"},
    {"artist":"Jala Brat","title":"Cigare",
     "lyric":"Parim ___, gledam u nebo, misli idu daleko, ne znam kuda...",
     "answer":["cigare","cigaru"],"hint":"Puši ih"},
    {"artist":"Jala Brat & Buba Corelli","title":"Trik",
     "lyric":"To je samo ___, ne uzimaj srcu blizu, znaš pravila igre...",
     "answer":["trik"],"hint":"Prevara u igri"},
    {"artist":"Buba Corelli","title":"Sjena",
     "lyric":"Pratim te ko ___, kud god kreneš tu sam ja, ne mogu bez tebe...",
     "answer":["sjena"],"hint":"Prati te posvuda"},
    {"artist":"Jala Brat","title":"Pas",
     "lyric":"Vjeran ti sam ko ___, nikad neću izdati, uvijek pored tebe...",
     "answer":["pas"],"hint":"Najvjernija životinja"},
    {"artist":"Jala Brat & Buba Corelli","title":"Bez Adrese",
     "lyric":"Živim ___, nema gdje da me nađeš, bježim od problema...",
     "answer":["bez adrese"],"hint":"Nema doma ni adrese"},
    {"artist":"Jala Brat","title":"Dijamant",
     "lyric":"Ti si moj ___, rijetka, skupa, nema ti zamjene ni za što...",
     "answer":["dijamant"],"hint":"Dragulj"},
    {"artist":"Buba Corelli","title":"Novac",
     "lyric":"___ i slava, ali sreće nema — sve je tu a praznina ostaje...",
     "answer":["novac"],"hint":"Ima ga ali nije sretan"},
    {"artist":"Jala Brat","title":"Šampanjac",
     "lyric":"Otvori ___, slavimo večeras, sve je moguće kad smo zajedno...",
     "answer":["sampanjac","šampanjac","champagne"],"hint":"Piće za slavlje"},
    {"artist":"Jala Brat & Buba Corelli","title":"Litar Krvi",
     "lyric":"Dal' bi dao ___ za mene, ili bi me ostavio ko i svi drugi...",
     "answer":["litar krvi","krvi","litar"],"hint":"Pitanje odanosti"},
    {"artist":"Buba Corelli","title":"Kiša",
     "lyric":"Pada ___, ne mogu se skloniti, misli na tebe nikako da izbjegnem...",
     "answer":["kiša","kisa"],"hint":"Pada s neba"},
    {"artist":"Jala Brat","title":"Cvijet",
     "lyric":"Ti si moj ___, u svakom godišnjem dobu miriš jednako lijepo...",
     "answer":["cvijet","cvjet","flower"],"hint":"Biljka koja cvjeta"},
]
QUIZ_REWARD = 300
QUIZ_TIME   = 60

class QuizGame:
    NAME  = "Nastavi Pjesmu"
    COLOR = discord.Color.from_rgb(220, 80, 180)

    async def run(self, channel):
        song = random.choice(SONGS)
        msg = await channel.send(embed=game_emb(
            QuizGame, "🎵  NASTAVI PJESMU",
            f"*\"{song['lyric']}\"*",
            self.COLOR,
            fields=[
                ("Izvođač", song["artist"], True),
                ("Nagrada", f"**{QUIZ_REWARD}** {COIN}", True),
                ("Hint", song["hint"], True),
                ("Uputa", f"Napiši naziv pjesme u chat!  •  **{QUIZ_TIME}s**", False),
            ]))

        winner_uid = None
        def check(m): return (m.channel.id == channel.id and not m.author.bot
                               and any(a in m.content.lower() for a in song["answer"]))
        try:
            am = await channel.bot.wait_for("message", timeout=QUIZ_TIME, check=check)
            winner_uid = am.author.id
        except asyncio.TimeoutError: pass

        if winner_uid:
            await ensure_user(winner_uid, am.author.display_name)
            await add_coins(winner_uid, QUIZ_REWARD); await add_win(winner_uid, 40)
            result = game_emb(QuizGame, "✅  Tačan Odgovor!", None, discord.Color.green(),
                fields=[("Pobjednik", f"<@{winner_uid}>", True),
                        ("Dobitak", f"**{QUIZ_REWARD}** {COIN}", True),
                        ("Pjesma", song["title"], True),
                        ("Izvođač", song["artist"], True)])
            await post_achievements(channel, winner_uid)
        else:
            result = game_emb(QuizGame, "⏰  Vrijeme Isteklo",
                "Niko nije pogodio.", discord.Color.red(),
                fields=[("Tačan odgovor", song["title"], True),
                        ("Izvođač", song["artist"], True)])
        await msg.edit(embed=result)
        await asyncio.sleep(8)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 5 — RULET
# ═══════════════════════════════════════════════════════════════════════════════
RED_NUMS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
WHEEL_ORDER = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,
               30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
ROUL_COST = 70

def col_label(n):
    if n == 0: return "🟢 Nula"
    return "🔴 Crvena" if n in RED_NUMS else "⚫ Crna"

def wheel_embed(ball_pos, title, color):
    sz = len(WHEEL_ORDER)
    seg = []
    for i in range(7):
        idx = (ball_pos - 3 + i) % sz
        n = WHEEL_ORDER[idx]
        c = "🟢" if n==0 else ("🔴" if n in RED_NUMS else "⚫")
        seg.append(f"**[ {c} {n} ]**" if i==3 else f"{c} {n}")
    e = discord.Embed(title=title, description="  ".join(seg), color=color)
    e.timestamp = datetime.utcnow()
    thumb = THUMBS.get("RouletteGame","")
    if thumb: e.set_thumbnail(url=thumb)
    return e

class RouletteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.bets: dict[int, tuple[str,int]] = {}
        self.closed = False

    async def _bet(self, i: discord.Interaction, choice: str):
        if self.closed:
            return await i.response.send_message("Zatvoreno.", ephemeral=True)
        uid = i.user.id
        if uid in self.bets:
            return await i.response.send_message(f"Već si oklado na **{self.bets[uid][0]}**!", ephemeral=True)
        await ensure_user(uid, i.user.display_name)
        if not await deduct_coins(uid, ROUL_COST):
            c = await get_coins(uid)
            return await i.response.send_message(f"Trebaš **{ROUL_COST}** {COIN}. Imaš **{c}**", ephemeral=True)
        self.bets[uid] = (choice, ROUL_COST)
        await i.response.send_message(f"Oklado si **{ROUL_COST}** {COIN} na **{choice}**!", ephemeral=True)

    @discord.ui.button(label="🔴 Crvena (x2)", style=discord.ButtonStyle.danger, row=0)
    async def b_red(self,i,b): await self._bet(i,"crvena")
    @discord.ui.button(label="⚫ Crna (x2)", style=discord.ButtonStyle.secondary, row=0)
    async def b_blk(self,i,b): await self._bet(i,"crna")
    @discord.ui.button(label="🟢 Nula (x14)", style=discord.ButtonStyle.success, row=0)
    async def b_zer(self,i,b): await self._bet(i,"nula")
    @discord.ui.button(label="Parno (x2)", style=discord.ButtonStyle.primary, row=1)
    async def b_evn(self,i,b): await self._bet(i,"parno")
    @discord.ui.button(label="Neparno (x2)", style=discord.ButtonStyle.primary, row=1)
    async def b_odd(self,i,b): await self._bet(i,"neparno")
    @discord.ui.button(label="1–18 (x2)", style=discord.ButtonStyle.secondary, row=2)
    async def b_low(self,i,b): await self._bet(i,"nisko")
    @discord.ui.button(label="19–36 (x2)", style=discord.ButtonStyle.secondary, row=2)
    async def b_hig(self,i,b): await self._bet(i,"visoko")

class RouletteGame:
    NAME  = "Rulet"
    COLOR = discord.Color.from_rgb(20, 140, 40)

    async def run(self, channel):
        view = RouletteView()
        msg = await channel.send(embed=game_emb(
            RouletteGame, "🎲  RULET",
            "Odaberi okladu i klikni dugme!",
            self.COLOR,
            fields=[
                ("Ulog", f"**{ROUL_COST}** {COIN}", True),
                ("Prijave", f"**{TICK}s**", True),
                ("Isplate",
                 "🔴 Crvena → x2\n⚫ Crna → x2\n"
                 "Parno → x2\nNeparno → x2\n"
                 "1–18 → x2\n19–36 → x2\n🟢 Nula → x14", False),
            ]), view=view)
        await asyncio.sleep(TICK)
        view.closed = True; view.stop()

        if not view.bets:
            await msg.edit(embed=game_emb(RouletteGame, "RULET",
                "Niko nije oklado.", discord.Color.greyple()), view=None)
            return

        wm = await channel.send(embed=wheel_embed(0, "Rulet — kugla se kotrlja...", self.COLOR))
        pos = 0
        steps = random.randint(24, 44)
        for s in range(steps):
            pos = (pos + 1) % len(WHEEL_ORDER)
            delay = 0.09 + (s / steps) * 0.6
            await wm.edit(embed=wheel_embed(pos, "Rulet — kugla se kotrlja...", self.COLOR))
            await asyncio.sleep(delay)

        num = WHEEL_ORDER[pos]
        cl  = col_label(num)
        await wm.edit(embed=wheel_embed(pos, f"🛑  Pao broj {num}  •  {cl}", self.COLOR))
        await asyncio.sleep(2)

        winners, losers = [], []
        for uid, (choice, bet) in view.bets.items():
            won, mult = False, 0
            if choice=="nula"    and num==0:                             won,mult=True,14
            elif choice=="crvena" and num in RED_NUMS:                   won,mult=True,2
            elif choice=="crna"   and num not in RED_NUMS and num!=0:    won,mult=True,2
            elif choice=="parno"  and num!=0 and num%2==0:              won,mult=True,2
            elif choice=="neparno" and num%2==1:                         won,mult=True,2
            elif choice=="nisko"  and 1<=num<=18:                        won,mult=True,2
            elif choice=="visoko" and 19<=num<=36:                       won,mult=True,2
            await add_played(uid)
            if won:
                w = bet*mult; await add_coins(uid,w); await add_win(uid,30)
                winners.append(f"<@{uid}> ({choice}) → +**{w}** {COIN}")
                await post_achievements(channel, uid)
            else:
                losers.append(f"<@{uid}> ({choice}) → ❌")

        await channel.send(embed=game_emb(
            RouletteGame, f"Rulet — {num}  {cl}", None,
            discord.Color.green() if winners else discord.Color.red(),
            fields=[
                ("Pobjednici", "\n".join(winners) or "—", False),
                ("Gubitnici",  "\n".join(losers)  or "—", False),
            ]))
        await asyncio.sleep(8)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 6 — GREBALICA
# ═══════════════════════════════════════════════════════════════════════════════
SCRATCH_PRIZES = [(0,40),(30,20),(60,15),(100,10),(200,7),(500,4),(1000,2),(2000,1),(5000,0.5)]
SCRATCH_SYMS   = {0:"✗ · ✗ · ✗",30:"🍒 · 🍒 · ✗",60:"🍒 · 🍒 · 🍒",100:"⭐ · ⭐ · 🍒",
                  200:"⭐ · ⭐ · ⭐",500:"💎 · 💎 · ⭐",1000:"💎 · 💎 · 💎",
                  2000:"👑 · 👑 · 💎",5000:"7️⃣ · 7️⃣ · 7️⃣"}

class ScratchCard(discord.ui.View):
    def __init__(self, owner_id, prize, item):
        super().__init__(timeout=30)
        self.owner_id = owner_id; self.prize = prize; self.item = item
        self.done = False

    @discord.ui.button(label="🎫  Ogrebi!", style=discord.ButtonStyle.success)
    async def scratch(self, i: discord.Interaction, b):
        if i.user.id != self.owner_id:
            return await i.response.send_message("Nije tvoja grebalica!", ephemeral=True)
        if self.done: return
        self.done = True; b.disabled = True; self.stop()
        if self.prize > 0: await add_coins(self.owner_id, self.prize)
        if self.item: await add_item(self.owner_id, self.item[0], self.item[1])
        syms = SCRATCH_SYMS.get(self.prize,"? · ? · ?")
        fields = [("Kombinacija", syms, False), ("Dobitak", f"**{self.prize}** {COIN}", True)]
        if self.item: fields.append(("Bonus", self.item[1], True))
        await i.response.edit_message(
            embed=emb("🎉  Ogrebana!", None,
                discord.Color.green() if self.prize>0 else discord.Color.greyple(),
                fields=fields, thumbnail=THUMBS.get("ScratchGame") or None),
            view=self)

class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.buyers: set[int] = set(); self.closed = False

    @discord.ui.button(label="🎫  Kupi Grebalicu  —  40 🪙", style=discord.ButtonStyle.success)
    async def buy(self, i: discord.Interaction, b):
        if self.closed:
            return await i.response.send_message("Rasprodano!", ephemeral=True)
        uid = i.user.id
        if uid in self.buyers:
            return await i.response.send_message("Već imaš grebalicu!", ephemeral=True)
        await ensure_user(uid, i.user.display_name)
        if not await deduct_coins(uid, 40):
            return await i.response.send_message("Trebaš **40** coina!", ephemeral=True)
        self.buyers.add(uid)
        prizes=[p for p,_ in SCRATCH_PRIZES]; weights=[w for _,w in SCRATCH_PRIZES]
        prize = random.choices(prizes, weights=weights)[0]
        item  = rand_prize("legendary") if prize==5000 else (rand_prize("rare") if prize>=1000 else None)
        cv = ScratchCard(uid, prize, item)
        await i.response.send_message(
            embed=emb("🎫  Tvoja Grebalica", "Klikni da ogrebešȘ",
                discord.Color.gold(), thumbnail=THUMBS.get("ScratchGame") or None),
            view=cv, ephemeral=True)
        await add_played(uid)

class ScratchGame:
    NAME  = "Grebalica"
    COLOR = discord.Color.gold()

    async def run(self, channel):
        view = ScratchView()
        msg = await channel.send(embed=game_emb(
            ScratchGame, "🎫  GREBALICE — NA PRODAJI!",
            "Kupi grebalicu i odmah je ogrebi!",
            self.COLOR,
            fields=[
                ("Cijena", "**40** coina", True),
                ("Trajanje", f"**{TICK}s**", True),
                ("Top nagrade",
                 "7️⃣ 7️⃣ 7️⃣  →  5000 coina + Nitro\n"
                 "👑 👑 💎  →  2000 coina + Item\n"
                 "💎 💎 💎  →  1000 coina\n"
                 "⭐ ⭐ ⭐  →  200 coina", False),
            ]), view=view)
        await asyncio.sleep(TICK)
        view.closed = True; view.stop()
        await msg.edit(view=None)
        if view.buyers:
            await channel.send(embed=game_emb(ScratchGame,
                "Grebalice Završene",
                f"Prodano **{len(view.buyers)}** grebalica.", self.COLOR))
        await asyncio.sleep(5)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 7 — LUTRIJA
# ═══════════════════════════════════════════════════════════════════════════════
LOT_COST = 60

class LotteryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.tickets: dict[int,list[int]] = {}; self.pot = 0; self.closed = False

    @discord.ui.button(label="🎟  Kupi Listić  —  60 🪙", style=discord.ButtonStyle.primary)
    async def buy(self, i: discord.Interaction, b):
        if self.closed:
            return await i.response.send_message("Zatvoreno!", ephemeral=True)
        uid = i.user.id
        if uid in self.tickets:
            return await i.response.send_message("Već imaš listić!", ephemeral=True)
        await ensure_user(uid, i.user.display_name)
        if not await deduct_coins(uid, LOT_COST):
            return await i.response.send_message(f"Trebaš {LOT_COST} {COIN}!", ephemeral=True)
        nums = sorted(random.sample(range(1,50), 6)); self.tickets[uid]=nums; self.pot+=LOT_COST
        ns = "  ".join(f"**{n}**" for n in nums)
        await i.response.send_message(
            embed=emb("🎟  Tvoj Listić", ns, discord.Color.blue(),
                footer=f"Pot: {self.pot} coina"), ephemeral=True)

class LotteryGame:
    NAME  = "Lutrija"
    COLOR = discord.Color.from_rgb(255, 165, 0)

    async def run(self, channel):
        view = LotteryView()
        msg = await channel.send(embed=game_emb(
            LotteryGame, "🏆  LUTRIJA",
            "Kupi listić i čekaj izvlačenje! Ko ima više pogodaka pobijedi!",
            self.COLOR,
            fields=[
                ("Cijena", f"**{LOT_COST}** {COIN}", True),
                ("Trajanje", f"**{TICK}s**", True),
                ("Brojevi", "6 random (1–49)", True),
            ]), view=view)
        await asyncio.sleep(TICK)
        view.closed = True; view.stop()

        if not view.tickets:
            await msg.edit(embed=game_emb(LotteryGame, "LUTRIJA",
                "Nema igrača.", discord.Color.greyple()), view=None)
            return
        await msg.edit(view=None)

        pool = list(range(1,50)); random.shuffle(pool)
        drawn = []
        dm = await channel.send(embed=game_emb(LotteryGame,
            "🏆  LUTRIJA — Izvlačenje!", "Bubanj se puni...", self.COLOR))

        for i in range(6):
            for _ in range(5):
                fake = random.randint(1,49)
                parts = ["**{0}**".format(n) for n in drawn] + ["**??**"] + ["—"]*(5-len(drawn))
                await dm.edit(embed=game_emb(LotteryGame,
                    f"Izvlačenje broja {i+1}/6...",
                    "  ".join(parts[:6]), self.COLOR,
                    footer=f"Izvučeno: {i}/6"))
                await asyncio.sleep(0.35)
            drawn.append(pool[i])
            ds = "  ".join(f"**{n}**" for n in drawn)
            await dm.edit(embed=game_emb(LotteryGame,
                f"Broj {i+1}  →  **{pool[i]}**", None, self.COLOR,
                fields=[("Izvučeni", ds, False)], footer=f"Izvučeno: {len(drawn)}/6"))
            await asyncio.sleep(1.5)

        drawn_set = set(drawn)
        for uid in view.tickets: await add_played(uid)
        scores = {uid: len(set(nums) & drawn_set) for uid,nums in view.tickets.items()}
        top = max(scores.values())
        winners = [uid for uid,s in scores.items() if s==top]
        drawn_str = "  ".join(f"**{n}**" for n in sorted(drawn))

        if top == 0:
            await dm.edit(embed=game_emb(LotteryGame, "LUTRIJA — Nema Pobjednika",
                "Niko nije imao pogodaka.", discord.Color.red(),
                fields=[("Izvučeni brojevi", drawn_str, False)]))
        else:
            share = view.pot // len(winners)
            bonus = None
            for uid in winners:
                await add_coins(uid, share); await add_win(uid, 50)
                if top >= 5:
                    rtype,item = rand_prize("rare"); await add_item(uid,rtype,item); bonus=item
                await post_achievements(channel, uid)
            fields = [("Izvučeni", drawn_str, False),
                      ("Pobjednici", "  ".join(f"<@{uid}>" for uid in winners), False),
                      ("Pogodaka", f"**{top}/6**", True),
                      ("Po osobi", f"**{share}** {COIN}", True)]
            if bonus: fields.append(("Bonus item", bonus, False))
            await dm.edit(embed=game_emb(LotteryGame, "🎉  LUTRIJA — Pobjednici!",
                None, discord.Color.green(), fields=fields))
        await asyncio.sleep(10)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 8 — MINES
# ═══════════════════════════════════════════════════════════════════════════════
MINES_COST  = 100
MINES_COUNT = 5

class MinesView(discord.ui.View):
    def __init__(self, mines, pot, pid):
        super().__init__(timeout=120)
        self.mines=mines; self.revealed=set(); self.safe=0
        self.pot=pot; self.player_id=pid; self.active=True
        for i in range(25):
            btn = discord.ui.Button(label=f"{i+1:02d}",
                style=discord.ButtonStyle.secondary, row=i//5, custom_id=str(i))
            btn.callback = self._cb(i)
            self.add_item(btn)
        co = discord.ui.Button(label="💰 Naplata", style=discord.ButtonStyle.success, row=4)
        co.callback = self.cashout; self.add_item(co)

    def _cb(self, pos):
        async def cb(i: discord.Interaction):
            if i.user.id != self.player_id:
                return await i.response.send_message("Nije tvoja igra!", ephemeral=True)
            if not self.active or pos in self.revealed:
                return await i.response.send_message("Nije moguće.", ephemeral=True)
            self.revealed.add(pos)
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id==str(pos):
                    item.label = "💣" if pos in self.mines else "✅"
                    item.style = discord.ButtonStyle.danger if pos in self.mines else discord.ButtonStyle.success
                    item.disabled = True; break
            if pos in self.mines:
                self.active=False; self.stop()
                for x in self.children: x.disabled=True
                await i.response.edit_message(embed=game_emb(MinesGame,
                    "💣  BOOM — Mina!",
                    f"<@{self.player_id}> izgubio **{self.pot}** {COIN}.",
                    discord.Color.red()), view=self)
                await add_played(self.player_id)
            else:
                self.safe += 1
                pot = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
                await i.response.edit_message(embed=game_emb(MinesGame,
                    f"✅  Sigurno! ({self.safe} otvoreno)",
                    f"<@{self.player_id}> — nastavi ili naplati!",
                    discord.Color.green(),
                    fields=[("Potencijalni dobitak", f"**{pot}** {COIN}", True)]), view=self)
        return cb

    async def cashout(self, i: discord.Interaction):
        if i.user.id!=self.player_id:
            return await i.response.send_message("Nije tvoja igra!", ephemeral=True)
        if not self.active: return
        self.active=False; self.stop()
        for x in self.children: x.disabled=True
        if self.safe == 0:
            await add_coins(self.player_id, self.pot)
            return await i.response.edit_message(embed=game_emb(MinesGame,
                "Naplata","Nisi otvorio nijedno polje — ulog vraćen.",
                discord.Color.gold()), view=self)
        win = int(self.pot * (1 + self.safe * MINES_COUNT / 20))
        await add_coins(self.player_id, win); await add_win(self.player_id, 40)
        await i.response.edit_message(embed=game_emb(MinesGame,
            "💰  Naplata!", f"<@{self.player_id}> uzima nagradu!", discord.Color.gold(),
            fields=[("Polja otvorena", str(self.safe), True),
                    ("Dobitak", f"**{win}** {COIN}", True)]), view=self)

class MinesLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.player=None; self.closed=False

    @discord.ui.button(label="💣  Zaigraj Mines  —  100 🪙", style=discord.ButtonStyle.danger)
    async def join(self, i: discord.Interaction, b):
        if self.closed:
            return await i.response.send_message("Zatvoreno!", ephemeral=True)
        if self.player is not None:
            return await i.response.send_message("Neko već igra!", ephemeral=True)
        await ensure_user(i.user.id, i.user.display_name)
        if not await deduct_coins(i.user.id, MINES_COST):
            return await i.response.send_message(f"Trebaš {MINES_COST} {COIN}!", ephemeral=True)
        self.player=i.user.id; self.closed=True; self.stop()
        await i.response.send_message("Igra počinje!", ephemeral=True)

class MinesGame:
    NAME  = "Mines"
    COLOR = discord.Color.from_rgb(60, 60, 80)

    async def run(self, channel):
        lobby = MinesLobbyView()
        msg = await channel.send(embed=game_emb(
            MinesGame, "💣  MINES",
            "Otvori polja i izbjegni mine! Naplati kad god hoćeš.",
            self.COLOR,
            fields=[
                ("Ulog", f"**{MINES_COST}** {COIN}", True),
                ("Mine", f"**{MINES_COUNT}** od 25", True),
                ("Savjet", "Klikni 'Naplata' na vrijeme!", True),
            ]), view=lobby)
        await asyncio.sleep(TICK)
        lobby.closed = True
        if lobby.player is None:
            await msg.edit(embed=game_emb(MinesGame, "MINES",
                "Niko se nije prijavio.", discord.Color.greyple()), view=None)
            return
        mines = set(random.sample(range(25), MINES_COUNT))
        gv = MinesView(mines, MINES_COST, lobby.player)
        await msg.edit(embed=game_emb(MinesGame,
            "💣  MINES — Igra počela!",
            f"<@{lobby.player}> — klikni polja, izbjegni mine!",
            discord.Color.blue()), view=gv)
        await gv.wait()
        await post_achievements(channel, lobby.player)
        await asyncio.sleep(5)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 9 — EMOJI GUESS
# ═══════════════════════════════════════════════════════════════════════════════
EMOJI_QS = [
    {"emojis":"👠 ⏰ 🎃","answers":["cinderella","pepeljuga"],"hint":"Disney bajka"},
    {"emojis":"🌊 🐠 🔍","answers":["nemo","finding nemo"],"hint":"Animirani film"},
    {"emojis":"🦁 👑 🌍","answers":["lion king","kralj lavova","simba"],"hint":"Disney"},
    {"emojis":"❄️ 👸 ✨","answers":["frozen","ledeno kraljevstvo","elsa"],"hint":"Animirani film"},
    {"emojis":"🕷️ 👦 🏙️","answers":["spiderman","spider-man"],"hint":"Superjunak"},
    {"emojis":"🦇 🤵 🌃","answers":["batman","betmen"],"hint":"Gotham City"},
    {"emojis":"⚡ 🧙 📚","answers":["harry potter","hari poter"],"hint":"Čarobnjak"},
    {"emojis":"💍 🧝 🌋","answers":["lord of the rings","lotr","gospodar prstenova"],"hint":"Fantasy"},
    {"emojis":"🚀 👨‍🚀 ♾️","answers":["interstellar"],"hint":"Nolan sci-fi"},
    {"emojis":"🃏 🤡 🃏","answers":["joker","džoker"],"hint":"DC vilain"},
    {"emojis":"🐉 🔥 ⚔️","answers":["game of thrones","igra prijestolja"],"hint":"HBO serija"},
    {"emojis":"💊 🔵 🔴","answers":["matrix","matriks"],"hint":"Sci-fi klasik"},
    {"emojis":"🧟 🔫 🌍","answers":["walking dead"],"hint":"AMC serija"},
    {"emojis":"👨‍🍳 💀 🧪","answers":["breaking bad"],"hint":"Hemičar-kriminalac"},
    {"emojis":"🔫 🕶️ 📱","answers":["john wick","džon vik"],"hint":"Keanu Reeves"},
    {"emojis":"🧠 🌀 💤","answers":["inception","san"],"hint":"Snovi u snovima"},
    {"emojis":"🦈 🏖️ 🩸","answers":["ajkula","jaws"],"hint":"Spielberg horor"},
    {"emojis":"🤖 🌋 🏝️","answers":["lost","izgubljeni"],"hint":"ABC serija"},
    {"emojis":"🦸 🛡️ ⚡","answers":["avengers","avengeri"],"hint":"Marvel"},
    {"emojis":"🐍 🪄 🧙","answers":["harry potter","hari poter"],"hint":"Hogwarts"},
]
EMOJI_REWARD = 250
EMOJI_TIME   = 45

class EmojiGame:
    NAME  = "Emoji Guess"
    COLOR = discord.Color.from_rgb(255, 200, 0)

    async def run(self, channel):
        q = random.choice(EMOJI_QS)
        msg = await channel.send(embed=game_emb(
            EmojiGame, "🎭  EMOJI GUESS",
            f"# {q['emojis']}\n\nŠta predstavljaju ovi emoji?",
            self.COLOR,
            fields=[
                ("Hint",    q["hint"], True),
                ("Nagrada", f"**{EMOJI_REWARD}** {COIN}", True),
                ("Vrijeme", f"**{EMOJI_TIME}s**", True),
            ]))
        winner_uid = None
        def check(m): return (m.channel.id==channel.id and not m.author.bot
                               and any(a in m.content.lower() for a in q["answers"]))
        try:
            am = await channel.bot.wait_for("message", timeout=EMOJI_TIME, check=check)
            winner_uid = am.author.id
        except asyncio.TimeoutError: pass

        if winner_uid:
            await ensure_user(winner_uid, am.author.display_name)
            await add_coins(winner_uid, EMOJI_REWARD); await add_win(winner_uid, 30)
            result = game_emb(EmojiGame, "✅  Tačan Odgovor!", None, discord.Color.green(),
                fields=[("Pobjednik", f"<@{winner_uid}>", True),
                        ("Dobitak", f"**{EMOJI_REWARD}** {COIN}", True),
                        ("Odgovor", q["answers"][0].title(), True)])
            await post_achievements(channel, winner_uid)
        else:
            result = game_emb(EmojiGame, "⏰  Vrijeme Isteklo",
                "Niko nije pogodio.", discord.Color.red(),
                fields=[("Tačan odgovor", q["answers"][0].title(), True)])
        await msg.edit(embed=result)
        await asyncio.sleep(8)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME 10 — JACKPOT EVENT
# ═══════════════════════════════════════════════════════════════════════════════
JP_COST = 120

class JackpotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TICK)
        self.entrants: list[int]=[]; self.pot=0; self.closed=False

    @discord.ui.button(label="💰  Ulozi u Jackpot  —  120 🪙", style=discord.ButtonStyle.danger)
    async def enter(self, i: discord.Interaction, b):
        if self.closed:
            return await i.response.send_message("Jackpot zatvoren!", ephemeral=True)
        uid = i.user.id
        if uid in self.entrants:
            return await i.response.send_message(
                f"Već si u igri! Pot: **{self.pot}** {COIN}", ephemeral=True)
        await ensure_user(uid, i.user.display_name)
        if not await deduct_coins(uid, JP_COST):
            return await i.response.send_message(f"Trebaš {JP_COST} {COIN}!", ephemeral=True)
        self.entrants.append(uid); self.pot+=JP_COST
        await i.response.send_message(
            f"U igri! Igrači: **{len(self.entrants)}**  •  Pot: **{self.pot}** {COIN}", ephemeral=True)

class JackpotGame:
    NAME  = "Jackpot Event"
    COLOR = discord.Color.from_rgb(200, 30, 30)

    async def run(self, channel):
        view = JackpotView()
        msg = await channel.send(embed=game_emb(
            JackpotGame, "💰  JACKPOT EVENT",
            "Svi ulaze — **jedan** osvaja sve!",
            self.COLOR,
            fields=[
                ("Ulog", f"**{JP_COST}** {COIN}", True),
                ("Nagrada", "Cijeli pot + Legendarni item", True),
                ("Prijave", f"**{TICK}s**", True),
                ("Šansa", "Proporcionalna broju igrača", False),
            ]), view=view)
        await asyncio.sleep(TICK)
        view.closed = True; view.stop()

        if len(view.entrants) < 2:
            await msg.edit(embed=game_emb(JackpotGame, "JACKPOT EVENT",
                "Premalo igrača! Ulog vraćen.", discord.Color.red()), view=None)
            for uid in view.entrants: await add_coins(uid, JP_COST)
            return

        for cd in [5,4,3,2,1]:
            await msg.edit(embed=game_emb(JackpotGame,
                f"💰  Jackpot — Izvlačenje za {cd}...", None, self.COLOR,
                fields=[("Igrači", str(len(view.entrants)), True),
                        ("Pot", f"**{view.pot}** {COIN}", True)]), view=None)
            await asyncio.sleep(1)

        winner = random.choice(view.entrants)
        await add_coins(winner, view.pot); await add_win(winner, 100)
        rtype, item = rand_prize("legendary"); await add_item(winner, rtype, item)
        for uid in view.entrants:
            await add_played(uid)
            await award_jackpot_ach(uid, uid==winner, channel)

        await msg.edit(embed=game_emb(JackpotGame,
            "🎉  JACKPOT — POBJEDNIK!",
            f"<@{winner}> uzima sve!",
            discord.Color.gold(),
            fields=[("Pot", f"**{view.pot}** {COIN}", True),
                    ("Legendarni item", item, True)]))
        await asyncio.sleep(10)

async def award_jackpot_ach(uid, won, channel):
    from database import award_achievement, ACHIEVEMENT_DEFS
    if won:
        newly = await award_achievement(uid, "jackpot")
        if newly:
            await channel.send(embed=emb("Achievement Otključan!",
                f"<@{uid}> — **{ACHIEVEMENT_DEFS['jackpot']}**",
                discord.Color.from_rgb(255,215,0)))


# ── Registry ──────────────────────────────────────────────────────────────────
ALL_GAMES = [
    EmojiGame, QuizGame, SlotGame, WheelGame, RouletteGame,
    ScratchGame, LotteryGame, BingoGame, MinesGame, JackpotGame,
]
