"""Numbers the recogniser writes as digits."""

from learnling.agents.reading import ReadingAgent
from learnling.models import Utterance


def test_a_number_heard_as_digits_matches_the_page_in_words():
    page = "More than a hundred years ago, letters took weeks. One thousand two hundred and five miles."
    for heard in ("more than 100 years ago letters took weeks 1205 miles",
                  "more than a 100 years ago letters took weeks 1205 miles"):
        result = ReadingAgent().assess(page, Utterance(text=heard, duration_seconds=10), confidence_threshold=0.0)
        assert [m for m in result.miscues if m.kind != "insertion"] == []
        assert result.accuracy == 1.0


def test_a_wrong_number_is_still_a_miscue():
    result = ReadingAgent().assess("a hundred years ago", Utterance(text="200 years ago", duration_seconds=5),
                                   confidence_threshold=0.0)
    assert result.accuracy < 1.0
