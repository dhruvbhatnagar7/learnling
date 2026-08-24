from learnling.models import age_band_for
from learnling.adaptation import BAND_MAX_SENTENCE_WORDS, shape


def test_sentence_length_cap_per_band():
    # comfortably longer than the widest band, so every cap is actually exercised
    longest_cap = max(BAND_MAX_SENTENCE_WORDS.values())
    long_sentence = " ".join(f"word{i}" for i in range(longest_cap * 2)) + "."
    for band, max_words in BAND_MAX_SENTENCE_WORDS.items():
        shaped = shape(long_sentence, band)
        for sentence in shaped.split(". "):
            words = [w for w in sentence.rstrip(".").split() if w]
            assert len(words) <= max_words


def test_simplification_applies_only_to_youngest_band():
    text = "I will attempt this difficult task."
    shaped_young = shape(text, "4-6")
    shaped_older = shape(text, "7-8")
    assert "attempt" not in shaped_young.lower()
    assert "difficult" not in shaped_young.lower()
    assert "attempt" in shaped_older.lower()
    assert "difficult" in shaped_older.lower()


def test_short_text_passes_through_unchanged_shape():
    text = "Great job!"
    assert shape(text, "9-10") == text


def test_older_learners_get_the_upper_speech_band():
    """An 11+ learner is spoken to in their own band, not a nine-year-old's.

    The rest of the system serves this learner age-appropriate material; it
    would undo that to then talk over it in clipped sentences.
    """
    assert age_band_for(11) == "11+"
    assert age_band_for(15) == "11+"
    assert BAND_MAX_SENTENCE_WORDS["11+"] > BAND_MAX_SENTENCE_WORDS["9-10"]


def test_no_vocabulary_simplification_above_the_youngest_band():
    text = "I will attempt this difficult task."
    assert "attempt" in shape(text, "11+").lower()
