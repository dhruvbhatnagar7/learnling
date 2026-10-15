# Reproducing the evaluation

These scripts rebuild every test case behind [`results/`](../results/) from public recordings. No audio is
committed to this repository; `fetch.sh` downloads it. The method is described in
[`docs/evaluation-method.md`](../docs/evaluation-method.md).

```
pip install -e ".[asr,vosk]" pyarrow
bash eval/fetch.sh eval-data

# Adults (21 cases from 6 LibriSpeech clips)
python eval/make_adult_cases.py eval-data/clips eval-data/adult-cases
python -m learnling eval eval-data/adult-cases --asr vosk --vosk-model eval-data/models/vosk-model-small-en-us-0.15
python -m learnling eval eval-data/adult-cases --asr whisper

# Children (600 cases from 300 speechocean762 clips)
python eval/make_child_cases.py eval-data/speechocean762-test.parquet eval-data/child-cases 300
python -m learnling eval eval-data/child-cases --asr vosk --vosk-model eval-data/models/vosk-model-small-en-us-0.15 > child-vosk.txt
python -m learnling eval eval-data/child-cases --asr whisper > child-whisper.txt
python eval/breakdown.py child-vosk.txt
```

The child cases are drawn with a fixed random seed, so the same 300 clips and the same edits come out each
time.

| File | What it does |
|---|---|
| `fetch.sh` | Downloads the clips, the children's dataset and the Vosk model |
| `make_adult_cases.py` | Turns the 6 adult clips into 21 labelled cases |
| `make_child_cases.py` | Turns speechocean762 clips into one clean and one error case each |
| `breakdown.py` | Splits a results table by error type and child age |
| `neighbour_experiment.py` | A side experiment, not part of learnling: Vosk with similar-looking words added |
