"""Core data contracts shared by every layer of learnling.

These are plain stdlib dataclasses on purpose: the whole core package stays
dependency-free, so the models double as the contract between optional
pieces (ASR adapters, LLM-backed agents) and the rule-based core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

MiscueKind = Literal["substitution", "omission", "insertion"]
Assessment = Literal["decoding", "fluency", "comprehension", "clean"]

SkillStage = Literal["1a", "1b", "1c", "2", "3", "4", "5", "6"]

#: The skill scale in order, so stages can be compared without inventing a
#: numeric encoding that would imply a spurious equal spacing between them.
SKILL_STAGES: tuple[SkillStage, ...] = ("1a", "1b", "1c", "2", "3", "4", "5", "6")


def skill_stage_rank(stage: SkillStage) -> int:
    """Position of `stage` on the skill scale, for ordering comparisons only."""
    return SKILL_STAGES.index(stage)


class ContentTier(str, Enum):
    """How material is delivered — themes, topics and lexicon.

    This is the *content* axis. It is a pure function of the learner's age
    and is never derived from any measure of skill: an eleven-year-old
    working on consonant digraphs needs digraph practice written about
    something an eleven-year-old cares about, not "the cat sat on the mat".
    """

    EARLY = "early"  # ages 4-7:  animals, family, school, play
    MIDDLE = "middle"  # ages 8-11: adventure, mystery, sports, science, humor
    UPPER = "upper"  # ages 12+:  real-world topics, technology, social dynamics


#: Tiers from youngest to oldest, so "below the learner's tier" is well defined.
CONTENT_TIERS: tuple[ContentTier, ...] = (
    ContentTier.EARLY,
    ContentTier.MIDDLE,
    ContentTier.UPPER,
)


def content_tier_rank(tier: ContentTier) -> int:
    """Position of `tier` on the content scale, for ordering comparisons."""
    return CONTENT_TIERS.index(tier)


def content_tier_for(age_years: int) -> ContentTier:
    """Map an age in years to a content tier.

    Takes an age and nothing else, deliberately. Keeping this a free function
    over a single int — rather than a method that could reach for `self` —
    is what makes it structurally impossible for content selection to be
    contaminated by a learner's skill stage.
    """
    if age_years <= 7:
        return ContentTier.EARLY
    if age_years <= 11:
        return ContentTier.MIDDLE
    return ContentTier.UPPER


def age_band_for(age_years: int) -> str:
    """Map a child's age in years to a developmental response band.

    Distinct from `content_tier_for`: this band governs how the agent *speaks*
    (sentence length, vocabulary — see `adaptation.py`), while the content tier
    governs what the learner is asked to *read*.
    """
    if age_years <= 6:
        return "4-6"
    if age_years <= 8:
        return "7-8"
    if age_years <= 10:
        return "9-10"
    return "11+"


@dataclass
class LearnerProfile:
    """Who the learner is, across two independent axes.

    Skill and content are tracked separately and must stay that way. The
    central case this design exists for is a learner who is
    `foundational_stage="2"`, `comprehension_stage="5"`, `content_tier=UPPER`:
    an older student with a decoding gap and strong comprehension. That is
    the normal case, not an edge case.

    The two skill tracks are themselves independent — a learner may sit at
    different stages on each, and neither one implies the other.

    `learner_id` defaults to a placeholder because learnling keeps no
    cross-session store (see `safety.py`); it is only meaningful when an
    educator supplies one for their own record-keeping.
    """

    age_years: int
    learner_id: str = "anonymous"
    foundational_stage: SkillStage = "1a"
    comprehension_stage: SkillStage = "1a"
    #: An educator may override the age-derived tier (a mature 11-year-old
    #: reading upper-tier material, say). Nothing *automatic* may set this.
    content_tier_override: ContentTier | None = None

    @property
    def content_tier(self) -> ContentTier:
        """The learner's content tier: from age, or an educator's override.

        Implemented as a property over `content_tier_for(self.age_years)` so
        there is no writable field a later change could quietly start setting
        from a skill measurement.
        """
        if self.content_tier_override is not None:
            return self.content_tier_override
        return content_tier_for(self.age_years)

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
class Passage:
    """One piece of reading material, tagged on both axes at once.

    Every passage carries a skill tag (`patterns`, `foundational_stage`) and
    a content tag (`content_tier`) independently, which is what lets the same
    phonics pattern set exist at three different maturity levels.

    `wcpm_target_grade` is the grade level of the *material*, used to pick the
    right column of the fluency norms. It is not the reader's grade and must
    never be shown to the learner.
    """

    id: str
    text: str
    patterns: list[str]
    foundational_stage: SkillStage
    content_tier: ContentTier
    wcpm_target_grade: int
    #: Prompts keyed by the comprehension stage they suit, so a learner's
    #: comprehension track can be served independently of their decoding one.
    comprehension_prompts: dict[str, list[str]] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


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

    profile: LearnerProfile
    events: list = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def log(self, event: dict) -> None:
        self.events.append(event)
