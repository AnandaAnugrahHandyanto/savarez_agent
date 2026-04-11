#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path


def run_hermes(command: str) -> dict:
    import subprocess
    start = time.time()
    proc = subprocess.run(['bash', '-lc', command], text=True, capture_output=True)
    return {
        'command': command,
        'exit_code': proc.returncode,
        'duration_seconds': round(time.time() - start, 2),
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Compare Gemini native provider vs custom/CAPI lane in Hermes.')
    parser.add_argument('--model', default='gemini-3-flash-preview', help='Gemini model to compare')
    parser.add_argument('--query', default='Reply with exactly: gemini-ok', help='Query to run')
    args = parser.parse_args()

    native_cmd = (
        f"source venv/bin/activate && hermes chat -Q --provider gemini -m {args.model!s} -q {json.dumps(args.query)}"
    )
    capi_cmd = (
        f"source venv/bin/activate && hermes chat -Q --provider custom -m {args.model!s} -q {json.dumps(args.query)}"
    )

    native = run_hermes(native_cmd)
    capi = run_hermes(capi_cmd)

    out = {
        'model': args.model,
        'query': args.query,
        'native_gemini': native,
        'custom_capi': capi,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
