"""Hard rules 3, 4 and 5: how support escalates and when a stage may move.

  3. No demotion language reaches the learner.
  4. Struggle earns more scaffolding at the current stage first; only when
     that is exhausted does a single sub-skill step back, never the track.
  5. No permanent stage change from a single session.
"""

from __future__ import annotations

import pytest

from learnling.progression import (
    MIN_SESSIONS_FOR_STAGE_CHANGE,
    SCAFFOLD_LADDER,
    SessionObservation,
    SupportState,
    next_support,
    should_change_stage,
)
from learnling.safety import DEMOTION_REDIRECT, check_output

# --- Hard rule 4: scaffold before step-back ---------------------------------


def test_first_response_to_struggle_is_scaffolding_not_a_step_back():
    state = SupportState(stage="2")
    decision = next_support(state, sub_skill="digraphs")
    assert decision.action == "scaffold"
    assert decision.sub_skill is None


def test_scaffolding_climbs_the_whole_ladder_before_stepping_back():
    state = SupportState(stage="2")
    levels = [next_support(state, "digraphs").scaffold_level for _ in SCAFFOLD_LADDER]
    assert levels == list(SCAFFOLD_LADDER)
    # only now, with every rung used, may anything step back
    assert next_support(state, "digraphs").action == "step_back_sub_skill"


def test_scaffolding_never_changes_the_learners_stage():
    state = SupportState(stage="3")
    for _ in range(len(SCAFFOLD_LADDER) + 2):
        assert next_support(state, "digraphs").stage == "3"


def test_step_back_names_one_sub_skill_and_leaves_the_track_alone():
    state = SupportState(stage="3", rung=len(SCAFFOLD_LADDER))
    decision = next_support(state, sub_skill="digraphs")
    assert decision.action == "step_back_sub_skill"
    assert decision.sub_skill == "digraphs"
    # the track's stage is untouched: the sub-skill stepped back, not the learner
    assert decision.stage == "3"


# --- Hard rule 3: no demotion language --------------------------------------


def test_every_scaffold_message_survives_the_safety_gate():
    """The lines learners actually hear must not themselves trip rule 3."""
    state = SupportState(stage="2")
    for _ in range(len(SCAFFOLD_LADDER) + 1):
        message = next_support(state, "digraphs").learner_message
        assert check_output(message) == message, f"demotion language in: {message!r}"


@pytest.mark.parametrize(
    "text",
    [
        "This is too hard for you.",
        "Let's go back to an easier book.",
        "You're not ready for this one.",
        "Let's try a simpler passage.",
        "This is first-grade reading.",
        "That's a grade 2 word.",
        "This story is for younger kids.",
        "Let's go back a level.",
    ],
)
def test_demotion_language_never_reaches_the_learner(text: str):
    assert check_output(text) == DEMOTION_REDIRECT


@pytest.mark.parametrize(
    "text",
    [
        "Try that line again and see if you can catch it.",
        "Let's read that part again, nice and slow.",
        "Nice reading! Let's look at one word again.",
        "Let's practise breaking big words apart.",
        "Let's do this in smaller pieces — one sound at a time.",
        "Beautiful! Every word matched. Want to try a trickier one?",
    ],
)
def test_ordinary_reading_instructions_pass_through_untouched(text: str):
    """Rule 3 must not swallow normal coaching — re-reading is not demotion."""
    assert check_output(text) == text


# --- Hard rule 5: no stage change from one session --------------------------


def test_a_single_session_never_moves_a_stage():
    observations = [SessionObservation(session_id="s1", struggled=True)]
    decision = should_change_stage("2", observations)
    assert decision.should_change is False
    assert decision.new_stage is None


def test_repeated_struggles_inside_one_session_are_still_one_session():
    """Three bad attempts in a sitting are one session's evidence, not three."""
    observations = [
        SessionObservation(session_id="s1", struggled=True) for _ in range(5)
    ]
    decision = should_change_stage("2", observations)
    assert decision.should_change is False
    assert decision.sessions_of_evidence == 1


def test_stage_moves_only_after_enough_consistent_sessions():
    observations = [
        SessionObservation(session_id=f"s{i}", struggled=True)
        for i in range(MIN_SESSIONS_FOR_STAGE_CHANGE)
    ]
    decision = should_change_stage("2", observations)
    assert decision.should_change is True
    assert decision.new_stage == "1c"


def test_inconsistent_evidence_is_not_a_pattern():
    """A learner having a mixed week is not a learner who changed stage."""
    observations = [
        SessionObservation(session_id="s1", struggled=True),
        SessionObservation(session_id="s2", struggled=False),
        SessionObservation(session_id="s3", struggled=True),
    ]
    decision = should_change_stage("2", observations)
    assert decision.should_change is False


def test_consistent_success_moves_the_stage_forward():
    observations = [
        SessionObservation(session_id=f"s{i}", struggled=False)
        for i in range(MIN_SESSIONS_FOR_STAGE_CHANGE)
    ]
    decision = should_change_stage("2", observations)
    assert decision.should_change is True
    assert decision.new_stage == "3"


def test_no_change_past_either_end_of_the_scale():
    struggling = [
        SessionObservation(session_id=f"s{i}", struggled=True)
        for i in range(MIN_SESSIONS_FOR_STAGE_CHANGE)
    ]
    assert should_change_stage("1a", struggling).should_change is False

    thriving = [
        SessionObservation(session_id=f"s{i}", struggled=False)
        for i in range(MIN_SESSIONS_FOR_STAGE_CHANGE)
    ]
    assert should_change_stage("6", thriving).should_change is False


def test_no_history_means_no_change():
    """The current no-store default: nothing to go on, so nothing moves."""
    assert should_change_stage("2", []).should_change is False
