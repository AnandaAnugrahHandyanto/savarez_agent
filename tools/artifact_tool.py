"""Artifact presentation tool.

Registers generated content or a local file as an immutable Dashboard artifact
under HERMES_HOME/artifacts and returns structured metadata for the Artifacts
viewer.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from tools.registry import registry, tool_error

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover - isolated import fallback
    def get_hermes_home() -> Path:  # type: ignore[misc]
        val = (os.environ.get("HERMES_HOME") or "").strip()
        return Path(val) if val else Path.home() / ".hermes"


ARTIFACT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
_SECRET_FILENAMES = {".env", ".secret", "id_rsa", "id_ed25519", "known_hosts"}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
_DEFAULT_FILENAME_BY_TYPE = {
    "text/html": "index.html",
    "image/svg+xml": "index.svg",
    "text/markdown": "index.md",
    "application/vnd.mermaid": "diagram.mmd",
    "application/json": "data.json",
    "text/plain": "artifact.txt",
}


ARTIFACT_PRESENT_SCHEMA = {
    "name": "artifact_present",
    "description": (
        "Register generated content or an existing local file as a local Hermes artifact. "
        "Writes under HERMES_HOME/artifacts, creates a versioned manifest, and returns "
        "structured metadata including preview URL for the Artifacts dashboard."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Human-readable artifact title"},
            "artifact_id": {"type": "string", "description": "Optional stable id; generated from title when omitted"},
            "content": {"type": "string", "description": "Generated content to store. Mutually exclusive with source_path."},
            "source_path": {"type": "string", "description": "Existing local file to copy. Mutually exclusive with content."},
            "filename": {"type": "string", "description": "Output filename inside the artifact version directory"},
            "content_type": {"type": "string", "description": "MIME/content type, e.g. text/html or image/svg+xml"},
            "description": {"type": "string", "description": "Optional artifact description"},
        },
        "required": [],
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps({"success": True, **payload}, ensure_ascii=False)


def _err(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value)
    value = re.sub(r"[-_.]{2,}", "-", value).strip("-_.")
    return value or "artifact"


def _artifact_id(title: str | None, artifact_id: str | None) -> str:
    candidate = _slugify(artifact_id or title or "artifact")
    if not ARTIFACT_ID_RE.fullmatch(candidate):
        raise ValueError("invalid artifact_id")
    return candidate


def _decode_path(value: str) -> str:
    decoded = value or ""
    for _ in range(3):
        nxt = unquote(decoded)
        if nxt == decoded:
            break
        decoded = nxt
    return decoded.replace("\\", "/")


def _is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in _SECRET_FILENAMES or any(lowered.endswith(suffix) for suffix in _SECRET_SUFFIXES)


def _safe_filename(filename: str) -> str:
    decoded = _decode_path(filename).strip()
    if not decoded:
        raise ValueError("filename cannot be empty")
    if decoded.startswith("/") or decoded.startswith("~"):
        raise ValueError("absolute filenames are not allowed")
    parts = [part for part in decoded.split("/") if part not in {"", "."}]
    if not parts:
        raise ValueError("filename cannot be empty")
    for part in parts:
        if part == "..":
            raise ValueError("filename traversal is not allowed")
        if part.startswith("."):
            raise ValueError("dotfiles are not allowed")
        if _is_secret_name(part):
            raise ValueError("secret-looking filenames are not allowed")
    return "/".join(parts)


def _resolve_source_path(source_path: str, task_id: str = "default") -> Path:
    raw = Path(source_path).expanduser()
    if not raw.is_absolute():
        base = os.environ.get("TERMINAL_CWD") or os.getcwd()
        raw = Path(base) / raw
    # Reject symlink inputs even if they resolve inside the same tree. The tool
    # should copy exactly the file the user names, not follow surprise portals.
    if raw.is_symlink():
        raise ValueError("symlink sources are not allowed")
    resolved = raw.resolve()
    if not resolved.exists():
        raise FileNotFoundError(str(source_path))
    if not resolved.is_file():
        raise ValueError("source_path must be a regular file")
    if resolved.name.startswith("."):
        raise ValueError("dotfile sources are not allowed")
    if _is_secret_name(resolved.name):
        raise ValueError("secret-looking source files are not allowed")
    return resolved


def _guess_content_type(filename: str, content_type: str | None = None) -> str:
    if content_type:
        return content_type
    guessed, _ = mimetypes.guess_type(filename)
    if filename.endswith(".md"):
        return "text/markdown"
    return guessed or "text/plain"


def _default_filename(content_type: str | None, source: Path | None = None) -> str:
    if source is not None:
        return source.name
    return _DEFAULT_FILENAME_BY_TYPE.get(content_type or "", "index.html")


def _artifact_root() -> Path:
    return get_hermes_home() / "artifacts"


def _load_manifest(manifest_path: Path, artifact_id: str, title: str, description: str, content_type: str) -> dict[str, Any]:
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("id") == artifact_id:
                data.setdefault("versions", [])
                return data
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    now = _now()
    return {
        "id": artifact_id,
        "title": title,
        "description": description,
        "contentType": content_type,
        "latestVersion": 0,
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }


def _next_version(manifest: dict[str, Any]) -> int:
    versions = manifest.get("versions") if isinstance(manifest.get("versions"), list) else []
    nums: list[int] = []
    for row in versions:
        if isinstance(row, dict):
            try:
                nums.append(int(row.get("version", 0)))
            except (TypeError, ValueError):
                pass
    try:
        nums.append(int(manifest.get("latestVersion", 0)))
    except (TypeError, ValueError):
        pass
    return max(nums or [0]) + 1


def _write_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def artifact_present(
    *,
    title: str | None = None,
    artifact_id: str | None = None,
    content: str | None = None,
    source_path: str | None = None,
    filename: str | None = None,
    content_type: str | None = None,
    description: str | None = None,
    task_id: str = "default",
) -> str:
    """Register content or a source file as a versioned Hermes artifact."""

    try:
        has_content = content is not None
        has_source = bool(source_path)
        if has_content == has_source:
            return _err("Provide exactly one of content or source_path")
        resolved_source: Path | None = None
        if has_source:
            resolved_source = _resolve_source_path(str(source_path), task_id=task_id)
        effective_content_type = _guess_content_type(
            filename or (resolved_source.name if resolved_source else ""),
            content_type,
        )
        effective_filename = _safe_filename(filename or _default_filename(effective_content_type, resolved_source))
        aid = _artifact_id(title, artifact_id)
        effective_title = title or aid
        effective_description = description or ""

        root = _artifact_root()
        artifact_dir = root / aid
        manifest_path = artifact_dir / "manifest.json"
        manifest = _load_manifest(manifest_path, aid, effective_title, effective_description, effective_content_type)
        version = _next_version(manifest)
        version_dir = artifact_dir / "versions" / str(version)
        target = version_dir / effective_filename
        resolved_version_dir = version_dir.resolve(strict=False)
        resolved_target = target.resolve(strict=False)
        try:
            resolved_target.relative_to(resolved_version_dir)
        except ValueError as exc:
            raise ValueError("target path escapes artifact version directory") from exc

        version_dir.mkdir(parents=True, exist_ok=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        if resolved_source is not None:
            shutil.copyfile(resolved_source, target)
        else:
            target.write_text(content or "", encoding="utf-8")

        now = _now()
        manifest["title"] = effective_title
        manifest["description"] = effective_description
        manifest["contentType"] = effective_content_type
        manifest["latestVersion"] = version
        manifest["updatedAt"] = now
        versions = manifest.setdefault("versions", [])
        if not isinstance(versions, list):
            versions = []
            manifest["versions"] = versions
        versions.append({
            "version": version,
            "entrypoint": effective_filename,
            "contentType": effective_content_type,
            "createdAt": now,
            "source": "file" if resolved_source is not None else "content",
        })
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_manifest(manifest_path, manifest)

        url = f"/api/plugins/artifacts/preview/{aid}/versions/{version}/{effective_filename}"
        artifact = {
            "id": aid,
            "version": version,
            "title": effective_title,
            "description": effective_description,
            "contentType": effective_content_type,
            "path": str(target),
            "manifestPath": str(manifest_path),
            "url": url,
        }
        return _ok({"artifact": artifact})
    except Exception as exc:
        return _err(str(exc))


def _handle_artifact_present(args, **kw):
    tid = kw.get("task_id") or "default"
    return artifact_present(
        title=args.get("title"),
        artifact_id=args.get("artifact_id"),
        content=args.get("content") if "content" in args else None,
        source_path=args.get("source_path"),
        filename=args.get("filename"),
        content_type=args.get("content_type"),
        description=args.get("description"),
        task_id=tid,
    )


def _check_artifact_reqs() -> bool:
    return True


registry.register(
    name="artifact_present",
    toolset="artifacts",
    schema=ARTIFACT_PRESENT_SCHEMA,
    handler=_handle_artifact_present,
    check_fn=_check_artifact_reqs,
    emoji="🖼️",
    max_result_size_chars=20_000,
)
