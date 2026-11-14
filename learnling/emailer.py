"""The session report as a short email to the adult.

    LEARNLING_SMTP_USER=you@gmail.com LEARNLING_SMTP_PASSWORD='app password' \\
        python -m learnling stand ... --email-to you@gmail.com

Gmail needs an app password (Google Account, Security, App passwords), not the
account password. Other providers work with `LEARNLING_SMTP_HOST` and
`LEARNLING_SMTP_PORT` (SSL).

The email carries numbers and practice words only: no audio, no transcript,
and nothing the reader said in answer to a question. No name either; the
reader is "your reader". Check the consent form covers who it goes to.
"""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

from learnling.report import build_summary


def report_text(session, full_report_coming: bool = False) -> str:
    """Short plain-text report of a `stand.StandSession`, for the adult right after the session.

    It only says what the stand measures reliably while listening: time, pace
    and which words needed a hint. Which words were read wrong is left to the
    full report, scored afterwards by a slower and better recogniser: the live
    one is there to time hints and is too unreliable to judge words.
    """
    summary = build_summary(session.orchestrator.session)
    stats = summary["reading_stats"]
    reads = summary["reading_attempts"]
    lines = [
        f"learnling reading session, {datetime.now():%A %B %-d, %-I:%M %p}",
        "",
        f"Read for about {max(1, round(session.minutes))} minute(s)"
        + (", twice." if reads == 2 else f", {reads} time(s)." if reads != 1 else ", once."),
    ]
    paces = [stat.get("wpm") for stat in stats]
    for i, pace in enumerate(paces, start=1):
        label = "First read" if i == 1 else "Second read"
        line = f"{label}: about {round(pace)} words per minute" if pace else f"{label}: done"
        if i == 2 and pace and paces[0]:
            line += _compared(paces[0], pace)
        line += "."
        if i == 1:
            line += (" Hints given for: " + ", ".join(session.words_helped) + "." if session.words_helped
                     else " No hints needed.")
        lines.append(line)
    if session.questions_asked:
        lines.append(f"Talked about {session.questions_asked} story question(s).")
    if full_report_coming:
        lines += ["", "A full report, with the words to practise, will follow by email in a few minutes."]
    return "\n".join(lines) + "\n"


def _compared(first: float, second: float) -> str:
    if second >= first * 1.05:
        return ", a little quicker than the first"
    if second <= first * 0.95:
        return ", a little slower than the first"
    return ", about the same pace as the first"


#: Enough words for an adult to act on; a longer list reads as noise.
_MAX_LISTED = 6


def _missed_words(stat: dict) -> list[str]:
    """Page words read differently or skipped, where the recogniser was sure."""
    missed = []
    for entry in stat["words_to_look_at"]:
        if entry["sure"] and entry["kind"] in ("substitution", "omission") and entry["word"] not in missed:
            word = entry["word"]
            missed.append(f"{word} (read as {entry['read_as']})" if entry.get("read_as") else f"{word} (skipped)")
    return missed


def send_report(to: str, body: str, subject: str | None = None) -> None:
    user = os.environ.get("LEARNLING_SMTP_USER")
    password = os.environ.get("LEARNLING_SMTP_PASSWORD")
    if not user or not password:
        raise RuntimeError("set LEARNLING_SMTP_USER and LEARNLING_SMTP_PASSWORD to send the report")
    message = EmailMessage()
    message["From"] = user
    message["To"] = to
    message["Subject"] = subject or f"learnling reading session, {datetime.now():%b %-d}"
    message.set_content(body)
    host = os.environ.get("LEARNLING_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("LEARNLING_SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=30) as server:
        server.login(user, password)
        server.send_message(message)
