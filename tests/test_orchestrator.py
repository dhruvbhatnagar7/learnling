from learnling.models import AgentResponse, LearnerProfile, Utterance
from learnling.orchestrator import Orchestrator
from learnling.safety import SAFE_REDIRECT


class _AlwaysUnsafeAgent:
    """Test double: always claims the utterance and returns unsafe text,
    so we can verify the safety layer runs regardless of which agent answered."""

    name = "unsafe"

    def can_handle(self, utterance, context):
        return True

    def handle(self, utterance, context):
        return AgentResponse(agent_name=self.name, spoken_text="go get a gun", report_notes={})


def test_routes_to_reading_agent_when_passage_active():
    orchestrator = Orchestrator(LearnerProfile(age_years=7))
    orchestrator.load_passage("the cat sat on the mat")
    orchestrator.handle_utterance(Utterance(text="the cat sat on the mat"))
    assert orchestrator.session.events[-1]["agent"] == "reading"


def test_routes_to_learning_agent_for_a_question_with_no_passage():
    orchestrator = Orchestrator(LearnerProfile(age_years=7))
    orchestrator.handle_utterance(Utterance(text="why is the sky blue"))
    assert orchestrator.session.events[-1]["agent"] == "learning"


def test_routes_to_learning_agent_fallback_for_non_question():
    orchestrator = Orchestrator(LearnerProfile(age_years=7))
    orchestrator.handle_utterance(Utterance(text="the dog ran fast"))
    assert orchestrator.session.events[-1]["agent"] == "learning"


def test_reading_agent_wins_even_over_a_question_when_passage_active():
    orchestrator = Orchestrator(LearnerProfile(age_years=7))
    orchestrator.load_passage("the cat sat on the mat")
    orchestrator.handle_utterance(Utterance(text="why is the mat there"))
    assert orchestrator.session.events[-1]["agent"] == "reading"


def test_safety_guardrail_replaces_unsafe_output_in_the_loop():
    orchestrator = Orchestrator(LearnerProfile(age_years=7), agents=[_AlwaysUnsafeAgent()])
    response = orchestrator.handle_utterance(Utterance(text="anything"))
    assert response == SAFE_REDIRECT
