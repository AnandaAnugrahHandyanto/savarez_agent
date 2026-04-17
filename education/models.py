from dataclasses import dataclass
from enum import StrEnum


class DocumentSourceType(StrEnum):
    LOCAL_FILE = "local_file"
    FEISHU = "feishu"
    WATCH_FOLDER = "watch_folder"


class IngestStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass(frozen=True)
class EducationPathLayout:
    root_name: str = "education"
    artifacts_dir_name: str = "artifacts"
