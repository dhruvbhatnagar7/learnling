# Building the book stand on a Raspberry Pi

The same `learnling live` that runs on a laptop, on a small computer in a book stand, with a microphone, a
speaker and a listening light. This guide has not been tried on a Pi yet; expect to adjust it.

## Parts

| Part | Notes | Rough cost |
|---|---|---|
| Raspberry Pi 5, 4 GB or 8 GB | The 4 GB model is enough | $60 to $80 |
| Official 27 W USB-C power supply | Underpowered supplies cause odd audio faults | $12 |
| microSD card, 32 GB | | $10 |
| Active cooler for the Pi 5 | Speech models keep the CPU busy | $5 |
| USB speakerphone (the kind used for video calls) | Microphone and speaker in one, and most cancel their own echo. The Pi 5 has no headphone jack, so audio has to go over USB or Bluetooth anyway | $25 to $40 |
| LED, 330 ohm resistor, 2 jumper wires | The listening light. Optional at first | $5 |
| Book stand | Plain, no character | $15 |

About $130 to $170 in total.

## Wiring the light

LED long leg to GPIO 17 (physical pin 11) through the 330 ohm resistor, short leg to any ground pin (for
example physical pin 9). Pass `--led-pin 17`.

## Software

1. Flash Raspberry Pi OS (64-bit) with Raspberry Pi Imager, and turn on SSH in its settings.
2. On the Pi:

```
sudo apt update && sudo apt install -y libportaudio2 git
python3 -m venv --system-site-packages ~/learnling-env    # system packages give gpiozero for the light
source ~/learnling-env/bin/activate
git clone https://github.com/dhruvbhatnagar7/learnling && cd learnling
pip install -e ".[live]"
```

3. Download a recognition model and a voice into `~/models` (see `docs/live-reading.md`). Start with the
   smaller recognition model; try the larger one if the Pi keeps up.
4. Check the speakerphone is the default input and output: `arecord -l` and `aplay -l` should list it.
5. Run:

```
python -m learnling live --passage passages/sample_level1.txt \
    --model ~/models/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17 \
    --voice ~/models/vits-piper-en_US-amy-low --led-pin 17 --age 6
```

## Before filming with children

- Each parent signs a consent form for the recording and for showing the video.
- Show what learnling actually does, including when it stays quiet because it is unsure. Do not edit the
  video to make it look more accurate than it is.
- The recogniser has not been tested on children's voices at home; see `docs/evaluation-method.md`.
