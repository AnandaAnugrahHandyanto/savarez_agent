from pathlib import Path

from hermes_constants import get_hermes_home


def education_root() -> Path:
    return get_hermes_home() / "education"


def artifacts_root() -> Path:
    return education_root() / "artifacts"


def question_bank_db_path() -> Path:
    return education_root() / "question_bank.db"


def raw_artifacts_root() -> Path:
    return artifacts_root() / "raw"


def mineru_artifacts_root() -> Path:
    return artifacts_root() / "mineru"


def normalized_artifacts_root() -> Path:
    return artifacts_root() / "normalized"


def wiki_artifacts_root() -> Path:
    return artifacts_root() / "wiki"
