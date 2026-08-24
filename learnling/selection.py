"""Choosing what a learner reads next.

Selection is an intersection, not a lookup. Three things are decided by three
different properties of the learner, and none of them may stand in for another:

    decodable pattern set   <- foundational_stage
    theme, topic, lexicon   <- content_tier   (which comes from age)
    comprehension prompts   <- comprehension_stage

The one inviolable constraint is that a learner is never handed material
written for someone younger than they are. Serving *above* their tier is fine
and happens routinely — an interesting text with support around it is a good
day's teaching. Serving below is never fine, because it tells the learner what
the tool thinks of them, and they are right to stop using it after that.

`select_passage` returns a `PassageSelection` rather than a bare `Passage`
because the prompts travel with the choice: they are picked off the learner's
comprehension track, which is independent of the decoding track that picked
the text itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from learnling.corpus import load_corpus
from learnling.models import (
    LearnerProfile,
    Passage,
    SkillStage,
    content_tier_rank,
    skill_stage_rank,
)


@dataclass
class PassageSelection:
    passage: Passage
    #: Prompts drawn from the learner's comprehension stage, which may sit
    #: well above or below the stage that chose the passage.
    comprehension_prompts: list[str] = field(default_factory=list)
    #: True when the text sits above the learner's content tier. Allowed, but
    #: the caller should scaffold rather than pretend it is a level match.
    needs_scaffolding: bool = False


def _prompts_for(passage: Passage, comprehension_stage: SkillStage) -> list[str]:
    """Prompts at the learner's comprehension stage, or the nearest below it.

    Falling back downward rather than upward is deliberate: an easier question
    about a text the learner has just read is a fair question. A harder one is
    a second obstacle stacked on the first.
    """
    available = passage.comprehension_prompts
    if not available:
        return []

    target = skill_stage_rank(comprehension_stage)
    at_or_below = [
        stage for stage in available if skill_stage_rank(stage) <= target  # type: ignore[arg-type]
    ]
    if at_or_below:
        best = max(at_or_below, key=skill_stage_rank)  # type: ignore[arg-type]
        return list(available[best])

    lowest = min(available, key=skill_stage_rank)  # type: ignore[arg-type]
    return list(available[lowest])


def eligible_passages(
    profile: LearnerProfile,
    corpus: Sequence[Passage] | None = None,
    exclude_ids: Iterable[str] = (),
) -> list[Passage]:
    """Every passage this learner may be served, hard rule 2 already applied."""
    passages = load_corpus() if corpus is None else corpus
    excluded = set(exclude_ids)
    floor = content_tier_rank(profile.content_tier)

    return [
        passage
        for passage in passages
        if passage.id not in excluded
        and content_tier_rank(passage.content_tier) >= floor
    ]


def select_passage(
    profile: LearnerProfile,
    corpus: Sequence[Passage] | None = None,
    exclude_ids: Iterable[str] = (),
) -> PassageSelection | None:
    """Pick the best passage for `profile`, or None if the corpus has nothing.

    Among passages the learner is allowed to see, prefer the closest match on
    the decoding stage first — that is what makes the text practisable — and
    only then the closest content tier, preferring an exact tier over one
    above it. Ties break on id so selection is deterministic and testable.

    `exclude_ids` lets a caller ask for something the learner has not just
    read, which matters for fluency sampling: a re-read is a practised
    reading, and the norms assume unpractised ones.
    """
    candidates = eligible_passages(profile, corpus=corpus, exclude_ids=exclude_ids)
    if not candidates:
        return None

    learner_stage = skill_stage_rank(profile.foundational_stage)
    learner_tier = content_tier_rank(profile.content_tier)

    def rank(passage: Passage) -> tuple[int, int, str]:
        return (
            abs(skill_stage_rank(passage.foundational_stage) - learner_stage),
            content_tier_rank(passage.content_tier) - learner_tier,
            passage.id,
        )

    best = min(candidates, key=rank)
    return PassageSelection(
        passage=best,
        comprehension_prompts=_prompts_for(best, profile.comprehension_stage),
        needs_scaffolding=content_tier_rank(best.content_tier) > learner_tier,
    )
