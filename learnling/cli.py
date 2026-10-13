"""The learnling command-line interface.

    python -m learnling read --passage passages/sample_level1.txt --age 6 --simulate "the cat sat on teh mat"
    python -m learnling read --passage passages/sample_level1.txt --age 6 --audio recording.wav   # requires [asr]
    python -m learnling read --passage passages/sample_level1.txt --age 6 --audio recording.wav --asr vosk --vosk-model PATH
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


def _add_asr_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asr",
        choices=["whisper", "vosk"],
        default="whisper",
        help="Recogniser for --audio: open Whisper, or Vosk listening for the passage's words",
    )
    parser.add_argument("--whisper-model", default="base.en", help="Whisper model size (default base.en)")
    parser.add_argument("--vosk-model", help="Folder of a Vosk small model (needed for --asr vosk)")


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

    ask_parser = subparsers.add_parser("ask", help="Ask learnling a question")
    ask_parser.add_argument("--age", type=int, required=True, help="Child's age in years")
    ask_parser.add_argument("--simulate", help="Simulated transcript text (no audio needed)")
    ask_parser.add_argument("--audio", help="Path to an audio file (requires the 'asr' extra)")
    ask_parser.add_argument("--save-report", help="Write a session report to this path")
    ask_parser.set_defaults(func=cmd_ask)

    demo_parser = subparsers.add_parser("demo", help="Run a scripted demo session, no setup needed")
    demo_parser.set_defaults(func=cmd_demo)

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
