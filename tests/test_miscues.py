from learnling.agents.reading import ReadingAgent
from learnling.models import Utterance

PASSAGE = "the cat sat on the mat and the dog ran to the park"


def test_clean_above_accuracy_threshold():
    agent = ReadingAgent()
    result = agent.assess(PASSAGE, Utterance(text=PASSAGE))
    assert result.accuracy == 1.0
    assert result.assessment == "clean"


def test_near_miss_substitution_is_decoding():
    agent = ReadingAgent()
    # "teh" for "the" is a classic decoding slip: edit distance 2, same first letter
    transcript = "teh cat sat on the mat and the dog ran to the park"
    result = agent.assess(PASSAGE, Utterance(text=transcript))
    assert result.assessment == "decoding"


def test_many_omissions_is_fluency():
    agent = ReadingAgent()
    transcript = "cat sat mat dog ran park"  # lots of dropped words
    result = agent.assess(PASSAGE, Utterance(text=transcript))
    assert result.assessment == "fluency"


def test_slow_choppy_reading_is_fluency():
    agent = ReadingAgent()
    # a couple of dropped words plus a very slow pace -> a fluency read, not clean
    transcript = "the cat sat on mat and the dog to the park"  # dropped "the" and "ran"
    result = agent.assess(PASSAGE, Utterance(text=transcript, duration_seconds=60.0))
    assert result.wpm is not None and result.wpm < 40
    assert result.assessment == "fluency"


def test_feedback_never_reveals_the_expected_word():
    agent = ReadingAgent()
    transcript = "the cat sat on the hat and the dog ran to the park"
    response = agent.handle(Utterance(text=transcript), {"passage_text": PASSAGE})
    assert "mat" not in response.spoken_text.lower()
