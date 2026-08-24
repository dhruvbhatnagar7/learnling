"""When to add support, and when — rarely, slowly — to move a skill stage.

Two rules govern every decision here, and both exist to protect the learner
from the tool's own eagerness.

**Support before step-back.** When a learner struggles, the first response is
always more scaffolding at the stage they are already on: more explicit
instruction, then smaller steps, then more repetitions. Only when that ladder
is exhausted does anything step back, and then only the specific sub-skill
that is failing — never the whole track. A learner who is shaky on digraphs
does not get demoted out of the stage they are otherwise succeeding at.

**No permanent change from a single session.** A stage change requires a
consistent pattern across `MIN_SESSIONS_FOR_STAGE_CHANGE` separate sessions.
Fatigue, mood, an unfamiliar topic, a bad night's sleep and a noisy room all
look exactly like a skill gap in a single sitting. Acting on one session
means repeatedly moving learners on noise.

Note on the second rule: learnling keeps no cross-session store by design
(see `safety.py`), so callers today cannot supply the session history that
`should_change_stage` requires, and it correctly refuses every stage change.
That is the intended conservative default rather than an oversight — the
function is the seam a future opt-in store would plug into, and the rule is
specified and tested now so it cannot be quietly skipped when that lands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from learnling.models import SKILL_STAGES, SkillStage, skill_stage_rank

#: Sessions of consistent evidence required before any stage moves.
MIN_SESSIONS_FOR_STAGE_CHANGE = 3

#: Scaffolding escalates in this order, all at the learner's current stage.
SCAFFOLD_LADDER: tuple[str, ...] = (
    "more_explicit_instruction",
    "smaller_steps",
    "more_repetitions",
)

SupportAction = Literal["scaffold", "step_back_sub_skill"]

#: What the learner hears at each rung. Every line names the *skill* being
#: practised. None of them refer to difficulty, level, grade or going back —
#: see `safety.check_output`, which enforces that independently.
_SCAFFOLD_MESSAGES: dict[str, str] = {
    "more_explicit_instruction": "Let's take this one apart together. I'll show you the first step.",
    "smaller_steps": "Let's do this in smaller pieces — one sound at a time.",
    "more_repetitions": "Let's practise this one a few more times until it feels easy.",
}

_STEP_BACK_MESSAGE = "Let's practise breaking big words apart."


@dataclass
class SupportState:
    """How much scaffolding a learner has already been given at this stage.

    Session-scoped, like everything else that touches learner state.
    """

    stage: SkillStage
    rung: int = 0

    @property
    def ladder_exhausted(self) -> bool:
        return self.rung >= len(SCAFFOLD_LADDER)


@dataclass
class SupportDecision:
    action: SupportAction
    #: The stage the learner stays on. Scaffolding never changes it, and a
    #: sub-skill step-back does not change the track's stage either.
    stage: SkillStage
    scaffold_level: str | None = None
    #: Named only for a step-back, and always a single sub-skill.
    sub_skill: str | None = None
    learner_message: str = ""


def next_support(state: SupportState, sub_skill: str) -> SupportDecision:
    """Decide the response to a struggle, and advance `state`.

    Climbs the scaffolding ladder at the current stage first. Only once every
    rung has been used does it step `sub_skill` back — and even then the
    learner's stage is returned unchanged, because the track does not move.
    """
    if not state.ladder_exhausted:
        level = SCAFFOLD_LADDER[state.rung]
        state.rung += 1
        return SupportDecision(
            action="scaffold",
            stage=state.stage,
            scaffold_level=level,
            learner_message=_SCAFFOLD_MESSAGES[level],
        )

    return SupportDecision(
        action="step_back_sub_skill",
        stage=state.stage,
        sub_skill=sub_skill,
        learner_message=_STEP_BACK_MESSAGE,
    )


@dataclass
class SessionObservation:
    """One session's worth of evidence about one skill track.

    `session_id` is what makes "3 separate sessions" checkable; three
    observations logged inside a single sitting are one session's evidence,
    not three, and are counted as such.
    """

    session_id: str
    struggled: bool
    track: str = "foundational"


@dataclass
class StageChangeDecision:
    should_change: bool
    reason: str
    new_stage: SkillStage | None = None
    sessions_of_evidence: int = 0


def should_change_stage(
    current_stage: SkillStage,
    observations: list[SessionObservation],
) -> StageChangeDecision:
    """Whether `current_stage` may move, given session history.

    Requires `MIN_SESSIONS_FOR_STAGE_CHANGE` *distinct* sessions all pointing
    the same way. Mixed evidence is not a pattern — it is a learner having a
    normal week — and returns no change.
    """
    by_session: dict[str, bool] = {}
    for observation in observations:
        # Within one session, any struggle counts as that session struggling.
        by_session[observation.session_id] = (
            by_session.get(observation.session_id, False) or observation.struggled
        )

    sessions = len(by_session)
    if sessions < MIN_SESSIONS_FOR_STAGE_CHANGE:
        return StageChangeDecision(
            should_change=False,
            reason=(
                f"{sessions} session(s) of evidence; "
                f"{MIN_SESSIONS_FOR_STAGE_CHANGE} required before a stage moves"
            ),
            sessions_of_evidence=sessions,
        )

    verdicts = set(by_session.values())
    if len(verdicts) > 1:
        return StageChangeDecision(
            should_change=False,
            reason="evidence is not consistent across sessions",
            sessions_of_evidence=sessions,
        )

    struggled = verdicts.pop()
    index = skill_stage_rank(current_stage)
    target = index - 1 if struggled else index + 1

    if not 0 <= target < len(SKILL_STAGES):
        return StageChangeDecision(
            should_change=False,
            reason="already at the end of the skill scale",
            sessions_of_evidence=sessions,
        )

    direction = "back" if struggled else "on"
    return StageChangeDecision(
        should_change=True,
        reason=f"consistent evidence across {sessions} sessions supports moving {direction}",
        new_stage=SKILL_STAGES[target],
        sessions_of_evidence=sessions,
    )
