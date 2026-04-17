from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


class MinerUUnavailableError(RuntimeError):
    """Raised when the MinerU backend is unavailable."""


@dataclass(frozen=True)
class MinerUResult:
    markdown: str
    output_dir: Path
    json_payload: dict
    warnings: list[str]


class CliMinerUBackend:
    def __init__(self, binary: str = "mineru"):
        self.binary = binary

    def build_command(self, source_file: str | Path, output_dir: str | Path) -> list[str]:
        source = Path(source_file)
        destination = Path(output_dir)
        return [self.binary, "parse", str(source), "--output-dir", str(destination)]

    def parse_document(self, source_file: str | Path, output_dir: str | Path) -> MinerUResult:
        if shutil.which(self.binary) is None:
            raise MinerUUnavailableError(
                f"MinerU binary '{self.binary}' is not available on PATH"
            )
        raise NotImplementedError("MinerU execution will be added in a later task")

    def _build_result(
        self,
        *,
        markdown: str,
        output_dir: str | Path,
        json_payload: dict,
        warnings: list[str] | None = None,
    ) -> MinerUResult:
        return MinerUResult(
            markdown=markdown,
            output_dir=Path(output_dir),
            json_payload=json_payload,
            warnings=list(warnings or []),
        )
