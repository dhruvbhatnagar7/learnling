"""The reading buddy's voice in conversation: a small language model running on the stand.

Between reads, learnling talks with the reader: it greets them, says something
about how the read went, asks a couple of questions about the story and
answers what they say. A small model running on the stand itself writes those
lines, through Ollama (https://ollama.com):

    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull gemma3:1b

The model only ever sees text: the passage, simple reading numbers, and the
words the speech recogniser heard. It never hears audio, and nothing it sees
leaves the stand. What it says passes through the same safety gate and age
shaping as every other line (`safety.check_output`, `adaptation.shape`).

Hints while the reader is reading do not come from here. They have to arrive
within seconds and must never say the word, so they stay with the rules in
`live.py`.

If the model is missing, slow to start or says something unusable, each step
falls back to a plain line so the session carries on.
"""

from __future__ import annotations

import json
import re
import urllib.request

from learnling.adaptation import shape
from learnling.models import LearnerProfile
from learnling.safety import check_output

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:1b"


class OllamaChat:
    """A chat model served by Ollama on this machine."""

    def __init__(self, model: str = DEFAULT_MODEL, url: str = OLLAMA_URL, timeout: float = 60.0):
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout

    def __call__(self, messages: list[dict], max_words: int = 40) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_predict": int(max_words * 2), "temperature": 0.7},
        }
        request = urllib.request.Request(
            f"{self.url}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())["message"]["content"]

    def warm_up(self) -> None:
        """Load the model now, so the first real line isn't slow."""
        self([{"role": "user", "content": "Say hi."}], max_words=3)


_MARKUP = re.compile(r"[*_#`~>\[\]]|[\U0001F000-\U0001FFFF☀-➿]")


def clean_for_speech(text: str, max_sentences: int = 3) -> str:
    """Plain spoken sentences: no markdown, emoji or stage directions, and not too many."""
    text = re.sub(r"\([^)]*\)", "", text)  # "(smiles)"
    text = _MARKUP.sub("", text)
    text = " ".join(text.split())
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:max_sentences]).strip().strip('"')


_QUESTION_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])?\s*(.+\?)\s*$")


def parse_questions(text: str, how_many: int = 2) -> list[str]:
    """Questions from a model's reply, one per line."""
    found = []
    for line in text.splitlines():
        match = _QUESTION_LINE.match(line)
        if match:
            found.append(clean_for_speech(match.group(1), max_sentences=1))
    return found[:how_many]


FALLBACK_QUESTIONS = ["What happened in the story?", "What was your favourite part?"]


class ReadingBuddy:
    """Writes what learnling says between reads, with a small local model."""

    def __init__(self, passage_text: str, age_years: int, chat=None):
        self.passage_text = passage_text
        self.age_years = age_years
        self.age_band = LearnerProfile(age_years=age_years).age_band
        self.chat = chat if chat is not None else OllamaChat()
        self.history: list[dict] = []

    def _system(self) -> str:
        return (
            f"You are learnling, a warm, playful reading buddy for a {self.age_years} year old child. "
            "You talk out loud through a small speaker on a book stand, so speak in one or two short "
            "sentences with simple words. No lists, no emoji, no stage directions. Never make the child "
            "feel wrong or behind. Never ask for their name, school, address or anything personal. Stay "
            "on reading and the story. What the child says reaches you through a speech recogniser, so "
            "it may have small mistakes; don't point them out.\n\n"
            f"Today's story:\n{self.passage_text}"
        )

    def say(self, instruction: str, fallback: str, max_words: int = 30) -> str:
        """One line from the model for `instruction`, or `fallback` if that fails."""
        messages = [{"role": "system", "content": self._system()}, *self.history,
                    {"role": "user", "content": instruction}]
        try:
            text = clean_for_speech(self.chat(messages, max_words=max_words))
        except Exception:
            text = ""
        if not text:
            text = fallback
        self.history += [{"role": "user", "content": instruction}, {"role": "assistant", "content": text}]
        return shape(check_output(text), self.age_band)

    def greet(self) -> str:
        return self.say(
            "The child just walked up and said they are ready to read. Greet them warmly and tell them "
            "today's story is ready on the stand. Don't tell them what happens in it.",
            "Hi there! Your story is ready on the stand.",
        )

    def after_first_read(self, words_helped: list[str], accuracy: float) -> str:
        if words_helped:
            how = f"They needed a little help with: {', '.join(words_helped)}."
        else:
            how = "They read it without needing any help."
        return self.say(
            f"The child just finished reading the story out loud for the first time. {how} About "
            f"{accuracy:.0%} of the words matched the page. Tell them one specific, honest, kind thing about "
            "their reading, then say you'll read it once more and this time think about what happens.",
            "Nice reading! Let's read it once more, and this time think about what happens.",
        )

    def questions(self, how_many: int = 2) -> list[str]:
        """Questions about the story, from the model, for the adult to approve."""
        instruction = (
            f"Write {how_many} short questions about what happens in today's story, for a "
            f"{self.age_years} year old to answer out loud. Answers must be in the story. "
            "One question per line, nothing else."
        )
        messages = [{"role": "system", "content": self._system()}, {"role": "user", "content": instruction}]
        try:
            found = parse_questions(self.chat(messages, max_words=40), how_many)
        except Exception:
            found = []
        found = [q for q in found if check_output(q) == q]
        return found if len(found) == how_many else FALLBACK_QUESTIONS[:how_many]

    def spoken(self, question: str) -> str:
        """How an approved question will be said, word for word."""
        return shape(check_output(question), self.age_band)

    def ask(self, question: str) -> str:
        """Put an approved question to the child."""
        self.history += [{"role": "assistant", "content": question}]
        return self.spoken(question)

    def answer(self, heard: str) -> str:
        if heard.strip():
            instruction = (
                f'The child answered: "{heard}". Reply in one or two short sentences. If the answer fits '
                "the story, say what was good about it. If it doesn't, gently give a small clue from the "
                "story, without saying they were wrong. Don't ask another question."
            )
        else:
            instruction = (
                "The child didn't answer. Say that's okay, and gently tell them the answer from the story. "
                "Don't ask another question."
            )
        return self.say(instruction, "Thanks for telling me!")

    def goodbye(self, minutes: float) -> str:
        return self.say(
            f"The session is over. The child read for about {max(1, round(minutes))} minutes today. "
            "Say a warm, short goodbye and that they did a great job reading today.",
            "Great job reading today! See you next time.",
        )
