"""The fixed closing at the end of a stand session started from the phone."""

from learnling.buddy import ReadingBuddy
from learnling.stand import BYE_LINE, run_stand
from tests.test_stand import PASSAGE, FakeChat, PhaseRecognizer, open_mic

CLOSING = "Great reading today! I'm proud of you. Otherwise, say goodbye!"


def _session(bye_script):
    rec = PhaseRecognizer([
        [(1.0, "im ready to read")],
        [(0.5, PASSAGE)],
        [(0.5, PASSAGE)],
        bye_script,
    ])
    spoken = []
    chat = FakeChat("You did it!")
    run_stand(PASSAGE, rec, open_mic, spoken.append, ReadingBuddy(PASSAGE, 7, chat=chat), [],
              on_status=lambda text: None, closing=CLOSING)
    return spoken


def test_the_closing_replaces_the_goodbye_and_answers_a_bye():
    spoken = _session([(1.0, "bye")])
    assert spoken[-2:] == [CLOSING, BYE_LINE]
    assert "You did it!" not in spoken[-2:]


def test_no_bye_means_no_answer():
    spoken = _session([])
    assert spoken[-1] == CLOSING
