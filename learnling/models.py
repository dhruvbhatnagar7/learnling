"""Core data contracts shared by every layer of learnling.

These are plain stdlib dataclasses on purpose: the whole core package stays
dependency-free, so the models double as the contract between optional
pieces (ASR adapters, LLM-backed agents) and the rule-based core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

MiscueKind = Literal["substitution", "omission", "insertion"]
Assessment = Literal["decoding", "fluency", "comprehension", "clean"]


def age_band_for(age_years: int) -> str:
    """Map a child's age in years to a developmental response band."""
    if age_years <= 6:
        return "4-6"
    if age_years <= 8:
        return "7-8"
    return "9-10"


@dataclass
class ChildProfile:
    age_years: int
    reading_level: str | None = None

    @property
    def age_band(self) -> str:
        return age_band_for(self.age_years)


@dataclass
class Utterance:
    """The contract every ASR adapter must produce, real or simulated."""

    text: str
    confidence: float | None = None
    duration_seconds: float | None = None
    word_timestamps: list | None = None


@dataclass
class Miscue:
    kind: MiscueKind
    expected: str | None
    heard: str | None
    position: int


@dataclass
class ReadingResult:
    passage: str
    transcript: str
    miscues: list[Miscue]
    accuracy: float
    wpm: float | None
    assessment: Assessment


@dataclass
class AgentResponse:
    """An agent's raw output before the age-adaptation layer shapes it."""

    agent_name: str
    spoken_text: str
    report_notes: dict = field(default_factory=dict)


@dataclass
class Session:
    """In-memory session state.

    No transcripts or audio are persisted here by default — see safety.py.
    `events` holds report-worthy summaries (stats, not raw child speech)
    unless the caller opts into `--save-report`.
    """

    profile: ChildProfile
    events: list = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def log(self, event: dict) -> None:
        self.events.append(event)
