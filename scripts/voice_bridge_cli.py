#!/usr/bin/env python3
"""CLI for OpenClaw voice bridge (harness HTTP preferred)."""

from __future__ import annotations

import argparse
import json
import sys

from tools.openclaw.voice_bridge import list_audio_devices, voice_stack_status, voice_test_say, voice_turn


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes OpenClaw voice bridge CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show voice stack availability")
    sub.add_parser("devices", help="List audio devices")

    turn = sub.add_parser("turn", help="Record + transcribe + reply (harness)")
    turn.add_argument("--seconds", type=float, default=5.0)
    turn.add_argument("--emotion", default="neutral")
    turn.add_argument("--speaker", type=int, default=8)

    say = sub.add_parser("say", help="Speak text via harness VOICEVOX")
    say.add_argument("text")
    say.add_argument("--emotion", default="neutral")
    say.add_argument("--speaker", type=int, default=8)

    args = parser.parse_args()
    if args.command == "status":
        out = voice_stack_status()
    elif args.command == "devices":
        out = list_audio_devices()
    elif args.command == "turn":
        out = voice_turn(
            record_seconds=args.seconds,
            emotion=args.emotion,
            speaker=args.speaker,
        )
    else:
        out = voice_test_say(args.text, emotion=args.emotion, speaker=args.speaker)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("success") is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
