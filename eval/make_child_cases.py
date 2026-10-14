"""Labelled eval cases from speechocean762 children (ages 6-10), test split.

    python eval/make_child_cases.py test-00000-of-00001.parquet CASES_DIR 300   (needs pyarrow and ffmpeg)

Only clips that the dataset's experts scored as complete (every word read)
are used, so `said` = the prompt text. As with the adult set, errors are made
by editing the passage, never the audio. Each clip gives one clean case and
one error case, cycling: close misreading, different word, skipped word.
"""
import io, json, random, subprocess, sys
from pathlib import Path
import pyarrow.parquet as pq

src, out, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
def ed1(a, b):
    if abs(len(a) - len(b)) > 1 or a == b: return False
    if len(a) == len(b): return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b): a, b = b, a
    return any(b[:i] + b[i+1:] == a for i in range(len(b)))

table = pq.read_table(src).to_pylist()
# Substitute words come from the dataset's own sentences, so they are real words.
vocab = sorted({w for r in table for w in r['text'].lower().split() if w.isalpha() and len(w) >= 3})
rows = [r for r in table if r['age'] <= 10 and r['completeness'] == 10.0]
rng = random.Random(7)
rng.shuffle(rows)
meta, kinds, made = [], ['close', 'different', 'skip'], 0
for r in rows:
    if made >= n: break
    words = r['text'].lower().split()
    kind = kinds[made % 3]
    cands = [i for i, w in enumerate(words) if len(w) >= 3]
    if kind != 'skip' and not cands: continue
    passage = list(words)
    if kind == 'close':
        opts = [(i, v) for i in cands for v in vocab if ed1(words[i], v)]
        if not opts: continue
        i, v = rng.choice(opts); passage[i] = v
    elif kind == 'different':
        i = rng.choice(cands)
        v = rng.choice([v for v in vocab if abs(len(v) - len(words[i])) <= 1 and v[0] != words[i][0] and not ed1(v, words[i])])
        passage[i] = v
    else:
        i = rng.randrange(len(words) + 1); passage.insert(i, rng.choice(['big', 'little', 'then', 'very', 'also', 'happy']))
    stem = f"c{made:03d}-age{r['age']}-{r['speaker']}"
    wav = out / f"{stem}.wav"
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', 'pipe:0', '-ac', '1', '-ar', '16000', '-sample_fmt', 's16', str(wav)], input=r['audio']['bytes'], check=True)
    said = ' '.join(words)
    (out / f"{stem}-clean.json").write_text(json.dumps({"passage": said, "said": said, "audio": wav.name}))
    (out / f"{stem}-{kind}.json").write_text(json.dumps({"passage": ' '.join(passage), "said": said, "audio": wav.name}))
    meta.append({"stem": stem, "age": r['age'], "speaker": r['speaker'], "sentence_accuracy": r['accuracy'], "kind": kind})
    made += 1
(out.parent / 'child-cases-meta.json').write_text(json.dumps(meta, indent=1))
print(made, 'clips,', 2 * made, 'cases,', len({m['speaker'] for m in meta}), 'children')
