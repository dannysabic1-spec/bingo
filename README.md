# 🎮 Discord Game Bot

Auto-posting game bot s 10 igara, coin ekonomijom i nagradama.  
Igre se šalju **automatski** u određeni kanal — jedna za drugom u krug.

---

## 🎮 10 Igara

| Igra | Opis | Ulaz |
|------|------|------|
| 😀 Emoji Guess | Pogodi šta emoji prikazuju (tipka u chat) | Besplatno |
| 🎵 Nastavi Pjesmu | Jala Brat, Buba Corelli tekstovi | Besplatno |
| 🎰 Slot Machine | Klikni dugme → animirani reeli | 50 🪙 |
| 🎡 Kolo Sreće | Animirani spin kola | 60 🪙 |
| 🎯 Rulet | Okladi se, gledaj kuglu | 70 🪙 |
| 🎟️ Grebalica | Kupi i odmah ogrebi | 40 🪙 |
| 🎲 Lutrija | 6 nasumičnih brojeva, draw | 60 🪙 |
| 🎱 Bingo | Multiplayer, 15 brojeva | 80 🪙 |
| 💣 Mines | 5×5 grid dugmadi, izbjegni mine | 100 🪙 |
| 👑 Jackpot Event | Svi ulažu, jedan uzima sve | 120 🪙 |

## 🎁 Nagrade

- **Coini** 🪙 — osnovna valuta
- **Dekoracije** 🎨 — Zlatna Zvijezda, Vatreni Efekt, Rainbow Aura...
- **Avatari** 🖼️ — Zmaj, Lav, Cyber, Čarobnjak...
- **Nitro** 💜 — samo iz jackpot nagrada

## 💰 Ekonomija

- Novi korisnici dobivaju **500 🪙** automatski
- `!daily` — dnevna nagrada 200–700 🪙
- `!balans` — stanje, XP, level, pobjede
- `!top` — ljestvica
- `!inventar` — sve nagrade
- `!transfer @user <iznos>` — slanje coina

---

## 🚀 Pokretanje (lokalno / hosting)

### 1. Instaliraj pakete

```bash
pip install -r requirements.txt
```

### 2. Postavi `.env` fajl

```bash
cp .env.example .env
# uredi .env i popuni vrijednosti
```

```env
DISCORD_TOKEN=tvoj_bot_token
GAME_CHANNEL_ID=id_kanala
GAME_INTERVAL=180
```

### 3. Pokreni

```bash
python bot.py
```

---

## 🌐 Hosting (VPS / Replit / Railway)

### Replit
- Dodaj `DISCORD_TOKEN` i `GAME_CHANNEL_ID` u Secrets
- Pokreni `python discord_bot/bot.py`

### Railway / Render / VPS
```bash
git clone <repo>
cd discord_bot
pip install -r requirements.txt
python bot.py
```

---

## ⚙️ Konfiguracija

| Varijabla | Opis | Default |
|-----------|------|---------|
| `DISCORD_TOKEN` | Bot token | obavezno |
| `GAME_CHANNEL_ID` | ID kanala za igre | obavezno |
| `GAME_INTERVAL` | Pauza između igara (sekunde) | 180 |

---

## 🔧 Discord Developer Setup

1. Idi na [discord.com/developers](https://discord.com/developers/applications)
2. **New Application** → Bot → **Reset Token** → kopiraj token
3. Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`, `Manage Roles` (za role nagrade)
4. Invite link:
```
https://discord.com/oauth2/authorize?client_id=BOT_ID&permissions=274877908992&scope=bot
```

---

## 📁 Struktura

```
discord_bot/
├── bot.py          # Main entry, komande, game loop
├── games.py        # Svih 10 igara s Views/dugmadima
├── database.py     # SQLite ekonomija
├── requirements.txt
├── .env.example
└── README.md
```
