"""Experiment, not in learnling itself: give Vosk real-word neighbours of each passage word.

    python eval/neighbour_experiment.py CASES_DIR VOSK_MODEL_DIR WHISPER_TOKENIZER_JSON

The tokenizer.json of faster-whisper base.en is used only as an English word list.
"""
import json, sys, wave, glob
import vosk; vosk.SetLogLevel(-1)
from pathlib import Path
from learnling.asr.vosk import passage_grammar, UNKNOWN_WORD
from learnling.asr.base import utterance_from_words
from learnling.evaluate import EvalSummary, CaseResult, _error_positions, load_case, format_summary
from learnling.agents.reading import ReadingAgent, align, normalize_words

tok = json.load(open(sys.argv[3]))['model']['vocab']
vocab = {t[1:].lower() for t in tok if t.startswith('Ġ') and t[1:].isalpha() and len(t) > 3}
by_len = {}
for w in vocab: by_len.setdefault(len(w), set()).add(w)
def ed1(a, b):
    if abs(len(a)-len(b)) > 1: return False
    if len(a) == len(b): return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b): a, b = b, a
    return any(b[:i] + b[i+1:] == a for i in range(len(b)))
def neighbours(word):
    if len(word) < 3: return []
    return sorted(w for L in (len(word)-1, len(word), len(word)+1) for w in by_len.get(L, ()) if w != word and ed1(word, w))

m = vosk.Model(sys.argv[2])
summary = EvalSummary()
for lp in sorted(Path(sys.argv[1]).glob('*.json')):
    passage, said, audio = load_case(lp)
    pw = passage_grammar(passage)[:-1]
    extra = sorted({n for w in pw for n in neighbours(w)} - set(pw))
    r = vosk.KaldiRecognizer(m, 16000, json.dumps(pw + extra + ['[unk]'])); r.SetWords(True)
    wv = wave.open(str(audio)); res = []
    while (d := wv.readframes(4000)):
        if r.AcceptWaveform(d): res.append(json.loads(r.Result()))
    res.append(json.loads(r.FinalResult()))
    u = utterance_from_words([(UNKNOWN_WORD if x['word'] == '[unk]' else x['word'], x['start'], x['end'], x.get('conf')) for q in res for x in q.get('result', [])])
    exp = normalize_words(passage)
    out = ReadingAgent().assess(passage, u)
    summary.cases.append(CaseResult(lp.stem, len(exp), _error_positions(align(exp, normalize_words(said))), _error_positions(out.miscues), out.suppressed_miscues, out.wcpm, u.text))
print(format_summary(summary))
for c in summary.cases:
    if c.missed or c.false_accusations: print(c.name, '|', c.transcript)
