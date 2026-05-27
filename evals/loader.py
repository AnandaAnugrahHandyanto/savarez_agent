from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .schemas import EvalCase, EvalSchemaError, load_eval_case_file

DEFAULT_CASES_DIR = Path("evals/cases")


def resolve_case_files(
    root: str | Path = DEFAULT_CASES_DIR,
    *,
    suites: Sequence[str] | None = None,
) -> list[Path]:
    base_dir = Path(root)
    if not base_dir.exists():
        raise EvalSchemaError(f"case root does not exist: {base_dir}")
    if not base_dir.is_dir():
        raise EvalSchemaError(f"case root must be a directory: {base_dir}")

    suite_filter = {suite for suite in (suites or [])}
    case_files: list[Path] = []
    for path in base_dir.rglob("*.yaml"):
        if not path.is_file():
            continue
        if suite_filter:
            relative = path.relative_to(base_dir)
            inferred_suite = relative.parts[0] if len(relative.parts) > 1 else None
            if inferred_suite not in suite_filter:
                continue
        case_files.append(path)

    return sorted(case_files, key=lambda path: path.relative_to(base_dir).as_posix())


def load_eval_cases(
    root: str | Path = DEFAULT_CASES_DIR,
    *,
    suites: Sequence[str] | None = None,
    case_ids: Sequence[str] | None = None,
) -> list[EvalCase]:
    requested_case_ids = list(case_ids or [])
    requested_case_id_set = set(requested_case_ids)
    cases: list[EvalCase] = []

    for path in resolve_case_files(root, suites=suites):
        case = load_eval_case_file(path)
        if requested_case_id_set and case.case_id not in requested_case_id_set:
            continue
        cases.append(case)

    cases.sort(key=_case_sort_key)

    if requested_case_ids:
        found_case_ids = {case.case_id for case in cases}
        missing = sorted(requested_case_id_set - found_case_ids)
        if missing:
            raise EvalSchemaError(f"missing case_id(s): {', '.join(missing)}")

    return cases


def load_eval_suite(root: str | Path = DEFAULT_CASES_DIR, suite: str = "") -> list[EvalCase]:
    if not suite:
        raise EvalSchemaError("suite is required")
    return load_eval_cases(root, suites=[suite])


def group_cases_by_suite(cases: Iterable[EvalCase]) -> dict[str, list[EvalCase]]:
    grouped: dict[str, list[EvalCase]] = {}
    for case in sorted(cases, key=_case_sort_key):
        grouped.setdefault(case.suite, []).append(case)
    return grouped


def _case_sort_key(case: EvalCase) -> tuple[str, str, str]:
    return (case.suite, case.case_id, case.title)
