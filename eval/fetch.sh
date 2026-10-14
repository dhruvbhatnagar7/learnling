#!/usr/bin/env bash
# Download everything the 2026-10-13 evaluation used into ./eval-data (not committed).
# Needs curl, tar, unzip and ffmpeg. About 400 MB in total.
set -euo pipefail

DATA="${1:-eval-data}"
mkdir -p "$DATA/clips" "$DATA/models" "$DATA/tmp"
cd "$DATA"

# Adult read speech: LibriSpeech (CC BY 4.0) sample clips shipped with two open-source projects.
curl -L -o tmp/deepspeech-audio.tar.gz \
  https://github.com/mozilla/DeepSpeech/releases/download/v0.9.3/audio-0.9.3.tar.gz
tar -xzf tmp/deepspeech-audio.tar.gz -C tmp
for id in 2830-3980-0043 4507-16021-0012 8455-210777-0068; do
  ffmpeg -loglevel error -y -i "tmp/audio/$id.wav" -ac 1 -ar 16000 -sample_fmt s16 "clips/ls-$id.wav"
done

curl -L -o tmp/sherpa-whisper-tiny.tar.bz2 \
  https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-tiny.en.tar.bz2
tar -xjf tmp/sherpa-whisper-tiny.tar.bz2 -C tmp
for id in 0 1 8k; do
  ffmpeg -loglevel error -y -i "tmp/sherpa-onnx-whisper-tiny.en/test_wavs/$id.wav" -ac 1 -ar 16000 -sample_fmt s16 "clips/ls-$id.wav"
done

# Children: speechocean762 test split (Mandarin-speaking speakers reading English; the case script keeps children aged 10 and under).
curl -L -o speechocean762-test.parquet \
  https://huggingface.co/datasets/mispeech/speechocean762/resolve/main/data/test-00000-of-00001.parquet

# Vosk small English model. faster-whisper downloads base.en by itself on first use.
curl -L -o tmp/vosk.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip -q -o tmp/vosk.zip -d models

rm -rf tmp
echo "Done. Clips in $DATA/clips, children's data in $DATA/speechocean762-test.parquet, Vosk in $DATA/models."
