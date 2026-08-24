"""Hard rule 1: content_tier never derives from any skill field.

This is the rule the whole skill/content split exists to protect. If it ever
breaks, an older student working on early phonics starts being handed material
written for a six-year-old, concludes the tool thinks they are a baby, and
stops using it. That failure is silent — nothing crashes, the learner just
disengages — so it is pinned down here from three directions:

  1. behaviourally, across every combination of the two skill tracks;
  2. structurally, via the signature of the derivation function;
  3. by construction, since `content_tier` is a read-only property.
"""

from __future__ import annotations

import inspect
from itertools import product

import pytest

from learnling.models import (
    SKILL_STAGES,
    ContentTier,
    LearnerProfile,
    content_tier_for,
)

# Ages spanning every tier boundary, including both sides of each cut.
AGES = list(range(4, 19))


def test_content_tier_is_identical_across_every_skill_combination():
    """The exhaustive form of the rule: skill cannot move content, at any age.

    For each age, sweep both skill tracks over their full range. Every
    resulting content_tier must equal the tier derived from age alone.
    """
    for age in AGES:
        expected = content_tier_for(age)
        for foundational, comprehension in product(SKILL_STAGES, SKILL_STAGES):
            profile = LearnerProfile(
                age_years=age,
                foundational_stage=foundational,
                comprehension_stage=comprehension,
            )
            assert profile.content_tier == expected, (
                f"age {age} with foundational={foundational} "
                f"comprehension={comprehension} produced {profile.content_tier}, "
                f"expected {expected} — skill leaked into the content axis"
            )


def test_the_central_case_older_learner_with_a_decoding_gap():
    """A 12-year-old at the earliest foundational stage still reads upper-tier.

    This exact learner is the reason the two axes exist. Spelled out as its
    own test so the intent survives a future refactor of the sweep above.
    """
    profile = LearnerProfile(
        age_years=12,
        foundational_stage="1a",
        comprehension_stage="5",
    )
    assert profile.content_tier is ContentTier.UPPER


def test_lowest_skill_and_highest_skill_agree_at_the_same_age():
    """A direct A/B: same age, opposite ends of both skill scales."""
    struggling = LearnerProfile(
        age_years=13, foundational_stage="1a", comprehension_stage="1a"
    )
    advanced = LearnerProfile(
        age_years=13, foundational_stage="6", comprehension_stage="6"
    )
    assert struggling.content_tier == advanced.content_tier


def test_content_tier_for_accepts_age_and_nothing_else():
    """Structural guard: the derivation cannot even see a skill value.

    A future change that wanted to consult skill would have to widen this
    signature, which is a visible, reviewable diff rather than a quiet one.
    """
    params = list(inspect.signature(content_tier_for).parameters)
    assert params == ["age_years"]


def test_content_tier_cannot_be_assigned_on_a_profile():
    """By construction: there is no writable field to contaminate."""
    profile = LearnerProfile(age_years=9, foundational_stage="2")
    with pytest.raises(AttributeError):
        profile.content_tier = ContentTier.EARLY  # type: ignore[misc]


@pytest.mark.parametrize(
    "age,expected",
    [
        (4, ContentTier.EARLY),
        (7, ContentTier.EARLY),
        (8, ContentTier.MIDDLE),
        (11, ContentTier.MIDDLE),
        (12, ContentTier.UPPER),
        (17, ContentTier.UPPER),
    ],
)
def test_tier_boundaries(age: int, expected: ContentTier):
    """Both sides of each boundary, so an off-by-one can't slip through."""
    assert content_tier_for(age) is expected


def test_educator_override_is_honoured():
    """An adult may override the age default; nothing automatic may."""
    profile = LearnerProfile(age_years=6, content_tier_override=ContentTier.MIDDLE)
    assert profile.content_tier is ContentTier.MIDDLE


def test_override_is_independent_of_skill_too():
    """An override is an educator's judgment, not a skill readout."""
    for foundational in SKILL_STAGES:
        profile = LearnerProfile(
            age_years=6,
            foundational_stage=foundational,
            content_tier_override=ContentTier.UPPER,
        )
        assert profile.content_tier is ContentTier.UPPER


def test_skill_tracks_are_independent_of_each_other():
    """The two skill tracks may sit at different stages; neither implies the other."""
    profile = LearnerProfile(
        age_years=10, foundational_stage="2", comprehension_stage="5"
    )
    assert profile.foundational_stage == "2"
    assert profile.comprehension_stage == "5"


def test_age_band_and_content_tier_are_separate_axes():
    """`age_band` shapes how the agent speaks; `content_tier` what it serves.

    They partition age differently on purpose, so this guards against a
    future refactor collapsing one into the other.
    """
    profile = LearnerProfile(age_years=8)
    assert profile.age_band == "7-8"
    assert profile.content_tier is ContentTier.MIDDLE
