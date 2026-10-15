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


def test_joined_word_is_not_a_miscue():
    expected = normalize_words("to connect her parent for ever with the race")
    transcript = normalize_words("to connect her parent forever with the race")
    assert align(expected, transcript) == []


def test_split_word_is_not_a_miscue():
    expected = normalize_words("the frog jumped into the pond")
    transcript = normalize_words("the frog jumped in to the pond")
    assert align(expected, transcript) == []


def test_joining_keeps_confidences_in_step():
    expected = normalize_words("for ever and a day")
    transcript = normalize_words("forever and a dog")
    miscues = align(expected, transcript, word_confidences=[0.9, 0.9, 0.9, 0.4])
    assert len(miscues) == 1
    assert miscues[0].heard == "dog"
    assert miscues[0].confidence == 0.4


def test_real_misreading_next_to_a_page_pair_still_counts():
    expected = normalize_words("in to the house")
    transcript = normalize_words("in the house")
    miscues = align(expected, transcript)
    assert [m.kind for m in miscues] == ["omission"]


def test_digits_match_spelled_out_numbers():
    expected = normalize_words("nine three two and twenty one")
    transcript = normalize_words("9 3 2 and 21")
    assert align(expected, transcript) == []
