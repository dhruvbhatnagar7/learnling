"""Session report for the adult in the loop: stats, not raw transcripts.

By default the report only includes what's needed for a teacher or parent
to see progress — accuracy, words-per-minute, miscue counts, assessment
categories, how many questions came up — matching the data policy in
SAFETY.md. Raw transcript text is only included if the caller explicitly
opts in.
"""

from __future__ import annotations

import json

from learnling.models import Session


def build_summary(session: Session, include_transcripts: bool = False) -> dict:
    reading_events = [e for e in session.events if e["agent"] == "reading"]
    learning_events = [e for e in session.events if e["agent"] == "learning"]

    summary = {
        "age_band": session.profile.age_band,
        "started_at": session.started_at.isoformat(),
        "reading_attempts": len(reading_events),
        "questions_asked": len(learning_events),
        "reading_stats": [
            {
                "accuracy": e["report_notes"].get("accuracy"),
                "wpm": e["report_notes"].get("wpm"),
                "assessment": e["report_notes"].get("assessment"),
                "miscue_counts": e["report_notes"].get("miscue_counts"),
            }
            for e in reading_events
        ],
    }

    if include_transcripts:
        summary["transcripts"] = [
            {"agent": e["agent"], "utterance": e["utterance"], "response": e["response"]}
            for e in session.events
        ]

    return summary


def to_markdown(summary: dict) -> str:
    lines = [
        "# learnling session report",
        "",
        f"- Age band: {summary['age_band']}",
        f"- Started: {summary['started_at']}",
        f"- Reading attempts: {summary['reading_attempts']}",
        f"- Questions asked: {summary['questions_asked']}",
        "",
    ]

    if summary["reading_stats"]:
        lines.append("## Reading")
        lines.append("")
        lines.append("| # | Accuracy | WPM | Assessment | Miscues |")
        lines.append("|---|----------|-----|------------|---------|")
        for i, stat in enumerate(summary["reading_stats"], start=1):
            accuracy = f"{stat['accuracy']:.0%}" if stat["accuracy"] is not None else "-"
            wpm = f"{stat['wpm']:.0f}" if stat["wpm"] is not None else "-"
            miscues = ", ".join(f"{k}: {v}" for k, v in (stat["miscue_counts"] or {}).items()) or "none"
            lines.append(f"| {i} | {accuracy} | {wpm} | {stat['assessment']} | {miscues} |")
        lines.append("")

    if "transcripts" in summary:
        lines.append("## Transcripts")
        lines.append("")
        for entry in summary["transcripts"]:
            lines.append(f"- **{entry['agent']}** heard: \"{entry['utterance']}\" -> \"{entry['response']}\"")
        lines.append("")

    return "\n".join(lines)


def to_json(summary: dict) -> str:
    return json.dumps(summary, indent=2)


def generate_report(session: Session, fmt: str = "markdown", include_transcripts: bool = False) -> str:
    summary = build_summary(session, include_transcripts=include_transcripts)
    if fmt == "json":
        return to_json(summary)
    return to_markdown(summary)
