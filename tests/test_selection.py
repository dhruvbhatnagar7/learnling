"""Hard rule 2, plus the intersection that selection is supposed to be.

  2. A learner is never served a passage whose content_tier is below their
     age tier. Above is allowed, with scaffolding; below is never allowed.
"""

from __future__ import annotations

from learnling.corpus import load_corpus
from learnling.models import ContentTier, LearnerProfile, Passage, content_tier_rank
from learnling.selection import eligible_passages, select_passage


def _passage(
    id: str,
    stage: str = "2",
    tier: ContentTier = ContentTier.EARLY,
    prompts: dict | None = None,
) -> Passage:
    return Passage(
        id=id,
        text="text",
        patterns=["sh"],
        foundational_stage=stage,  # type: ignore[arg-type]
        content_tier=tier,
        wcpm_target_grade=1,
        comprehension_prompts=prompts or {},
    )


# --- Hard rule 2 ------------------------------------------------------------


def test_never_serves_material_below_the_learners_content_tier():
    """The rule this whole feature exists to guarantee, over the real corpus."""
    for age in range(4, 19):
        profile = LearnerProfile(age_years=age, foundational_stage="1a")
        floor = content_tier_rank(profile.content_tier)
        for passage in eligible_passages(profile):
            assert content_tier_rank(passage.content_tier) >= floor


def test_older_learner_at_the_earliest_stage_is_never_given_early_material():
    """The central case: a 13-year-old on stage 1a still gets upper-tier text.

    The corpus deliberately contains an easier, closer stage match at the
    early tier — the selector must refuse it despite the better skill fit.
    """
    profile = LearnerProfile(age_years=13, foundational_stage="1a")
    selection = select_passage(profile)
    assert selection is not None
    assert selection.passage.content_tier is ContentTier.UPPER


def test_the_closer_skill_match_does_not_override_the_tier_floor():
    corpus = [
        _passage("exact_but_early", stage="1a", tier=ContentTier.EARLY),
        _passage("further_but_upper", stage="3", tier=ContentTier.UPPER),
    ]
    profile = LearnerProfile(age_years=14, foundational_stage="1a")
    selection = select_passage(profile, corpus=corpus)
    assert selection is not None
    assert selection.passage.id == "further_but_upper"


def test_serving_above_the_tier_is_allowed_and_flagged():
    corpus = [_passage("only_upper", stage="2", tier=ContentTier.UPPER)]
    profile = LearnerProfile(age_years=5, foundational_stage="2")
    selection = select_passage(profile, corpus=corpus)
    assert selection is not None
    assert selection.needs_scaffolding is True


def test_an_exact_tier_match_is_preferred_over_one_above():
    corpus = [
        _passage("above", stage="2", tier=ContentTier.UPPER),
        _passage("exact", stage="2", tier=ContentTier.MIDDLE),
    ]
    profile = LearnerProfile(age_years=9, foundational_stage="2")
    selection = select_passage(profile, corpus=corpus)
    assert selection is not None
    assert selection.passage.id == "exact"
    assert selection.needs_scaffolding is False


def test_returns_none_when_nothing_is_eligible():
    corpus = [_passage("early_only", tier=ContentTier.EARLY)]
    profile = LearnerProfile(age_years=15)
    assert select_passage(profile, corpus=corpus) is None


# --- The intersection -------------------------------------------------------


def test_skill_stage_picks_the_patterns():
    profile = LearnerProfile(age_years=13, foundational_stage="3")
    selection = select_passage(profile)
    assert selection is not None
    assert selection.passage.foundational_stage == "3"


def test_same_age_different_skill_gets_different_text_at_the_same_tier():
    """Skill moves the patterns; the tier stays put. That is the whole model."""
    younger_skill = select_passage(
        LearnerProfile(age_years=13, foundational_stage="1c")
    )
    older_skill = select_passage(LearnerProfile(age_years=13, foundational_stage="3"))
    assert younger_skill is not None and older_skill is not None
    assert younger_skill.passage.id != older_skill.passage.id
    assert younger_skill.passage.content_tier == older_skill.passage.content_tier


def test_same_skill_different_age_gets_the_same_patterns_at_different_tiers():
    corpus = [
        _passage("early_2", stage="2", tier=ContentTier.EARLY),
        _passage("upper_2", stage="2", tier=ContentTier.UPPER),
    ]
    child = select_passage(LearnerProfile(age_years=5, foundational_stage="2"), corpus)
    teen = select_passage(LearnerProfile(age_years=14, foundational_stage="2"), corpus)
    assert child is not None and teen is not None
    assert child.passage.foundational_stage == teen.passage.foundational_stage == "2"
    assert child.passage.content_tier is ContentTier.EARLY
    assert teen.passage.content_tier is ContentTier.UPPER


def test_comprehension_prompts_come_from_the_comprehension_track():
    """A learner decoding at 1c but comprehending at 5 gets the stage-5 prompt."""
    corpus = [
        _passage(
            "p",
            stage="1c",
            tier=ContentTier.UPPER,
            prompts={"1c": ["easy one"], "5": ["harder one"]},
        )
    ]
    profile = LearnerProfile(
        age_years=13, foundational_stage="1c", comprehension_stage="5"
    )
    selection = select_passage(profile, corpus=corpus)
    assert selection is not None
    assert selection.comprehension_prompts == ["harder one"]


def test_prompts_fall_back_downward_never_upward():
    corpus = [
        _passage(
            "p",
            stage="1c",
            tier=ContentTier.UPPER,
            prompts={"1c": ["easy one"], "5": ["harder one"]},
        )
    ]
    profile = LearnerProfile(
        age_years=13, foundational_stage="1c", comprehension_stage="3"
    )
    selection = select_passage(profile, corpus=corpus)
    assert selection is not None
    assert selection.comprehension_prompts == ["easy one"]


def test_excluded_ids_are_not_reselected():
    """Supports unpractised sampling: don't hand back what was just read."""
    profile = LearnerProfile(age_years=13, foundational_stage="3")
    first = select_passage(profile)
    assert first is not None
    second = select_passage(profile, exclude_ids=[first.passage.id])
    assert second is None or second.passage.id != first.passage.id


def test_selection_is_deterministic():
    profile = LearnerProfile(age_years=13, foundational_stage="2")
    ids = {select_passage(profile).passage.id for _ in range(5)}  # type: ignore[union-attr]
    assert len(ids) == 1


def test_every_shipped_passage_is_selectable_by_someone():
    """Guards against a corpus entry no learner profile can ever reach."""
    reachable = set()
    for age in range(4, 19):
        for stage in ("1a", "1b", "1c", "2", "3", "4", "5", "6"):
            selection = select_passage(
                LearnerProfile(age_years=age, foundational_stage=stage)  # type: ignore[arg-type]
            )
            if selection is not None:
                reachable.add(selection.passage.id)
    assert reachable == {p.id for p in load_corpus()}
