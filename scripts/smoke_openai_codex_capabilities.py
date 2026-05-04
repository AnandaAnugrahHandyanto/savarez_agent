#!/usr/bin/env python3
"""Smoke-test OpenAI Codex Plan/OAuth models through Hermes.

This script intentionally uses provider='openai-codex' and Hermes auth (usually
~/.hermes/auth.json / credential_pool.openai-codex). It does not read or require
a direct OPENAI_API_KEY.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.auxiliary_client import call_llm, extract_content_or_reasoning  # noqa: E402

# 32x32 red PNG generated with Python stdlib. Earlier 1x1 probes were rejected
# by the Codex image validator as invalid/too small.
_RED_32_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKElEQVR4nO3NsQ0AAAzCMP5/"
    "un0CNkuZ41wybXsHAAAAAAAAAAAAxR4yw/wuPL6QkAAAAABJRU5ErkJggg=="
)

DEFAULT_MODELS = ["gpt-5.5", "gpt-5.4-mini", "gpt-5.3-codex"]
FEATURES = ("text", "tools", "structured", "vision")


@dataclass
class SmokeResult:
    model: str
    feature: str
    ok: bool
    detail: str
    started_at: str
    finished_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _messages_for(feature: str) -> list[dict[str, Any]]:
    if feature == "vision":
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What dominant color is in this 32x32 image? Answer one word."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_RED_32_PNG}"},
                    },
                ],
            }
        ]
    return [{"role": "user", "content": "Reply with exactly: codex-smoke-ok"}]


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "record_smoke_result",
                "description": "Record the smoke-test sentinel.",
                "parameters": {
                    "type": "object",
                    "properties": {"sentinel": {"type": "string"}},
                    "required": ["sentinel"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def _extra_body(feature: str) -> dict[str, Any] | None:
    if feature != "structured":
        return None
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "codex_smoke",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"status": {"type": "string", "enum": ["codex-smoke-ok"]}},
                    "required": ["status"],
                    "additionalProperties": False,
                },
            },
        }
    }


def run_one(model: str, feature: str, timeout: float) -> SmokeResult:
    started = _now()
    try:
        response = call_llm(
            provider="openai-codex",
            model=model,
            task="vision" if feature == "vision" else "codex_smoke",
            messages=_messages_for(feature),
            max_tokens=64,
            temperature=None,
            tools=_tools() if feature == "tools" else None,
            timeout=timeout,
            extra_body=_extra_body(feature),
        )
        content = extract_content_or_reasoning(response)
        if feature == "tools":
            tool_calls = getattr(response.choices[0].message, "tool_calls", None)
            detail = f"tool_calls={len(tool_calls or [])}; content={content[:120]!r}"
            ok = bool(tool_calls)
        elif feature == "structured":
            parsed = json.loads(content)
            ok = parsed.get("status") == "codex-smoke-ok"
            detail = content[:240]
        else:
            ok = bool(content.strip())
            detail = content[:240]
    except Exception as exc:  # deliberately report provider/model errors verbatim-ish, no secrets
        ok = False
        detail = f"{type(exc).__name__}: {str(exc)[:500]}"
    return SmokeResult(model, feature, ok, detail, started, _now())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", dest="models", help="Model to test; repeatable.")
    parser.add_argument("--feature", choices=FEATURES, action="append", dest="features", help="Feature to test; repeatable.")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()

    models = args.models or DEFAULT_MODELS
    features = args.features or list(FEATURES)
    results = [run_one(model, feature, args.timeout) for model in models for feature in features]

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            status = "PASS" if result.ok else "FAIL"
            print(f"{status} {result.model} {result.feature}: {result.detail}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
