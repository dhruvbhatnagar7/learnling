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


def report_text(session) -> str:
    """Plain-text report of a `stand.StandSession`: time read, each read, and words to practise."""
    summary = build_summary(session.orchestrator.session)
    words_helped, minutes, questions_asked = session.words_helped, session.minutes, session.questions_asked
    lines = [
        f"learnling reading session, {datetime.now():%A %B %-d, %-I:%M %p}",
        "",
        f"Time reading aloud: about {max(1, round(minutes))} minute(s), over {summary['reading_attempts']} reads.",
    ]
    for i, stat in enumerate(summary["reading_stats"], start=1):
        label = "First read (with hints)" if i == 1 else "Second read (on their own)"
        accuracy = f"{stat['accuracy']:.0%}" if stat["accuracy"] is not None else "-"
        wcpm = stat.get("wcpm")
        lines.append(f"{label}: {accuracy} of words matched the page"
                     + (f", {wcpm} words correct per minute." if wcpm is not None else "."))
        missed = _missed_words(stat)
        if missed:
            lines.append("  Words that didn't match: " + ", ".join(missed) + ".")
        if i == 1:
            if words_helped:
                lines.append("  It gave a hint for: " + ", ".join(words_helped) + ".")
            else:
                lines.append("  No hints needed.")
    lines.append(f"Story questions talked about: {questions_asked}.")
    lines += [
        "",
        "learnling is a prototype. Its speech recognition is not yet accurate on children's voices,",
        "so treat these numbers as a rough guide and listen for yourself.",
    ]
    return "\n".join(lines) + "\n"


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
