"""The passage corpus: material tagged on the skill axis and the content axis.

The point of tagging both is that the same phonics pattern set has to exist at
every content tier. A learner working on consonant digraphs needs digraph
practice; whether that practice is about a duckling or about a late shift at a
warehouse is a separate question, answered by their age.

The corpus ships as JSON rather than YAML so the core package stays
dependency-free — `json` is stdlib, and the data still lives in a data file
rather than as literals in code, which was the point.

Stored under `learnling/data/` rather than a top-level `data/` directory so it
survives being pip-installed: a top-level directory is not packaged, and the
corpus would be missing for anyone who installed learnling rather than cloning
it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from learnling.models import ContentTier, Passage, SkillStage

_CORPUS_PATH = Path(__file__).parent / "data" / "passages.json"

#: The decodable progression this corpus is tagged against.
#:
#: Cumulative, as phonics progressions are: a stage-3 passage may freely use
#: stage-1 and stage-2 patterns, and does. Only the *new* patterns a stage
#: introduces are listed here.
FOUNDATIONAL_PATTERNS: dict[SkillStage, list[str]] = {
    "1a": ["cvc", "short a", "short e", "short i", "short o", "short u"],
    "1b": ["initial blends", "final blends", "ll", "ss", "ff"],
    "1c": ["ck", "ng", "nk", "three-letter blends", "cvcc", "ccvc"],
    "2": ["sh", "ch", "th", "tch", "wh"],
    "3": ["a_e", "i_e", "o_e", "u_e", "ai", "ay", "ee", "ea", "oa"],
    "4": ["ar", "or", "er", "ir", "ur", "oi", "oy", "ou", "ow", "oo"],
    "5": ["multisyllabic", "prefixes", "suffixes", "schwa"],
    "6": ["greek roots", "latin roots", "advanced morphology"],
}


def _passage_from_record(record: dict) -> Passage:
    return Passage(
        id=record["id"],
        text=record["text"],
        patterns=record["patterns"],
        foundational_stage=record["foundational_stage"],
        content_tier=ContentTier(record["content_tier"]),
        wcpm_target_grade=record["wcpm_target_grade"],
        comprehension_prompts=record.get("comprehension_prompts", {}),
    )


@lru_cache(maxsize=1)
def load_corpus() -> tuple[Passage, ...]:
    """Load every tagged passage. Cached: the corpus is read-only at runtime."""
    records = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    return tuple(_passage_from_record(record) for record in records["passages"])
