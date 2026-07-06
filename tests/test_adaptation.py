from learnling.adaptation import BAND_MAX_SENTENCE_WORDS, shape


def test_sentence_length_cap_per_band():
    long_sentence = " ".join(f"word{i}" for i in range(20)) + "."
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
