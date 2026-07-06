"""The Learning/Q&A Agent: bounded, age-appropriate answers to questions.

Without an LLM configured this agent is honest about what it can't do: it
acknowledges the question and hands the thinking back to the child (and a
grown-up) rather than pretending to have answers it can't safely generate.
With the `llm` extra and an API key, it asks Claude for a short, scaffolded
answer instead.
"""

from __future__ import annotations

import os

from learnling.models import AgentResponse, Utterance

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised only without the extra
    anthropic = None

_QUESTION_WORDS = (
    "what",
    "why",
    "how",
    "who",
    "when",
    "where",
    "which",
    "can",
    "could",
    "would",
    "is",
    "are",
    "do",
    "does",
)
_LEADING_WORDS = _QUESTION_WORDS + ("is", "are", "do", "does", "can", "could", "would")


def is_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return True
    first_word = stripped.split()[0].lower()
    return first_word in _QUESTION_WORDS


def _topic_phrase(question: str) -> str:
    words = question.strip().rstrip("?").split()
    if words and words[0].lower() in _QUESTION_WORDS:
        words = words[1:]
    if words and words[0].lower() in ("is", "are", "do", "does", "can", "could", "would"):
        words = words[1:]
    return " ".join(words) if words else "that"


def _llm_enabled() -> bool:
    return os.environ.get("LEARNLING_LLM") == "1" and bool(os.environ.get("ANTHROPIC_API_KEY"))


class LearningAgent:
    name = "learning"

    def can_handle(self, utterance: Utterance, context: dict) -> bool:
        # Catch-all: the orchestrator only reaches this agent when no other
        # (more specific) agent claimed the utterance.
        return True

    def handle(self, utterance: Utterance, context: dict) -> AgentResponse:
        profile = context.get("profile")
        age_band = profile.age_band if profile else "7-8"

        if _llm_enabled() and anthropic is not None:
            try:
                text = self._ask_llm(utterance.text, age_band)
                return AgentResponse(self.name, text, {"mode": "llm"})
            except Exception:
                pass  # any API/network failure falls back to offline behavior

        if is_question(utterance.text):
            topic = _topic_phrase(utterance.text)
            text = (
                f"Great question! Let's think about it together — what do YOU notice "
                f"about {topic}? Ask a grown-up too if you want to dig in more."
            )
        else:
            text = "Hmm, I'm not sure what you're asking! Try asking me a question, like 'why...' or 'how...'."

        return AgentResponse(self.name, text, {"mode": "offline"})

    def _ask_llm(self, question: str, age_band: str) -> str:
        model = os.environ.get("LEARNLING_MODEL", "claude-opus-4-8")
        client = anthropic.Anthropic()
        system = (
            f"You are a warm learning companion for a child in the {age_band} age band. "
            "Reply in 3 short sentences or fewer, in simple words for that age. "
            "Scaffold, don't solve: guide the child to notice or figure things out "
            "themselves rather than just stating the answer. Never discuss violent, "
            "adult, or otherwise unsafe topics, and never ask for personal information "
            "— if asked about any of that, gently redirect to a safe, age-appropriate "
            "topic instead."
        )
        response = client.messages.create(
            model=model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
        return "".join(block.text for block in response.content if hasattr(block, "text")).strip()
