"""
Main Job Alert Bot — Telegram + Scheduler (24/7)
Uses requests directly (python-telegram-bot httpx has timeout issues in WSL)
"""
import os
import sys
import time
import logging
import requests
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TIMEZONE,
    SCHEDULE_HOURS,
    MAX_JOBS_PER_NOTIFICATION,
    LOCATION_FILTER,
    ENVIRONMENT,
    IS_RAILWAY,
)
from database import init_db, is_job_sent, mark_job_sent, cleanup_old_jobs
from scraper import scrape_all
from formatter import format_job_message, format_no_jobs

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_notification(message: str):
    """Send message via Telegram Bot API using requests."""
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info("Notification sent successfully")
        else:
            logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


def send_progress(message: str):
    """Send a short progress update to Telegram."""
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"⏳ {message}",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except Exception as e:
        logger.debug(f"Progress notification failed: {e}")


def send_heartbeat():
    """Send a heartbeat to show the bot is alive."""
    env_label = "Railway" if IS_RAILWAY else "Local"
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"💓 <b>Bot Heartbeat</b> — {datetime.now().strftime('%H:%M')}\n🖥️ Environment: {env_label}\n\nBot masih aktif dan akan cek lagi jam berikutnya.",
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        logger.info("Heartbeat sent")
    except Exception as e:
        logger.debug(f"Heartbeat failed: {e}")


def job_check():
    """Main job: scrape with streaming — send notification immediately on each match."""
    logger.info("=" * 50)
    logger.info(f"Job check started at {datetime.now()}")

    send_progress("Mulai cek lowongan di Manado...")

    found_count = 0
    sent_count = 0

    def on_job_found(job):
        """Callback: called immediately when a matching job is found."""
        nonlocal found_count, sent_count
        found_count += 1

        job_key = f"{job['company'].lower()}|{job['position'].lower()}|{job['source']}"
        if not is_job_sent(job_key):
            mark_job_sent(job_key, job["company"], job["position"], job["source"])
            sent_count += 1
            # Send immediately — don't wait for all scraping to finish
            message = format_job_message([job], start_index=sent_count)
            send_notification(message)
            logger.info(f"Streamed job #{sent_count}: {job['company']} | {job['position']}")

    # Scrape with streaming callback
    scrape_all(on_job_found=on_job_found)

    logger.info(f"Job check completed — found {found_count}, sent {sent_count}")

    if sent_count == 0:
        send_notification(format_no_jobs())

    # Cleanup old entries
    cleanup_old_jobs()


def get_status_message() -> str:
    """Build a status report message."""
    import sqlite3
    from config import DB_PATH

    env_label = "Railway (Production)" if IS_RAILWAY else "Local"

    # Count sent jobs
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sent_jobs")
        total_sent = c.fetchone()[0]
        conn.close()
    except Exception:
        total_sent = 0

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"📊 <b>Bot Status</b>\n\n"
        f"🖥️ Environment: {env_label}\n"
        f"📍 Location: {LOCATION_FILTER.title()}\n"
        f"⏰ Timezone: {TIMEZONE}\n"
        f"🕘 Schedule: 24/7 (setiap jam)\n"
        f"📋 Max jobs per notif: {MAX_JOBS_PER_NOTIFICATION}\n"
        f"📨 Total jobs sent: {total_sent}\n"
        f"🕐 Last check: {now}\n"
        f"✅ Status: <b>Active</b>"
    )


def poll_updates():
    """Poll Telegram for /status commands and reply."""
    logger.info("Starting update poller for /status command")
    offset = 0

    while True:
        try:
            resp = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "")
                    chat_id = message.get("chat", {}).get("id")

                    if text.strip() == "/status" and chat_id:
                        status_msg = get_status_message()
                        requests.post(
                            f"{TELEGRAM_API}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": status_msg,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True,
                            },
                            timeout=15,
                        )
                        logger.info(f"/status replied to chat {chat_id}")
        except Exception as e:
            logger.debug(f"Poll error: {e}")

        time.sleep(1)


def main():
    """Start the scheduler."""
    logger.info("Starting Job Alert Bot...")
    logger.info(f"Timezone: {TIMEZONE}")
    logger.info(f"Schedule hours: {SCHEDULE_HOURS} (24/7)")
    logger.info(f"Location filter: {LOCATION_FILTER}")
    logger.info(f"Environment: {ENVIRONMENT} (Railway: {IS_RAILWAY})")

    # Init database
    init_db()

    # Send startup notification
    env_label = "Railway (Production)" if IS_RAILWAY else "Local"
    send_notification(
        "🤖 <b>Job Alert Bot Started!</b>\n"
        f"🌏 Timezone: {TIMEZONE}\n"
        f"🕘 Schedule: 24/7 (setiap jam)\n"
        f"📍 Location: {LOCATION_FILTER.title()} only\n"
        f"📋 Max jobs per notification: {MAX_JOBS_PER_NOTIFICATION}\n"
        f"🖥️ Environment: {env_label}\n\n"
        "Bot akan cek lowongan setiap jam, 24 jam sehari.\n"
        "Ketik /status untuk cek status bot."
    )

    # Start /status poller in background thread
    import threading
    poller_thread = threading.Thread(target=poll_updates, daemon=True)
    poller_thread.start()
    logger.info("Status poller started")

    # Setup scheduler
    scheduler = BlockingScheduler(timezone=TIMEZONE)

    # Schedule for each hour in SCHEDULE_HOURS (24 jam)
    for hour in SCHEDULE_HOURS:
        trigger = CronTrigger(hour=hour, minute=0)
        scheduler.add_job(
            job_check,
            trigger=trigger,
            id=f"job_check_{hour}",
            name=f"Job check at {hour}:00",
            replace_existing=True,
        )
        logger.info(f"Scheduled job check at {hour}:00")

    # Also run once immediately on startup
    scheduler.add_job(
        job_check,
        "date",
        id="job_check_startup",
        name="Startup job check",
        replace_existing=True,
    )

    # Heartbeat every 3 hours to show bot is alive
    for hour in [0, 3, 6, 9, 12, 15, 18, 21]:
        trigger = CronTrigger(hour=hour, minute=30)
        scheduler.add_job(
            send_heartbeat,
            trigger=trigger,
            id=f"heartbeat_{hour}",
            name=f"Heartbeat at {hour}:30",
            replace_existing=True,
        )
        logger.info(f"Scheduled heartbeat at {hour}:30")

    try:
        logger.info("Scheduler started. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        send_notification("🛑 Job Alert Bot dihentikan.")


if __name__ == "__main__":
    main()
