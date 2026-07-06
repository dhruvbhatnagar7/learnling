"""Routes utterances to the right specialist agent and owns session state.

v0 routing is deliberately plain rule-based logic, not a model making a
judgment call:

  1. If a reading passage is active, the Reading Agent always handles it.
  2. Otherwise the Learning Agent handles it — as a bounded Q&A answer if
     the utterance looks like a question, or a gentle clarifying prompt
     if it doesn't.

Agents are a registered list (`self.agents`), each satisfying the `Agent`
protocol in `agents/base.py`. Adding a new application means writing a new
agent and appending it to that list — nothing here needs to change.
"""

from __future__ import annotations

from learnling.agents.base import Agent
from learnling.agents.learning import LearningAgent
from learnling.agents.reading import ReadingAgent
from learnling.adaptation import shape
from learnling.models import ChildProfile, Session, Utterance
from learnling.safety import check_output


class Orchestrator:
    def __init__(self, profile: ChildProfile, agents: list[Agent] | None = None):
        self.session = Session(profile=profile)
        self.agents = agents if agents is not None else [ReadingAgent(), LearningAgent()]
        self.passage_text: str | None = None

    def load_passage(self, passage_text: str) -> None:
        self.passage_text = passage_text

    def clear_passage(self) -> None:
        self.passage_text = None

    def _route(self, utterance: Utterance, context: dict) -> Agent:
        for agent in self.agents:
            if agent.can_handle(utterance, context):
                return agent
        raise RuntimeError("no agent could handle the utterance")

    def handle_utterance(self, utterance: Utterance) -> str:
        context = {"profile": self.session.profile, "passage_text": self.passage_text}
        agent = self._route(utterance, context)
        response = agent.handle(utterance, context)

        safe_text = check_output(response.spoken_text)
        shaped_text = shape(safe_text, self.session.profile.age_band)

        self.session.log(
            {
                "agent": agent.name,
                "utterance": utterance.text,
                "response": shaped_text,
                "report_notes": response.report_notes,
            }
        )
        return shaped_text
