"""Age adaptation: shape every spoken response to the child's developmental band.

This is applied to every agent's output, every time, by the orchestrator —
it's a horizontal layer, not something each agent has to remember to do.

Band table (v0, rule-based):

    age_band   max words/sentence   vocabulary simplification
    --------   ------------------   -------------------------
    4-6        8                    yes (see SIMPLIFICATION_MAP)
    7-8        12                   no
    9-10       16                   no
    11+        20                   no

Longer sentences are split at the word-count boundary rather than dropped —
nothing the agent said is discarded, it's just re-paced for the listener.
Vocabulary simplification is scoped to the youngest band only, since that's
where "attempt" vs. "try" matters most for comprehension.

The 11+ band exists because this layer governs how the agent *speaks*, and
learners past ten are served by the rest of the system: an older student
practising early phonics gets age-appropriate passages (see `selection.py`),
and it would undo that work to hand them mature material and then talk over
it in sentences clipped for a nine-year-old. Note that these bands partition
age differently from `ContentTier` on purpose — how you speak to someone and
what you ask them to read are different questions.

An optional LLM polish pass can run after the rule-based shaping, off by
default: set `LEARNLING_LLM=1` and `ANTHROPIC_API_KEY` to enable it. It
rephrases the already-shaped text rather than replacing the rule-based pass,
so behavior stays predictable even when the polish step is skipped or fails.
"""

from __future__ import annotations

import os
import re

BAND_MAX_SENTENCE_WORDS = {"4-6": 8, "7-8": 12, "9-10": 16, "11+": 20}

SIMPLIFICATION_MAP = {
    "attempt": "try",
    "assist": "help",
    "difficult": "hard",
    "purchase": "buy",
    "however": "but",
    "additional": "more",
    "immediately": "right away",
    "several": "some",
    "observe": "watch",
    "require": "need",
    "enormous": "huge",
}

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised only without the extra
    anthropic = None

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z']+")


def _simplify_words(text: str) -> str:
    def replace(match: re.Match) -> str:
        word = match.group(0)
        replacement = SIMPLIFICATION_MAP.get(word.lower())
        if replacement is None:
            return word
        return replacement.capitalize() if word[0].isupper() else replacement

    return _WORD.sub(replace, text)


def _split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_BOUNDARY.split(text.strip()) if s]


def _finish_chunk(words: list[str]) -> str:
    chunk = " ".join(words).strip(" ,;—-")
    if not chunk.endswith((".", "!", "?")):
        chunk += "."
    return chunk[0].upper() + chunk[1:] if chunk else chunk


def _cap_sentence_length(sentence: str, max_words: int) -> list[str]:
    words = sentence.split()
    if len(words) <= max_words:
        return [sentence]

    chunks = []
    remaining = words
    while len(remaining) > max_words:
        split_at = max_words
        # prefer breaking at a natural pause near the cap over a hard word cut
        for i in range(max_words, max(0, max_words - 3), -1):
            if remaining[i - 1].endswith((",", ";", "—", "-")):
                split_at = i
                break
        chunks.append(_finish_chunk(remaining[:split_at]))
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(_finish_chunk(remaining))
    return chunks


def _llm_polish_enabled() -> bool:
    return os.environ.get("LEARNLING_LLM") == "1" and bool(os.environ.get("ANTHROPIC_API_KEY"))


def _llm_polish(text: str, age_band: str, max_words: int) -> str:
    model = os.environ.get("LEARNLING_MODEL", "claude-opus-4-8")
    client = anthropic.Anthropic()
    system = (
        f"Rewrite the given text so it reads naturally for a child in the "
        f"{age_band} age band, keeping the same meaning and warmth. Keep each "
        f"sentence to about {max_words} words or fewer. Return only the rewritten "
        "text, nothing else."
    )
    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": text}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text")).strip()


def shape(text: str, age_band: str) -> str:
    """Shape `text` for `age_band`: simplify vocabulary, cap sentence length."""
    max_words = BAND_MAX_SENTENCE_WORDS.get(age_band, BAND_MAX_SENTENCE_WORDS["7-8"])

    shaped = _simplify_words(text) if age_band == "4-6" else text

    sentences = []
    for sentence in _split_sentences(shaped):
        sentences.extend(_cap_sentence_length(sentence, max_words))
    shaped = " ".join(sentences)

    if _llm_polish_enabled() and anthropic is not None:
        try:
            shaped = _llm_polish(shaped, age_band, max_words)
        except Exception:
            pass  # any API/network failure keeps the rule-based result

    return shaped
