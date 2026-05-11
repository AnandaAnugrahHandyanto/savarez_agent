"""Filesystem store for Hermes Dashboard artifacts.

Phase 1 is intentionally read-only: it discovers artifact manifests under a
Hermes-controlled root and resolves preview file paths without allowing path
traversal, symlink escapes, or dotfile/secret exposure.
"""
from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover - defensive fallback for isolated tests
    import os as _os

    def get_hermes_home() -> Path:  # type: ignore[misc]
        val = (_os.environ.get("HERMES_HOME") or "").strip()
        return Path(val) if val else Path.home() / ".hermes"


ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DEFAULT_CSP = (
    "default-src 'none'; "
    "script-src 'unsafe-inline' 'unsafe-eval' data: blob:; "
    "style-src 'unsafe-inline' data:; "
    "img-src data: blob:; "
    "font-src data:; "
    "connect-src 'none'; "
    "media-src data: blob:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'self'"
)


class ArtifactStoreError(ValueError):
    """Raised when an artifact manifest or path is unsafe/invalid."""


def artifact_root() -> Path:
    """Return the profile-aware artifact root."""

    return get_hermes_home() / "artifacts"


def _safe_artifact_id(artifact_id: str) -> str:
    if not ARTIFACT_ID_RE.fullmatch(artifact_id or ""):
        raise ArtifactStoreError("invalid artifact id")
    return artifact_id


def _read_manifest(manifest_path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    artifact_id = data.get("id")
    if not isinstance(artifact_id, str):
        artifact_id = manifest_path.parent.name
    try:
        _safe_artifact_id(artifact_id)
    except ArtifactStoreError:
        return None
    data["id"] = artifact_id
    return data


def _version_entry(manifest: dict[str, Any], version: int | None = None) -> dict[str, Any]:
    versions = manifest.get("versions")
    if not isinstance(versions, list):
        versions = []
    if version is None:
        latest = manifest.get("latestVersion") or manifest.get("latest_version") or 1
        try:
            version = int(latest)
        except (TypeError, ValueError):
            version = 1
    for row in versions:
        if not isinstance(row, dict):
            continue
        try:
            if int(row.get("version", -1)) == version:
                return row
        except (TypeError, ValueError):
            continue
    return {"version": version, "entrypoint": "index.html", "contentType": manifest.get("contentType", "text/html")}


def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    artifact_id = _safe_artifact_id(str(manifest.get("id", "")))
    latest = _version_entry(manifest)
    version = int(latest.get("version", manifest.get("latestVersion") or 1))
    entrypoint = str(latest.get("entrypoint") or "index.html")
    content_type = str(latest.get("contentType") or manifest.get("contentType") or "text/html")
    return {
        "id": artifact_id,
        "title": manifest.get("title") or artifact_id,
        "description": manifest.get("description") or "",
        "contentType": content_type,
        "latestVersion": version,
        "createdAt": manifest.get("createdAt"),
        "updatedAt": manifest.get("updatedAt"),
        "versions": manifest.get("versions") if isinstance(manifest.get("versions"), list) else [latest],
        "previewUrl": f"/api/plugins/artifacts/preview/{artifact_id}/versions/{version}/{entrypoint}",
    }


def list_artifacts(root: Path | None = None) -> list[dict[str, Any]]:
    """List public artifact manifest summaries from the controlled root."""

    root = root or artifact_root()
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            _safe_artifact_id(child.name)
        except ArtifactStoreError:
            continue
        manifest = _read_manifest(child / "manifest.json")
        if not manifest:
            continue
        if manifest["id"] != child.name:
            # Keep ids directory-scoped; no alias tricks through manifests.
            continue
        try:
            out.append(_public_manifest(manifest))
        except (ArtifactStoreError, TypeError, ValueError):
            continue
    return out


def get_artifact(artifact_id: str, root: Path | None = None) -> dict[str, Any]:
    root = root or artifact_root()
    safe_id = _safe_artifact_id(artifact_id)
    manifest = _read_manifest(root / safe_id / "manifest.json")
    if not manifest or manifest.get("id") != safe_id:
        raise FileNotFoundError(safe_id)
    return _public_manifest(manifest)


def _decode_path(value: str) -> str:
    decoded = value or ""
    # Decode repeatedly enough to catch common double-encoding, without a cute
    # infinite loop. Cute infinite loops are still infinite loops.
    for _ in range(3):
        nxt = unquote(decoded)
        if nxt == decoded:
            break
        decoded = nxt
    return decoded.replace("\\", "/")


def _reject_unsafe_parts(decoded_path: str) -> None:
    if decoded_path.startswith("/") or decoded_path.startswith("~"):
        raise ArtifactStoreError("absolute preview paths are not allowed")
    parts = [part for part in decoded_path.split("/") if part not in {"", "."}]
    if not parts:
        raise ArtifactStoreError("empty preview path")
    for part in parts:
        if part == "..":
            raise ArtifactStoreError("path traversal is not allowed")
        if part.startswith("."):
            raise ArtifactStoreError("dotfiles are not served")
        lowered = part.lower()
        if lowered in {".env", "id_rsa", "id_ed25519"} or lowered.endswith((".pem", ".key")):
            raise ArtifactStoreError("secret-looking files are not served")


def resolve_preview_path(artifact_id: str, version: int, file_path: str, root: Path | None = None) -> Path:
    """Resolve a preview file path and prove it stays inside the version dir."""

    if version < 1:
        raise ArtifactStoreError("invalid artifact version")
    root = (root or artifact_root()).resolve()
    safe_id = _safe_artifact_id(artifact_id)
    decoded = _decode_path(file_path)
    _reject_unsafe_parts(decoded)

    base = (root / safe_id / "versions" / str(version)).resolve()
    candidate = (base / decoded).resolve()
    try:
        candidate.relative_to(base)
        base.relative_to(root)
    except ValueError as exc:
        raise ArtifactStoreError("preview path escapes artifact root") from exc
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(decoded)
    # If candidate was a symlink to inside base, resolve() above has normalized it.
    # If it pointed outside, relative_to(base) already rejected it.
    return candidate


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"
