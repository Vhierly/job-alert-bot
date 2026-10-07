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


def format_all_manado_message(jobs: list) -> str:
    """Format all available Manado jobs into one neat message (fallback mode)."""
    if not jobs:
        return format_no_jobs()

    lines = [
        f"📋 <b>Semua Lowongan Tersedia di Manado</b>",
        f"🔍 Tidak ada yang match keyword, ini semua yang tersedia:",
        "",
    ]

    for i, job in enumerate(jobs, 1):
        lines.append(f"<b>{i}. {job['position']}</b>")
        lines.append(f"   🏢 {job['company']}")
        lines.append(f"   📍 {job['location']}")
        lines.append(f"   ⏰ {job['deadline']}")
        lines.append(f"   🔗 {job['link']}")
        lines.append(f"   📰 {job['source']}")
        lines.append("")

    lines.append(f"Total: {len(jobs)} lowongan")
    lines.append("Jika tidak relevan, abaikan saja. Bot akan cek lagi jam berikutnya.")

    return "\n".join(lines)


def format_no_jobs() -> str:
    return "✅ Tidak ada lowongan baru di Manado saat ini. Bot akan cek lagi jam berikutnya."
