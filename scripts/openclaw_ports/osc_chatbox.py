"""Ported from clawdbot-main/scripts/tools — run via: py -3 scripts/openclaw_ports/<name>"""

#!/usr/bin/env python3
"""
VRChat OSC chatbox bridge.

Usage:
  osc_chatbox.py <message> [--host HOST] [--port PORT] [--no-sfx]
  osc_chatbox.py --raw <address> <value> [--host HOST] [--port PORT]
"""
import argparse
import sys

# Windows cp932 console cannot print emoji/non-ASCII without explicit UTF-8.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from pythonosc import udp_client
except ImportError:
    print("ERROR: python-osc is not installed. Run: py -3 -m pip install python-osc", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="VRChat OSC chatbox bridge")
    parser.add_argument("message", nargs="?", help="Chatbox message text")
    parser.add_argument(
        "--raw",
        nargs=2,
        metavar=("ADDRESS", "VALUE"),
        help="Send raw OSC message instead of chatbox",
    )
    parser.add_argument("--host", default="127.0.0.1", help="OSC host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9000, help="OSC port (default: 9000)")
    parser.add_argument(
        "--no-sfx", action="store_true", dest="no_sfx", help="Suppress notification sound"
    )
    args = parser.parse_args()

    client = udp_client.SimpleUDPClient(args.host, args.port)

    if args.raw:
        address, raw_value = args.raw
        # Type inference: bool -> int -> float -> str
        if raw_value.lower() == "true":
            value: bool | int | float | str = True
        elif raw_value.lower() == "false":
            value = False
        else:
            try:
                value = int(raw_value)
            except ValueError:
                try:
                    value = float(raw_value)
                except ValueError:
                    value = raw_value
        client.send_message(address, value)
        print(f"OSC sent: {address} -> {value}")
    else:
        if not args.message:
            parser.error("message is required in chatbox mode")
        sfx = not args.no_sfx
        # VRChat /chatbox/input: (string message, bool isImmediate, bool sfx)
        client.send_message("/chatbox/input", [args.message, True, sfx])
        print(f"Chatbox sent ({len(args.message)} chars): {args.message[:40]}")


if __name__ == "__main__":
    main()
