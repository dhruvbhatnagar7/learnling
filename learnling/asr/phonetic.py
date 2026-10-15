"""Passage-checked phone recognition with pasketti-phonetic (experimental).

`drivendata/pasketti-phonetic` is a WavLM model fine-tuned on about 116
hours of children's speech. It does not write words. It writes the sounds
it heard, in IPA ("ɛn æ dɚæf ɪz deiɹ tu" for "and a giraffe is there too").

So this adapter does the word step itself. Each passage word is turned into
the sounds it should have (CMU Pronouncing Dictionary, mapped to IPA), and
the sounds the model heard are lined up against the sounds of the whole
passage with an edit-distance alignment. For each passage word it then asks
how much of it went wrong:

- every sound missing: the word was skipped, and it is left out;
- more than `max_word_error` of its sounds wrong: the word is reported as
  `unk`, a misreading;
- otherwise: the word is reported as read.

The model's own word boundaries are not used, because children's pauses and
run-together words make them unreliable; the alignment decides where words
start and end. Similar sounds (two vowels, "t" and "d") cost half a
mistake, so an accent does not count as badly as a different word.

The model gives no timestamps or calibrated confidence, so the utterance has
neither, and every miscue it produces is kept. `max_word_error` is the only
knob.

Needs `pip install learnling[phonetic]`. Runs on CPU.
The model card asks that it not be used for surveillance or profiling of
children, or for fully automated high-stakes decisions.
"""

from __future__ import annotations

import unicodedata

from learnling.agents.reading import normalize_words
from learnling.asr.base import utterance_from_words
from learnling.models import Utterance

MODEL_ID = "drivendata/pasketti-phonetic"
UNKNOWN_WORD = "unk"

_ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "B": "b",
    "CH": "tʃ", "D": "d", "DH": "ð", "EH": "ɛ", "ER": "ɚ", "EY": "eɪ", "F": "f",
    "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k", "L": "l",
    "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "ɹ",
    "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}

#: Spellings of the same sound that differ between the dictionary and the model.
_SAME = {"g": "ɡ", "r": "ɹ", "ɝ": "ɚ", "ɐ": "ʌ", "ɜ": "ɚ", "ɫ": "l", "ʤ": "dʒ", "ʧ": "tʃ"}

_VOWELS = set("aeiouæɑɒɔəɚɛɪʊʌɨʉɯɤøœy")
#: Sounds a listener would still accept as close: voicing pairs and the flap.
_CLOSE_PAIRS = [
    {"p", "b"}, {"t", "d", "ɾ"}, {"k", "ɡ"}, {"f", "v"}, {"θ", "ð", "f"},
    {"s", "z"}, {"ʃ", "ʒ"}, {"m", "n", "ŋ"}, {"l", "ɹ", "w"}, {"θ", "t"},
    {"ð", "d"}, {"t", "ʔ"},
]


def normalize_phones(ipa: str) -> list[str]:
    """IPA text to a list of single-sound symbols, without stress, length,
    nasalisation, tie bars or spaces."""
    out: list[str] = []
    for ch in unicodedata.normalize("NFD", ipa):
        if ch.isspace() or unicodedata.combining(ch) or ch in "ˈˌːˑ.|‿-'":
            continue
        out.append(_SAME.get(ch, ch))
    # _SAME can expand to two symbols ("ʤ" -> "dʒ"); keep one symbol per entry.
    return [c for sym in out for c in sym]


def substitution_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if a in _VOWELS and b in _VOWELS:
        return 0.5
    if any(a in pair and b in pair for pair in _CLOSE_PAIRS):
        return 0.5
    return 1.0


class Pronouncer:
    """Word to IPA sounds, from the CMU Pronouncing Dictionary."""

    def __init__(self, dictionary: dict[str, list[list[str]]] | None = None):
        if dictionary is None:
            import cmudict

            dictionary = cmudict.dict()
        self._dict = dictionary
        self.unknown_words: set[str] = set()

    def phones(self, word: str) -> list[str]:
        prons = self._dict.get(word.lower())
        if not prons:
            # Not in the dictionary: fall back to the letters, which is crude
            # but keeps the word in the alignment.
            self.unknown_words.add(word)
            return normalize_phones(word)
        ipa = "".join(
            "ə" if p.rstrip("012") == "AH" and p.endswith("0") else _ARPABET_TO_IPA[p.rstrip("012")]
            for p in prons[0]
        )
        return normalize_phones(ipa)


