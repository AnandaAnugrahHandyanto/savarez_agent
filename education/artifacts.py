from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from education.paths import artifacts_root

_SUPPORTED_SOURCE_SUFFIXES = {".pdf", ".docx"}
_SUPPORTED_ARTIFACT_KINDS = {"raw", "mineru", "normalized", "wiki", "exports"}


@dataclass(frozen=True)
class StoredArtifact:
    kind: str
    path: Path
    sha256: str
    original_filename: str | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.replace("\x00", "")
    if not name or name in {".", ".."}:
        raise ValueError("Invalid artifact filename")
    return name


class ArtifactStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else artifacts_root()

    def store_source_file(self, source_path: str | Path) -> StoredArtifact:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(str(source))
        suffix = source.suffix.lower()
        if suffix not in _SUPPORTED_SOURCE_SUFFIXES:
            raise ValueError(f"Unsupported source file type: {suffix or '<none>'}")

        digest = _sha256_file(source)
        destination_dir = self.root / "raw" / digest[:16]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"source{suffix}"
        if not destination.exists():
            shutil.copy2(source, destination)

        return StoredArtifact(
            kind="raw",
            path=destination,
            sha256=digest,
            original_filename=source.name,
        )

    def write_named_artifact(
        self,
        *,
        kind: str,
        artifact_id: str,
        filename: str,
        content: str,
    ) -> StoredArtifact:
        if kind not in _SUPPORTED_ARTIFACT_KINDS:
            raise ValueError(f"Unsupported artifact kind: {kind}")
        safe_filename = _safe_filename(filename)
        safe_artifact_id = _safe_filename(artifact_id)
        destination_dir = self.root / kind / safe_artifact_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / safe_filename
        destination.write_text(content, encoding="utf-8")
        return StoredArtifact(
            kind=kind,
            path=destination,
            sha256=_sha256_text(content),
            original_filename=safe_filename,
        )
