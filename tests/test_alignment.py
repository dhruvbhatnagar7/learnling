from learnling.agents.reading import align, normalize_words


def test_exact_match_has_no_miscues():
    words = normalize_words("the cat sat on the mat")
    assert align(words, words) == []


def test_substitution():
    expected = normalize_words("the cat sat on the mat")
    transcript = normalize_words("the cat sat on the hat")
    miscues = align(expected, transcript)
    assert len(miscues) == 1
    assert miscues[0].kind == "substitution"
    assert miscues[0].expected == "mat"
    assert miscues[0].heard == "hat"


def test_omission():
    expected = normalize_words("the cat sat on the mat")
    transcript = normalize_words("the cat on the mat")
    miscues = align(expected, transcript)
    assert len(miscues) == 1
    assert miscues[0].kind == "omission"
    assert miscues[0].expected == "sat"
    assert miscues[0].heard is None


def test_insertion():
    expected = normalize_words("the cat sat on the mat")
    transcript = normalize_words("the big cat sat on the mat")
    miscues = align(expected, transcript)
    assert len(miscues) == 1
    assert miscues[0].kind == "insertion"
    assert miscues[0].heard == "big"


def test_mixed_miscues():
    expected = normalize_words("the cat sat on the mat and slept")
    transcript = normalize_words("the cat on the hat and quietly slept")
    miscues = align(expected, transcript)
    kinds = {m.kind for m in miscues}
    assert "omission" in kinds
    assert "substitution" in kinds
    assert "insertion" in kinds


def test_empty_transcript_is_all_omissions():
    expected = normalize_words("the cat sat")
    miscues = align(expected, [])
    assert len(miscues) == 3
    assert all(m.kind == "omission" for m in miscues)
