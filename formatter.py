"""
Format job listings into Telegram message
"""
from config import MAX_JOBS_PER_NOTIFICATION


def format_job_message(jobs: list, start_index: int = 1) -> str:
    """Format a list of jobs into a Telegram HTML message.
    start_index: counter number for the first job (used by streaming mode)."""
    if not jobs:
        return None

    messages = []
    for i, job in enumerate(jobs[:MAX_JOBS_PER_NOTIFICATION], start_index):
        msg = f"""
<b>📋 Lowongan #{i}</b>

🏢 <b>Perusahaan:</b> {job['company']}
💼 <b>Posisi:</b> {job['position']}
📍 <b>Lokasi:</b> {job['location']}
⏰ <b>Batas Akhir:</b> {job['deadline']}
📧 <b>Email:</b> {job['email']}
🔗 <b>Link:</b> {job['link']}
📰 <b>Sumber:</b> {job['source']}
"""
        messages.append(msg)

    header = f"🔔 <b>Job Alert — {len(jobs[:MAX_JOBS_PER_NOTIFICATION])} lowongan baru di Manado!</b>\n"
    footer = "\nJika tidak relevan, abaikan saja. Bot akan cek lagi jam berikutnya."

    return header + "\n---\n".join(messages) + footer


def format_no_jobs() -> str:
    return "✅ Tidak ada lowongan baru di Manado saat ini. Bot akan cek lagi jam berikutnya."
