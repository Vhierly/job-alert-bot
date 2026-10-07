# Job Alert Bot 🤖

Bot Telegram yang cari lowongan kerja di Manado (fokus Excel & Office) dan kirim notif real-time ke Telegram.

## Fitur

- 🔔 **Notif Real-Time** — Langsung kirim tiap nemu job match, ga nunggu scrape semua
- 📍 **Manado Only** — Filter lokasi Manado
- 🚫 **Skip Sales** — Filter otomatis buat job sales, marketing, dll
- 📱 **Multi-Source** — Kalibrr, LinkedIn (confirmed working), JobStreet, Indeed, Google Jobs, Glints, Twitter/X, Facebook, Instagram, Job Fair (auto-skip if blocked)
- 💓 **Heartbeat** — Bot kirim sinyal hidup tiap 3 jam
- ⏰ **24/7** — Cek lowongan setiap jam, hari libur pun tetap jalan
- 🔄 **Anti-Duplicate** — Job sama ga dikirim 2x (Supabase database)
- 🖥️ **Environment Detection** — Bot tau dia jalan di Local atau Railway

## Perintah Bot

| Perintah | Keterangan |
|---|---|
| `/status` | Cek status bot (environment, total jobs sent, schedule) |

## Cara Deploy ke Railway

1. Fork repo ini
2. Buka [Railway](https://railway.app) → New Project → Deploy from GitHub repo
3. Set environment variables:
   - `TELEGRAM_BOT_TOKEN` — Token dari @BotFather
   - `TELEGRAM_CHAT_ID` — Chat ID dari @userinfobot
4. Railway auto-deploy via Dockerfile

## Cara Jalankan Lokal

```bash
# Clone repo
git clone https://github.com/Vhierly/job-alert-bot.git
cd job-alert-bot

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set environment variables
cp .env.example .env
# Edit .env dengan token Telegram lo

# Jalankan
python bot.py
```

## Environment Variables

| Variable | Keterangan |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token bot dari @BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram lo |

## Tech Stack

- Python 3.11
- Playwright (headless browser)
- APScheduler (cron scheduler)
- Telegram Bot API
- SQLite (anti-duplicate)

## License

MIT
