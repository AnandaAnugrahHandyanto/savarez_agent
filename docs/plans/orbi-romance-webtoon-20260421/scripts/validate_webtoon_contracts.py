from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from webtoon_contracts import validate_episode_contracts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Orbi romance webtoon hard contracts.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    errors = validate_episode_contracts(project_root=project_root, episode=args.episode, strict=args.strict)
    payload = {
        "project_root": str(project_root),
        "episode": args.episode,
        "strict": args.strict,
        "ok": not errors,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
