"""
Format job listings into Telegram message
"""
from config import MAX_JOBS_PER_NOTIFICATION


def format_job_message(jobs: list) -> str:
    """Format a list of jobs into a Telegram HTML message."""
    if not jobs:
        return None

    messages = []
    for i, job in enumerate(jobs[:MAX_JOBS_PER_NOTIFICATION], 1):
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
