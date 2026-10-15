from learnling.asr.phonetic import (
    PaskettiPhoneticASR,
    Pronouncer,
    normalize_phones,
    word_errors,
)

DICT = {
    "the": [["DH", "AH0"]],
    "cat": [["K", "AE1", "T"]],
    "sat": [["S", "AE1", "T"]],
    "big": [["B", "IH1", "G"]],
}


class FakeModel:
    def __init__(self, ipa):
        self._ipa = ipa

    def ipa(self, path):
        return self._ipa


def asr(passage, heard):
    return PaskettiPhoneticASR(passage, model=FakeModel(heard), pronouncer=Pronouncer(DICT))


def test_normalize_drops_marks_and_unifies_spellings():
    assert normalize_phones("lɑ͡ɪks ˈʤɐ̃m") == ["l", "ɑ", "ɪ", "k", "s", "d", "ʒ", "ʌ", "m"]


def test_word_errors_counts_sounds_per_word():
    words = [["k", "æ", "t"], ["s", "æ", "t"]]
    assert word_errors(words, ["k", "æ", "t", "s", "æ", "t"]) == [(0.0, False), (0.0, False)]
    share, skipped = word_errors(words, ["k", "æ", "t"])[1]
    assert skipped and share == 1.0


def test_reading_matches_passage():
    assert asr("the cat sat", "ðə kæt sæt").transcribe("x.wav").text == "the cat sat"


def test_different_word_becomes_unk_and_skip_is_left_out():
    assert asr("the big cat sat", "ðə kæt ʃun").transcribe("x.wav").text == "the cat unk"


def test_accent_level_difference_is_accepted():
    # "kɛd" for "cat": one vowel and one voicing change, half a mistake each.
    assert asr("the cat", "ðə kɛd").transcribe("x.wav").text == "the cat"


def test_no_timestamps_or_confidence():
    utterance = asr("the cat", "ðə kæt").transcribe("x.wav")
    assert utterance.confidence is None and utterance.word_confidences is None
