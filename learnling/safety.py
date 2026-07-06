"""Content guardrails, applied to every spoken response, LLM-backed or not.

`check_output` is the last thing that runs before a response reaches the
child (see `orchestrator.Orchestrator.handle_utterance`) — it doesn't matter
whether the text came from a rule-based template or an LLM call, it passes
through the same gate.

The data-handling side of "safety as architecture" lives here too, as policy
made concrete in code rather than a promise in a document:

- No audio is ever written to disk by this package.
- Transcripts and utterance text live only in the in-memory `Session` for
  the duration of the process; nothing is persisted unless the caller
  explicitly passes `--save-report`, and even then the report is built from
  stats (accuracy, wpm, miscue counts), not raw transcripts, unless
  `--save-report` is paired with an explicit opt-in (see `report.py`).
- No personal information is requested or stored; asking for one (address,
  phone number, full name, school name) is itself a guardrail trigger below.

See `SAFETY.md` for the full policy in prose (COPPA-informed design notes).
"""

from __future__ import annotations

import re

SAFE_REDIRECT = "Let's talk about something else! What's your favorite part of the story so far?"

_GUARDRAIL_PATTERNS = [
    re.compile(r"\b(kill|gun|weapon|blood|violence|hurt (you|someone|him|her|them))\b", re.I),
    re.compile(r"\b(sex|sexual|naked|nude|porn)\b", re.I),
    re.compile(
        r"\b(what'?s your (home )?address|where do you live|phone number|"
        r"last name|social security|school name|what city)\b",
        re.I,
    ),
    re.compile(r"\b(drugs?|alcohol|cigarette|vape)\b", re.I),
]


def check_output(text: str) -> str:
    """Replace `text` with a safe redirect if it trips any guardrail pattern."""
    for pattern in _GUARDRAIL_PATTERNS:
        if pattern.search(text):
            return SAFE_REDIRECT
    return text
