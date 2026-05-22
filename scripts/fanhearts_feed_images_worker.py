#!/usr/bin/env python3
"""Process queued Fanhearts feed image jobs.

Environment:
  FANHEARTS_FEED_IMAGES_API_BASE_URL  default https://dev-api.fanhearts.com
  FANHEARTS_FEED_IMAGES_JWT           required JWT bearer token
  FANHEARTS_FEED_IMAGES_LIMIT         default 1
  FAL_KEY or managed Nous FAL gateway required for gpt-image-2 generation
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.feed_images import (  # noqa: E402
    DEFAULT_API_BASE_URL,
    process_queued_feed_images_sync,
)


def main() -> int:
    api_base_url = os.getenv("FANHEARTS_FEED_IMAGES_API_BASE_URL", DEFAULT_API_BASE_URL)
    jwt = os.getenv("FANHEARTS_FEED_IMAGES_JWT", "").strip()
    limit_raw = os.getenv("FANHEARTS_FEED_IMAGES_LIMIT", "1").strip()
    try:
        limit = max(1, int(limit_raw))
    except ValueError:
        limit = 1

    summary = process_queued_feed_images_sync(
        api_base_url=api_base_url,
        jwt=jwt,
        limit=limit,
        workdir=Path.home() / ".hermes" / "work" / "fanhearts-feed-images",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary.get("failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
