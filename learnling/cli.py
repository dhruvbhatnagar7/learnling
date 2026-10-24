"""The learnling command-line interface.

    python -m learnling read --passage passages/sample_level1.txt --age 6 --simulate "the cat sat on teh mat"
    python -m learnling read --passage passages/sample_level1.txt --age 6 --audio recording.wav   # requires [asr]
    python -m learnling read --passage passages/sample_level1.txt --age 6 --audio recording.wav --asr vosk --vosk-model PATH
    python -m learnling record --passage passages/sample_level1.txt --asr vosk --vosk-model PATH --save-to my-readings
    python -m learnling eval path/to/test-set --asr vosk --vosk-model PATH
    python -m learnling ask --age 7 --simulate "why is the sky blue"
    python -m learnling demo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from learnling.asr.mock import SimulatedASR
from learnling.models import LearnerProfile, Miscue, Utterance
from learnling.orchestrator import Orchestrator
from learnling.report import generate_report


def _print_miscue_table(miscues: list[Miscue]) -> None:
    if not miscues:
        print("  (no miscues)")
        return
    print(f"  {'kind':<14}{'expected':<14}{'heard':<14}position")
    print(f"  {'-' * 13:<14}{'-' * 13:<14}{'-' * 13:<14}--------")
    for m in miscues:
        print(f"  {m.kind:<14}{(m.expected or '-'):<14}{(m.heard or '-'):<14}{m.position}")


def _build_asr(args: argparse.Namespace, passage_text: str | None):
    """The real-audio adapter the flags ask for."""
    backend = getattr(args, "asr", "whisper")
    try:
        if backend == "vosk":
            from learnling.asr.vosk import VoskPassageASR

            if passage_text is None:
                print("error: --asr vosk needs a passage to listen for", file=sys.stderr)
                raise SystemExit(1)
            if not args.vosk_model:
                print("error: --asr vosk needs --vosk-model PATH", file=sys.stderr)
                raise SystemExit(1)
            return VoskPassageASR(passage_text, model_path=args.vosk_model)

        if backend == "sherpa":
            from learnling.asr.sherpa import SherpaStreamingASR

            if not getattr(args, "model", None):
                print("error: --asr sherpa needs --model PATH", file=sys.stderr)
                raise SystemExit(1)
            return SherpaStreamingASR(args.model)

        if backend == "pasketti":
            from learnling.asr.phonetic import PaskettiPhoneticASR, PhoneticModel

            if passage_text is None:
                print("error: --asr pasketti needs a passage to check against", file=sys.stderr)
                raise SystemExit(1)
            if not hasattr(args, "_phonetic_model"):
                args._phonetic_model = PhoneticModel(getattr(args, "model", None) or "drivendata/pasketti-phonetic")
            return PaskettiPhoneticASR(
                passage_text, model=args._phonetic_model, max_word_error=args.max_word_error
            )

        from learnling.asr.whisper import WhisperASR

        return WhisperASR(model_size=getattr(args, "whisper_model", "base.en"))
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _get_utterance(args: argparse.Namespace, passage_text: str | None = None) -> Utterance:
    if args.simulate is not None:
        return SimulatedASR().transcribe(args.simulate)
    if args.audio is not None:
        return _build_asr(args, passage_text).transcribe(args.audio)
    print("error: pass either --simulate TEXT or --audio PATH", file=sys.stderr)
    raise SystemExit(1)


def _maybe_save_report(orchestrator: Orchestrator, path: str | None) -> None:
    if not path:
        return
    fmt = "json" if path.endswith(".json") else "markdown"
    Path(path).write_text(generate_report(orchestrator.session, fmt=fmt))
    print(f"\nSaved session report to {path}")


def cmd_read(args: argparse.Namespace) -> None:
    passage_text = Path(args.passage).read_text().strip()
    profile = LearnerProfile(age_years=args.age)
    orchestrator = Orchestrator(profile)
    orchestrator.load_passage(passage_text)

    utterance = _get_utterance(args, passage_text)
    _score_and_print(orchestrator, passage_text, utterance)
    _maybe_save_report(orchestrator, args.save_report)


def _score_and_print(orchestrator: Orchestrator, passage_text: str, utterance: Utterance) -> None:
    feedback = orchestrator.handle_utterance(utterance)
    result = orchestrator.session.events[-1]["report_notes"]["reading_result"]

    print(f"Passage:    {passage_text}")
    print(f"Transcript: {result.transcript}")
    print("Miscues:")
    _print_miscue_table(result.miscues)
    print(f"Accuracy:   {result.accuracy:.0%}")
    if result.wpm is not None:
        print(f"WPM:        {result.wpm:.0f}")
    if result.wcpm is not None:
        print(f"WCPM:       {result.wcpm}")
    print(f"Assessment: {result.assessment}")
    print(f"\nlearnling says: {feedback}")


def cmd_record(args: argparse.Namespace) -> None:
    from learnling.record import record_until_enter, save_for_evaluation, transcribe_pcm

    passage_text = Path(args.passage).read_text().strip()
    asr = _build_asr(args, passage_text)
    orchestrator = Orchestrator(LearnerProfile(age_years=args.age))
    orchestrator.load_passage(passage_text)

    print(f"Passage to read:\n\n  {passage_text}\n")
    input("Press Enter, then start reading. ")
    try:
        pcm = record_until_enter()
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print()
    _score_and_print(orchestrator, passage_text, transcribe_pcm(asr, pcm))

    if args.save_to:
        label = save_for_evaluation(args.save_to, passage_text, pcm)
        print(
            f"\nSaved the recording for evaluation. Open {label} and type what was "
            "actually read into \"said\", then run: learnling eval " + str(args.save_to)
        )
    _maybe_save_report(orchestrator, args.save_report)


def cmd_ask(args: argparse.Namespace) -> None:
    profile = LearnerProfile(age_years=args.age)
    orchestrator = Orchestrator(profile)

    utterance = _get_utterance(args)
    response = orchestrator.handle_utterance(utterance)

    print(f"Child asked:    {utterance.text}")
    print(f"learnling says: {response}")

    _maybe_save_report(orchestrator, args.save_report)


_DEMO_PASSAGE = "The cat sat on the mat. The cat had a hat. The cat ran to the mat and sat."


def cmd_demo(args: argparse.Namespace) -> None:
    passage_text = _DEMO_PASSAGE

    profile = LearnerProfile(age_years=6)
    orchestrator = Orchestrator(profile)
    orchestrator.load_passage(passage_text)

    print("=== learnling demo: a 6-year-old reading practice session ===\n")
    print(f"Passage: {passage_text}\n")

    print("-- Reading attempt 1 (one word off) --")
    utterance = SimulatedASR().transcribe("the cat sat on the hat. the cat had a hat. the cat ran to the mat and sat.")
    feedback = orchestrator.handle_utterance(utterance)
    result = orchestrator.session.events[-1]["report_notes"]["reading_result"]
    print(f"Transcript: {utterance.text}")
    print(f"Assessment: {result.assessment} (accuracy {result.accuracy:.0%})")
    print(f"learnling says: {feedback}\n")

    print("-- Reading attempt 2 (clean read) --")
    utterance = SimulatedASR().transcribe(passage_text)
    feedback = orchestrator.handle_utterance(utterance)
    result = orchestrator.session.events[-1]["report_notes"]["reading_result"]
    print(f"Transcript: {utterance.text}")
    print(f"Assessment: {result.assessment} (accuracy {result.accuracy:.0%})")
    print(f"learnling says: {feedback}\n")

    print("-- The child asks a question --")
    orchestrator.clear_passage()
    utterance = SimulatedASR().transcribe("why do cats sleep so much")
    response = orchestrator.handle_utterance(utterance)
    print(f"Child asked:    {utterance.text}")
    print(f"learnling says: {response}\n")

    print("=== Session report ===\n")
    print(generate_report(orchestrator.session))


def cmd_eval(args: argparse.Namespace) -> None:
    from learnling.evaluate import evaluate_folder, format_summary

    summary = evaluate_folder(
        args.folder,
        lambda passage: _build_asr(args, passage),
        confidence_threshold=args.confidence,
    )
    if not summary.cases:
        print(f"error: no labelled recordings (*.json) in {args.folder}", file=sys.stderr)
        raise SystemExit(1)
    print(format_summary(summary))


def cmd_live(args: argparse.Namespace) -> None:
    from learnling.asr.sherpa import SherpaStreamingASR
    from learnling import live, live_io

    passage_text = Path(args.passage).read_text().strip()
    try:
        recognizer = SherpaStreamingASR(args.model)
        voice = live_io.make_voice(args.voice, speed=0.9) if args.voice else None
    except (ImportError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    timeline: list[bytes] | None = [] if args.save_demo else None
    light = live_io.ListeningLight(args.led_pin)
    speaker = live_io.Speaker(voice, play=not args.audio, light=light, timeline=timeline)
    max_seconds = max(30.0, len(passage_text.split()) * 3.0)

    def read(label: str, path: str | None):
        if path:
            chunks = live_io.file_chunks(path)
        else:
            input(f"{label}: press Enter, then start reading. Press Enter again if you need to stop. ")
            chunks = live_io.mic_chunks(speaker, max_seconds)
        light.on()
        if timeline is not None:
            chunks = live_io.recorded(chunks, timeline)
        return chunks

    print(f"Passage:\n\n  {passage_text}\n")
    first_audio = args.audio[0] if args.audio else None
    second_audio = args.audio[-1] if args.audio else None
    result = live.run_session(
        passage_text,
        recognizer,
        read("First read", first_audio),
        _Lazy(lambda: read("Second read", second_audio)),
        speaker,
        age_years=args.age,
    )
    light.off()

    print("\nFor the adult:")
    if result.first_read_events:
        for event in result.first_read_events:
            what = "hint" if event.kind == "hint" else "said the word"
            print(f"  first read, {event.at_seconds:4.1f}s: {what} for '{event.word}'")
    else:
        print("  first read: no help needed")
    second = result.orchestrator.session.events[-1]["report_notes"]["reading_result"]
    print(f"  second read: accuracy {second.accuracy:.0%}, words correct per minute {second.wcpm or '-'}")
    if second.miscues:
        print("  words to practise: " + ", ".join(sorted({m.expected for m in second.miscues if m.expected})))

    if args.save_demo:
        live_io.write_demo(args.save_demo, timeline)
        print(f"\nWrote the reading and learnling's voice to {args.save_demo}")
    _maybe_save_report(result.orchestrator, args.save_report)


def cmd_stand(args: argparse.Namespace) -> None:
    from learnling.asr.sherpa import SherpaStreamingASR
    from learnling import buddy as buddy_mod, emailer, live, live_io, stand

    passage_text = Path(args.passage).read_text().strip()
    try:
        recognizer = SherpaStreamingASR(args.model)
        voice = live_io.PreparedVoice(
            live_io.make_voice(args.voice, speed=args.voice_speed, speaker=args.voice_id)
        ) if args.voice else None
    except (ImportError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Passage:\n\n  {passage_text}\n")
    print(f"Loading {args.llm}...")
    try:
        chat = buddy_mod.make_chat(args.llm)
        chat.warm_up()
    except Exception as exc:  # noqa: BLE001 - any failure means the model isn't usable
        hint = ("Is OPENAI_API_KEY set?" if args.llm.startswith("openai:")
                else f"Is Ollama installed, and has 'ollama pull {args.llm}' finished?")
        print(f"error: could not reach {args.llm} ({exc}). {hint}", file=sys.stderr)
        raise SystemExit(1) from exc
    buddy = buddy_mod.ReadingBuddy(passage_text, args.age, chat=chat)

    questions = _approve_questions(buddy.questions(args.questions)) if args.questions else []

    if voice is not None:
        orchestrator = Orchestrator(LearnerProfile(age_years=args.age))
        fixed = [live.orchestrator_say(orchestrator, "Say 'read' when you're ready to start.")]
        voice.prepare(fixed + [buddy.spoken(q) for q in questions] + live.lines_for_passage(passage_text, args.age))

    light = live_io.ListeningLight(args.led_pin)
    speaker = live_io.Speaker(voice, light=light)
    session = stand.run_stand(
        passage_text, recognizer,
        lambda seconds: live_io.mic_chunks(speaker, seconds, enter_stops=False),
        speaker, buddy, questions, age_years=args.age, light=light, wake=not args.no_wake,
    )
    light.off()

    body = emailer.report_text(session)
    print("\n" + body)
    if args.email_to:
        try:
            emailer.send_report(args.email_to, body)
            print(f"Emailed the report to {args.email_to}")
        except Exception as exc:  # noqa: BLE001 - the session is over; say why and keep the report
            print(f"Could not email the report: {exc}", file=sys.stderr)
    _maybe_save_report(session.orchestrator, args.save_report)


def _approve_questions(questions: list[str], prompt=input) -> list[str]:
    """The adult checks each question before the reader hears it."""
    print("\nQuestions for after the reading. Press Enter to keep one, type a new one to replace it,")
    print("or type - to drop it.")
    approved = []
    for question in questions:
        answer = prompt(f"  {question}\n  > ").strip()
        if answer == "-":
            continue
        approved.append(answer or question)
    return approved


class _Lazy:
    """An iterable built only when first iterated, so the second read waits its turn."""

    def __init__(self, make):
        self._make = make

    def __iter__(self):
        return iter(self._make())


def _add_asr_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asr",
        choices=["whisper", "vosk", "sherpa", "pasketti"],
        default="whisper",
        help="Recogniser for --audio: open Whisper, Vosk listening for the passage's words, "
        "a sherpa-onnx streaming model, or the pasketti-phonetic children's sound model (experimental)",
    )
    parser.add_argument(
        "--whisper-model", default="base.en",
        help="Whisper model size, or the folder of a converted faster-whisper model (default base.en)",
    )
    parser.add_argument("--vosk-model", help="Folder of a Vosk small model (needed for --asr vosk)")
    parser.add_argument(
        "--model",
        help="Folder of a sherpa-onnx streaming model (needed for --asr sherpa); "
        "for --asr pasketti, another copy of the model",
    )
    parser.add_argument(
        "--max-word-error", type=float, default=0.5,
        help="--asr pasketti: share of a word's sounds that may be wrong before it counts as misread (default 0.5)",
    )


def cmd_pilot(args: argparse.Namespace) -> None:
    from learnling import pilot

    try:
        if args.pilot_command == "start":
            passage_text = Path(args.passage).read_text().strip()
            pilot.run_start(args.child, passage_text, args.age, led_pin=args.led_pin)
        elif args.pilot_command == "copy":
            pilot.run_copy(args.host)
        else:
            pilot.run_label(Path(args.folder))
    except (ValueError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="learnling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read", help="Practice reading a passage aloud")
    read_parser.add_argument("--passage", required=True, help="Path to a passage text file")
    read_parser.add_argument("--age", type=int, required=True, help="Child's age in years")
    read_parser.add_argument("--simulate", help="Simulated transcript text (no audio needed)")
    read_parser.add_argument("--audio", help="Path to an audio file (requires the 'asr' extra)")
    read_parser.add_argument("--save-report", help="Write a session report to this path")
    _add_asr_flags(read_parser)
    read_parser.set_defaults(func=cmd_read)

    record_parser = subparsers.add_parser(
        "record", help="Read a passage aloud into the microphone and score it (needs the 'mic' extra)"
    )
    record_parser.add_argument("--passage", required=True, help="Path to a passage text file")
    record_parser.add_argument("--age", type=int, default=8, help="Reader's age in years (default 8)")
    record_parser.add_argument(
        "--save-to",
        help="Keep the recording and a label file in this folder, for learnling eval. "
        "Without it, no audio is kept.",
    )
    record_parser.add_argument("--save-report", help="Write a session report to this path")
    _add_asr_flags(record_parser)
    record_parser.set_defaults(func=cmd_record)

    ask_parser = subparsers.add_parser("ask", help="Ask learnling a question")
    ask_parser.add_argument("--age", type=int, required=True, help="Child's age in years")
    ask_parser.add_argument("--simulate", help="Simulated transcript text (no audio needed)")
    ask_parser.add_argument("--audio", help="Path to an audio file (requires the 'asr' extra)")
    ask_parser.add_argument("--save-report", help="Write a session report to this path")
    ask_parser.set_defaults(func=cmd_ask)

    demo_parser = subparsers.add_parser("demo", help="Run a scripted demo session, no setup needed")
    demo_parser.set_defaults(func=cmd_demo)

    live_parser = subparsers.add_parser(
        "live", help="Listen while someone reads, hint when stuck, then a quiet second read"
    )
    live_parser.add_argument("--passage", required=True, help="Path to a passage text file")
    live_parser.add_argument("--model", required=True, help="Folder of a sherpa-onnx streaming model")
    live_parser.add_argument("--voice", help="Folder of a sherpa-onnx voice, or openai:coral; without it, learnling prints instead of speaking")
    live_parser.add_argument("--age", type=int, default=8, help="Reader's age in years (default 8)")
    live_parser.add_argument(
        "--audio", action="append",
        help="Use a recording instead of the microphone (give twice for first and second read)",
    )
    live_parser.add_argument("--save-demo", help="Write the reading plus learnling's voice to this WAV")
    live_parser.add_argument("--led-pin", type=int, help="Raspberry Pi GPIO pin of the listening light")
    live_parser.add_argument("--save-report", help="Write a session report to this path")
    live_parser.set_defaults(func=cmd_live)

    stand_parser = subparsers.add_parser(
        "stand", help="A hands-free session on the book stand: started by voice, with a small model on the stand"
    )
    stand_parser.add_argument("--passage", required=True, help="Path to a passage text file")
    stand_parser.add_argument("--model", required=True, help="Folder of a sherpa-onnx streaming model")
    stand_parser.add_argument("--voice", help="Folder of a sherpa-onnx voice (VITS, Kokoro or Kitten), "
                              "or openai:coral for OpenAI's natural voice (sends only learnling's own lines)")
    stand_parser.add_argument("--voice-id", type=int, default=0, help="Speaker number in a Kokoro or Kitten voice")
    stand_parser.add_argument("--voice-speed", type=float, default=0.95, help="Speaking speed (default 0.95)")
    stand_parser.add_argument("--llm", default="gemma3:1b", help="Ollama model on the stand (default gemma3:1b), or openai:MODEL to use "
                              "OpenAI's cloud (sends the reader's words as text; check the consent form)")
    stand_parser.add_argument("--age", type=int, default=8, help="Reader's age in years (default 8)")
    stand_parser.add_argument("--questions", type=int, default=2, help="Story questions after reading (default 2)")
    stand_parser.add_argument("--no-wake", action="store_true", help="Start straight away, without waiting for \"I'm ready\"")
    stand_parser.add_argument("--led-pin", type=int, help="Raspberry Pi GPIO pin of the listening light")
    stand_parser.add_argument("--email-to", help="Email the report here (needs LEARNLING_SMTP_USER and LEARNLING_SMTP_PASSWORD)")
    stand_parser.add_argument("--save-report", help="Write a session report to this path")
    stand_parser.set_defaults(func=cmd_stand)

    pilot_parser = subparsers.add_parser(
        "pilot", help="Record-only sessions for the family pilot (see docs/raspberry-pi.md)"
    )
    pilot_sub = pilot_parser.add_subparsers(dest="pilot_command", required=True)
    start_parser = pilot_sub.add_parser(
        "start", help="On the stand: record a child reading, with no hints or score"
    )
    start_parser.add_argument("child", help="Child code such as child03, never a name")
    start_parser.add_argument("--passage", required=True, help="Path to a passage text file")
    start_parser.add_argument("--age", type=int, required=True, help="Child's age in years")
    start_parser.add_argument("--led-pin", type=int, help="Raspberry Pi GPIO pin of the listening light")
    copy_parser = pilot_sub.add_parser(
        "copy", help="On the laptop: move all recordings off the stand, checking each one"
    )
    copy_parser.add_argument("host", help="The stand's SSH address, such as pi@learnling.local")
    label_parser = pilot_sub.add_parser(
        "label", help="On the laptop: listen to each reading and type what was said"
    )
    label_parser.add_argument("folder", help="One child's folder, such as ~/learnling-pilot/child03")
    pilot_parser.set_defaults(func=cmd_pilot)

    eval_parser = subparsers.add_parser(
        "eval", help="Score a folder of labelled recordings (see docs/audio-evaluation.md)"
    )
    eval_parser.add_argument("folder", help="Folder of .wav recordings with .json labels")
    eval_parser.add_argument(
        "--confidence", type=float, help="Override the miscue confidence threshold"
    )
    _add_asr_flags(eval_parser)
    eval_parser.set_defaults(func=cmd_eval)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