def word_errors(passage_words: list[list[str]], heard: list[str]) -> list[tuple[float, bool]]:
    """Align heard sounds to the passage's sounds; per word, return
    (share of its sounds wrong, whether every sound was missing)."""
    ref = [(p, w) for w, phones in enumerate(passage_words) for p in phones]
    n, m = len(ref), len(heard)
    inf = float("inf")
    cost = [[inf] * (m + 1) for _ in range(n + 1)]
    back: list[list[str | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if i and cost[i - 1][j] + 1 < cost[i][j]:
                cost[i][j], back[i][j] = cost[i - 1][j] + 1, "del"
            if j and cost[i][j - 1] + 1 < cost[i][j]:
                cost[i][j], back[i][j] = cost[i][j - 1] + 1, "ins"
            if i and j:
                c = cost[i - 1][j - 1] + substitution_cost(ref[i - 1][0], heard[j - 1])
                if c < cost[i][j]:
                    cost[i][j], back[i][j] = c, "sub"

    wrong = [0.0] * len(passage_words)
    deleted = [0] * len(passage_words)
    i, j = n, m
    while i or j:
        step = back[i][j]
        if step == "sub":
            wrong[ref[i - 1][1]] += substitution_cost(ref[i - 1][0], heard[j - 1])
            i, j = i - 1, j - 1
        elif step == "del":
            wrong[ref[i - 1][1]] += 1
            deleted[ref[i - 1][1]] += 1
            i -= 1
        else:
            # An extra sound inside a word counts against that word; one
            # between words (a pause filler, a restart) counts against none.
            if 0 < i < n and ref[i - 1][1] == ref[i][1]:
                wrong[ref[i - 1][1]] += 1
            j -= 1
    return [
        (wrong[w] / len(phones) if phones else 0.0, bool(phones) and deleted[w] == len(phones))
        for w, phones in enumerate(passage_words)
    ]


class PhoneticModel:
    """Loads pasketti-phonetic once and turns a WAV file into IPA text."""

    def __init__(self, model_id: str = MODEL_ID):
        import torch
        from transformers import Wav2Vec2Processor, WavLMForCTC

        self._torch = torch
        self.processor = Wav2Vec2Processor.from_pretrained(model_id)
        self.model = WavLMForCTC.from_pretrained(model_id).eval()
        self._cache: dict[str, str] = {}

    def ipa(self, path: str) -> str:
        if path not in self._cache:
            import librosa

            wav, _ = librosa.load(path, sr=16000, mono=True)
            inputs = self.processor(wav, sampling_rate=16000, return_tensors="pt")
            with self._torch.no_grad():
                ids = self.model(**inputs).logits.argmax(-1)
            self._cache[path] = self.processor.batch_decode(ids)[0]
        return self._cache[path]


class PaskettiPhoneticASR:
    """Checks a reading of one passage, sound by sound."""

    def __init__(
        self,
        passage_text: str,
        model: PhoneticModel | None = None,
        pronouncer: Pronouncer | None = None,
        max_word_error: float = 0.5,
    ):
        self._model = model or PhoneticModel()
        self._words = normalize_words(passage_text)
        pronouncer = pronouncer or Pronouncer()
        self._phones = [pronouncer.phones(w) for w in self._words]
        self._max = max_word_error
        self.last_ipa = ""

    def transcribe(self, audio: str | bytes) -> Utterance:
        if isinstance(audio, bytes):
            raise TypeError("PaskettiPhoneticASR.transcribe expects a WAV file path")
        self.last_ipa = self._model.ipa(audio)
        scores = word_errors(self._phones, normalize_phones(self.last_ipa))
        words = []
        for word, (share_wrong, skipped) in zip(self._words, scores):
            if skipped:
                continue
            words.append((word if share_wrong <= self._max else UNKNOWN_WORD, 0.0, 0.0, None))
        return utterance_from_words(words)
