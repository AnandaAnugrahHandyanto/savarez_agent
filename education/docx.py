from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class DocxPreparationError(RuntimeError):
    """Raised when a DOCX file cannot yet be prepared for MinerU."""


@dataclass(frozen=True)
class PreparedDocx:
    source_path: Path
    output_dir: Path
    converter: str | None


def prepare_for_mineru(source_path: str | Path, output_dir: str | Path) -> PreparedDocx:
    source = Path(source_path)
    destination = Path(output_dir)
    if source.suffix.lower() != ".docx":
        raise DocxPreparationError(
            f"Expected a .docx file for DOCX preparation, got: {source}"
        )
    raise DocxPreparationError(
        f"DOCX file {source} requires a converter seam before MinerU preparation can continue. "
        "Configure a DOCX converter backend first."
    )
