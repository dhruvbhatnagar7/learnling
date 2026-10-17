"""Session report for the adult in the loop: stats, not raw transcripts.

By default the report only includes what's needed for a teacher or parent
to see progress — accuracy, words-per-minute, words correct per minute, miscue counts, assessment
categories, how many questions came up — matching the data policy in
SAFETY.md. It also lists the page words behind the miscue counts, each with
the one word heard in its place and the spelling pattern it points to, so an
adult knows what to practise. Raw transcript text is only included if the caller explicitly
opts in.
"""

from __future__ import annotations

import json

from learnling.agents.reading import normalize_words
from learnling.models import Miscue, Session
from learnling.patterns import PATTERN_NAMES, is_self_correction, patterns_for

#: A pattern needs this many different words before it is listed as one to
#: practise. One word can be a recogniser mishearing; the same kind of slip
#: on several words is more likely the reader.
MIN_WORDS_PER_PATTERN = 2

#: Things a reader does that are not misreadings, listed apart from mistakes.
_NOT_MISTAKES = ("self_correction", "repeat")

_PATTERN_NOTE = (
    "*Patterns seen in at least two different words, grouped by spelling. Use "
    "it as a guide to what to listen for next time, not a diagnosis: the "
    "recogniser can mishear, especially with children's voices.*"
)


def _word_entry(miscue: Miscue, sure: bool, page: list[str]) -> dict:
    next_word = page[miscue.position] if miscue.position < len(page) else None
    if miscue.kind == "insertion" and miscue.heard == next_word:
        # "the the": saying a word twice is not a misreading.
        return {
            "word": next_word,
            "read_as": miscue.heard,
            "kind": "repeat",
            "patterns": [],
            "sure": sure,
        }
    if is_self_correction(miscue, next_word):
        tried = Miscue("substitution", next_word, miscue.heard, miscue.position)
        return {
            "word": next_word,
            "read_as": miscue.heard,
            "kind": "self_correction",
            "patterns": patterns_for(tried),
            "sure": sure,
        }
    return {
        "word": miscue.expected,
        "read_as": miscue.heard,
        "kind": miscue.kind,
        "patterns": patterns_for(miscue),
        "sure": sure,
    }


def _words_to_look_at(notes: dict) -> list[dict]:
    """The page words behind the miscue counts, raised ones first."""
    result = notes.get("reading_result")
    if result is None:
        return []
    page = normalize_words(result.passage)
    return [_word_entry(m, True, page) for m in result.miscues] + [
        _word_entry(m, False, page) for m in result.held_back
    ]


def _describe(entry: dict) -> str:
    if entry["kind"] == "repeat":
        text = f'"{entry["word"]}", said twice'
    elif entry["kind"] == "self_correction":
        text = f'"{entry["word"]}", first read as "{entry["read_as"]}", then fixed'
    elif entry["kind"] == "omission":
        text = f'"{entry["word"]}", skipped'
    elif entry["kind"] == "insertion":
        text = f'added "{entry["read_as"]}"'
    else:
        text = f'"{entry["word"]}", read as "{entry["read_as"]}"'
    # Short names here; the "Sounds to practise" list gives the examples.
    names = [
        PATTERN_NAMES[p].split(" (")[0]
        for p in entry["patterns"]
        if p not in ("skipped", "added")
    ]
    if names:
        text += f" ({'; '.join(names)})"
    return text


def _pattern_summary(reading_stats: list[dict]) -> list[tuple[str, list[str]]]:
    """Each pattern with the words that point to it, most words first."""
    words: dict[str, list[str]] = {}
    for stat in reading_stats:
        for entry in stat["words_to_look_at"]:
            if not entry["sure"] or entry["kind"] in _NOT_MISTAKES:
                continue
            label = entry["word"] or entry["read_as"]
            for pattern in entry["patterns"]:
                if label not in words.setdefault(pattern, []):
                    words[pattern].append(label)
    order = list(PATTERN_NAMES)
    repeated = [item for item in words.items() if len(item[1]) >= MIN_WORDS_PER_PATTERN]
    return sorted(repeated, key=lambda item: (-len(item[1]), order.index(item[0])))


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
                "wcpm": e["report_notes"].get("wcpm"),
                "assessment": e["report_notes"].get("assessment"),
                "miscue_counts": e["report_notes"].get("miscue_counts"),
                "suppressed_miscues": e["report_notes"].get("suppressed_miscues"),
                "words_to_look_at": _words_to_look_at(e["report_notes"]),
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
        lines.append("| # | Accuracy | WPM | WCPM | Assessment | Miscues | Not raised |")
        lines.append("|---|----------|-----|------|------------|---------|------------|")
        for i, stat in enumerate(summary["reading_stats"], start=1):
            accuracy = f"{stat['accuracy']:.0%}" if stat["accuracy"] is not None else "-"
            wpm = f"{stat['wpm']:.0f}" if stat["wpm"] is not None else "-"
            wcpm = str(stat["wcpm"]) if stat.get("wcpm") is not None else "-"
            miscues = ", ".join(f"{k}: {v}" for k, v in (stat["miscue_counts"] or {}).items()) or "none"
            suppressed = stat.get("suppressed_miscues") or 0
            lines.append(
                f"| {i} | {accuracy} | {wpm} | {wcpm} | {stat['assessment']} | {miscues} | {suppressed} |"
            )
        lines.append("")
        lines.append(
            "*Not raised: possible miscues the speech recogniser was not confident "
            "enough about to mention to the learner. See `MISCUE_CONFIDENCE_THRESHOLD`.*"
        )
        lines.append("")

        summary_rows = _pattern_summary(summary["reading_stats"])
        if summary_rows:
            lines.append("## Sounds to practise")
            lines.append("")
            for pattern, words in summary_rows:
                lines.append(f"- {PATTERN_NAMES[pattern].capitalize()}: {', '.join(words)}")
            lines.append("")
            lines.append(_PATTERN_NOTE)
            lines.append("")

        for i, stat in enumerate(summary["reading_stats"], start=1):
            entries = stat["words_to_look_at"]
            if not entries:
                continue
            lines.append(f"## Read {i}: words to look at")
            lines.append("")
            for entry in entries:
                if entry["sure"] and entry["kind"] not in _NOT_MISTAKES:
                    lines.append(f"- {_describe(entry)}")
            # However sure the recogniser was, these were not mistakes.
            fixed = [e for e in entries if e["kind"] in _NOT_MISTAKES]
            if fixed:
                lines.append(
                    "- Fixed or repeated, not mentioned to the reader: "
                    + "; ".join(_describe(e) for e in fixed)
                )
            unsure = [e for e in entries if not e["sure"] and e["kind"] not in _NOT_MISTAKES]
            if unsure:
                lines.append(
                    "- Not sure, so not mentioned to the reader: "
                    + "; ".join(_describe(e) for e in unsure)
                )
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
