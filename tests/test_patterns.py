import json

from learnling.models import LearnerProfile, Miscue, Utterance
from learnling.orchestrator import Orchestrator
from learnling.patterns import patterns_for
from learnling.report import generate_report


def _sub(expected, heard):
    return patterns_for(Miscue("substitution", expected, heard, 0))


def test_the_pattern_is_where_the_words_differ():
    assert _sub("found", "fond") == ["vowel_team"]
    assert _sub("high", "hig") == ["vowel_team"]
    assert _sub("shell", "sell") == ["digraph"]
    assert _sub("frog", "fog") == ["blend"]
    assert _sub("swam", "swim") == ["short_vowel"]
    assert _sub("kite", "kit") == ["silent_e"]
    assert _sub("park", "pack") == ["r_controlled"]
    assert _sub("mat", "hat") == ["consonant"]


def test_a_dropped_or_changed_ending_is_an_ending_slip():
    assert _sub("sitting", "sit") == ["ending"]
    assert _sub("jumped", "jumps") == ["ending"]
    assert _sub("make", "making") == ["ending"]


def test_an_unrelated_word_is_not_blamed_on_a_spelling_pattern():
    assert _sub("the", "a") == ["swap"]


def test_skips_and_additions_are_their_own_groups():
    assert patterns_for(Miscue("omission", "white", None, 0)) == ["skipped"]
    assert patterns_for(Miscue("insertion", None, "big", 0)) == ["added"]


PASSAGE = "Mia found a shell on the beach. It was pink and white and smooth."


def _report(text, word_confidences=None, fmt="markdown"):
    orchestrator = Orchestrator(LearnerProfile(age_years=7))
    orchestrator.load_passage(PASSAGE)
    orchestrator.handle_utterance(
        Utterance(text=text, duration_seconds=8.0, word_confidences=word_confidences)
    )
    return generate_report(orchestrator.session, fmt=fmt)


def test_the_report_names_the_words_and_the_pattern():
    report = _report("Mia fond a shell on the beach. It was pink and smooth.")
    assert '"found", read as "fond" (vowel teams)' in report
    assert '"white", skipped' in report
    assert "## Sounds to practise" in report
    assert "Vowel teams" in report


def test_words_the_recogniser_was_unsure_of_are_marked_not_sure():
    confidences = [0.9] * 6 + [0.3] + [0.9] * 6
    report = _report(
        "Mia found a shell on the bench. It was pink and white and smooth.",
        word_confidences=confidences,
    )
    assert 'Not sure, so not mentioned to the reader: "beach", read as "bench"' in report
    # A word nobody is sure about does not count toward what to practise.
    assert "## Sounds to practise" not in report


def test_the_json_report_carries_the_same_words():
    summary = json.loads(_report("Mia fond a shell on the beach. It was pink and white and smooth.", fmt="json"))
    words = summary["reading_stats"][0]["words_to_look_at"]
    assert words == [
        {"word": "found", "read_as": "fond", "kind": "substitution", "patterns": ["vowel_team"], "sure": True}
    ]


def test_a_clean_read_has_nothing_to_look_at():
    report = _report(PASSAGE)
    assert "words to look at" not in report
    assert "Sounds to practise" not in report
