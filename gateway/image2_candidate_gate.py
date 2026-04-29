"""Hermes-owned Image2 candidate freshness and SHA gate.

This module is deliberately small and local-only. It evaluates candidate image
files already present in a Hermes-owned job directory and refuses exact source
echoes, known historical/gallery images, and candidates whose file mtime predates
an explicit generation start/cutoff. It does not open a browser, call OpenCLI,
review pixels with Gemini, or send anything to Feishu.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SOURCE_PATH_KEYS = {"path", "local_path", "file_path", "source_path", "abs_path"}
SHA_KEYS = {"sha256", "sha", "image_sha256", "source_sha256", "file_sha256"}
HISTORY_FILES = (
    "history_sha256.json",
    "historical_sha256.json",
    "history_shas.json",
    "historical_candidates.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_sha(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if SHA256_RE.match(text):
        return text
    return None


def _iter_known_shas(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        sha = _normalize_sha(value)
        if sha:
            yield sha
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in SHA_KEYS or "sha256" in key_text:
                if isinstance(child, (list, tuple, set, dict)):
                    yield from _iter_known_shas(child)
                else:
                    sha = _normalize_sha(child)
                    if sha:
                        yield sha
            else:
                yield from _iter_known_shas(child)
        return
    if isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _iter_known_shas(child)


def _source_sha256(job_dir: Path) -> list[str]:
    manifest = _load_json(job_dir / "source_manifest.json")
    shas: set[str] = set(_iter_known_shas(manifest))

    def add_path_sha(value: Any) -> None:
        if isinstance(value, (str, os.PathLike)):
            path = Path(str(value)).expanduser()
            if path.is_file():
                shas.add(sha256_file(path))
            return
        if not isinstance(value, Mapping):
            return
        for key, child in value.items():
            if str(key).lower() in SOURCE_PATH_KEYS:
                path = Path(str(child)).expanduser()
                if path.is_file():
                    shas.add(sha256_file(path))
            elif isinstance(child, Mapping):
                add_path_sha(child)
            elif isinstance(child, list):
                for item in child:
                    add_path_sha(item)

    if isinstance(manifest, list):
        for item in manifest:
            add_path_sha(item)
    elif isinstance(manifest, Mapping):
        add_path_sha(manifest)
    return sorted(shas)


def _historical_sha256(job_dir: Path) -> list[str]:
    shas: set[str] = set()
    for name in HISTORY_FILES:
        value = _load_json(job_dir / name)
        if value is not None:
            shas.update(_iter_known_shas(value))
    message = _load_json(job_dir / "message.json")
    if isinstance(message, Mapping):
        for key in (
            "history_sha256",
            "historical_sha256",
            "historical_candidate_sha256",
            "historical_image_sha256",
            "history_hashes",
            "historical_candidates",
            "previous_candidate_sha256",
        ):
            if key in message:
                shas.update(_iter_known_shas(message.get(key)))
    return sorted(shas)


def _parse_generated_after(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except ValueError:
            return None


def _candidate_image_paths(job_dir: Path, candidate_paths: Sequence[Path | str] | None) -> list[Path]:
    if candidate_paths is None:
        candidate_root = job_dir / "candidates"
        paths = list(candidate_root.rglob("*")) if candidate_root.is_dir() else []
    else:
        paths = [Path(path) for path in candidate_paths]
    images = [path for path in paths if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
    return sorted(images, key=lambda path: (path.stat().st_mtime, path.name), reverse=True)


def _candidate_record(path: Path, generated_after: datetime | None, source_shas: set[str], historical_shas: set[str]) -> dict[str, Any]:
    digest = sha256_file(path)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    reasons: list[str] = []
    if digest in source_shas:
        reasons.append("source_sha_match")
    if digest in historical_shas:
        reasons.append("historical_sha_match")
    if generated_after is not None and mtime < generated_after:
        reasons.append("stale_mtime_before_generation_start")
    return {
        "path": str(path),
        "sha256": digest,
        "mtime": mtime.isoformat(),
        "decision": "reject" if reasons else "pass",
        "reasons": reasons,
    }


def evaluate_candidate_gate(
    *,
    job_dir: Path,
    candidate_paths: Sequence[Path | str] | None = None,
    generated_after: datetime | str | int | float | None = None,
    write_result: bool = True,
) -> dict[str, Any]:
    """Evaluate local candidate images for first-pass freshness/SHA safety.

    ``generated_after`` is intentionally explicit. Callers that know the worker
    claim or generation start time should pass it; otherwise this gate still
    blocks exact source echoes and historical/gallery SHA reuse.
    """
    root = Path(job_dir)
    source_shas = set(_source_sha256(root))
    historical_shas = set(_historical_sha256(root))
    cutoff = _parse_generated_after(generated_after)
    decisions = [
        _candidate_record(path, cutoff, source_shas, historical_shas)
        for path in _candidate_image_paths(root, candidate_paths)
    ]
    accepted = next((item for item in decisions if item["decision"] == "pass"), None)
    if accepted:
        status = "pass"
    elif decisions:
        status = "rejected"
    else:
        status = "no_candidates"
    result = {
        "status": status,
        "accepted": accepted,
        "decisions": decisions,
        "source_sha256": sorted(source_shas),
        "historical_sha256": sorted(historical_shas),
        "generated_after": cutoff.isoformat() if cutoff is not None else None,
    }
    if write_result:
        root.mkdir(parents=True, exist_ok=True)
        (root / "candidate_gate_result.json").write_text(_safe_json(result), encoding="utf-8")
    return result
