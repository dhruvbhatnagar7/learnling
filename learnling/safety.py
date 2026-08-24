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

#: What a learner hears instead of demotion language: the same step-back,
#: named by the skill being practised rather than by level or difficulty.
DEMOTION_REDIRECT = "Let's practise breaking big words apart."

#: Language that tells a learner they have been moved down.
#:
#: This matters most for exactly the learners the skill/content split exists
#: to serve. An older student practising early phonics already suspects the
#: tool thinks they are behind; hearing it said aloud confirms it and ends
#: the session for good. Step-backs are real and are allowed to happen — they
#: are just named by skill ("breaking big words apart"), never by grade,
#: level, or difficulty.
#:
#: Patterns are deliberately narrow. "Try that line again" and "read it once
#: more, nice and slow" are ordinary reading instructions, not demotion, and
#: must keep passing through untouched.
_DEMOTION_PATTERNS = [
    re.compile(r"\btoo (hard|difficult|advanced|tricky) for you\b", re.I),
    re.compile(r"\byou'?re not ready\b", re.I),
    re.compile(r"\blet'?s go back to (an? )?(easier|simpler|lower|earlier)\b", re.I),
    re.compile(r"\bgo(ing)? back (a|to an?) (level|grade|stage|step)\b", re.I),
    re.compile(r"\b(easier|simpler|lower|baby|babyish)\s+"
               r"(book|passage|text|story|level|words?|reading)\b", re.I),
    re.compile(r"\b(first|second|third|fourth|1st|2nd|3rd|4th)[- ]grade\b", re.I),
    re.compile(r"\bgrade \d\b", re.I),
    re.compile(r"\bfor (younger|little) (kids?|children|students?|readers?)\b", re.I),
    re.compile(r"\bthis is too (hard|difficult)\b", re.I),
]


def check_demotion_language(text: str) -> str:
    """Replace `text` if it would tell a learner they have been moved down."""
    for pattern in _DEMOTION_PATTERNS:
        if pattern.search(text):
            return DEMOTION_REDIRECT
    return text


def check_output(text: str) -> str:
    """Gate every spoken response: content guardrails, then demotion language.

    Both run here rather than in the agents, so a new agent cannot forget
    one — see `orchestrator.Orchestrator.handle_utterance`, which is the
    single place a response reaches the learner.
    """
    for pattern in _GUARDRAIL_PATTERNS:
        if pattern.search(text):
            return SAFE_REDIRECT
    return check_demotion_language(text)
