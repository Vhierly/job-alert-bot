"""
Supabase database to track sent jobs (avoid duplicates)
"""
import logging
from datetime import datetime

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def init_db():
    """Initialize database — table is created via Supabase SQL editor."""
    logger.info("Supabase database initialized")


def is_job_sent(job_key: str) -> bool:
    """Check if a job has already been sent."""
    try:
        result = supabase.table("sent_jobs").select("id").eq("job_key", job_key).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Supabase query error: {e}")
        return False


def mark_job_sent(job_key: str, company: str, position: str, source: str):
    """Mark a job as sent."""
    try:
        supabase.table("sent_jobs").insert({
            "job_key": job_key,
            "company": company,
            "position": position,
            "source": source,
            "sent_at": datetime.now().isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"Supabase insert error: {e}")


def cleanup_old_jobs(days=30):
    """Remove entries older than N days."""
    try:
        cutoff = datetime.now().timestamp() - (days * 86400)
        supabase.table("sent_jobs").delete().lt("sent_at", datetime.fromtimestamp(cutoff).isoformat()).execute()
    except Exception as e:
        logger.error(f"Supabase cleanup error: {e}")


def get_sent_count() -> int:
    """Get total number of sent jobs."""
    try:
        result = supabase.table("sent_jobs").select("id", count="exact").execute()
        return result.count or 0
    except Exception as e:
        logger.error(f"Supabase count error: {e}")
        return 0
