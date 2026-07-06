"""The specialist-agent contract.

Adding a new application to learnling means writing a class that satisfies
this protocol and registering it with the orchestrator — nothing about the
orchestrator, ASR layer, or horizontals needs to change.
"""

from __future__ import annotations

from typing import Protocol

from learnling.models import AgentResponse, Utterance


class Agent(Protocol):
    name: str

    def can_handle(self, utterance: Utterance, context: dict) -> bool:
        """Whether this agent should handle the utterance given session context."""
        ...

    def handle(self, utterance: Utterance, context: dict) -> AgentResponse:
        """Produce a response. `spoken_text` is pre-adaptation, pre-safety-check."""
        ...
