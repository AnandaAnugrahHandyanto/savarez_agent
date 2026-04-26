"""Publish Hermes daily usage reports to Feishu/Lark documents."""

from __future__ import annotations

import json
import subprocess
from datetime import timezone as timezone_cls, tzinfo
from pathlib import Path
from typing import Any

from agent.insights import InsightsEngine
from hermes_state import SessionDB


DEFAULT_LARK_CLI_PATH = "/opt/homebrew/bin/lark-cli"
DEFAULT_TITLE = "Hermes Daily Usage Report"
DEFAULT_FEISHU_DOC_BASE_URL = "https://thendlesssky.feishu.cn/docx/"


def publish_daily_report(
    *,
    db_path: str | Path,
    day: str | None = None,
    tz: tzinfo | None = timezone_cls.utc,
    doc_id: str | None = None,
    title: str = DEFAULT_TITLE,
    wiki_space: str | None = None,
    folder_token: str | None = None,
    lark_cli_path: str = DEFAULT_LARK_CLI_PATH,
) -> dict[str, Any]:
    """Render the daily report and publish it to a Feishu/Lark doc."""
    db = SessionDB(db_path=Path(db_path))
    try:
        engine = InsightsEngine(db)
        report = engine.generate_daily_summary(day=day, tz=tz)
        markdown = engine.format_feishu_daily_markdown(report)
        resolved_title = _resolve_report_title(title, report)
    finally:
        db.close()

    command = _build_publish_command(
        lark_cli_path=lark_cli_path,
        markdown=markdown,
        doc_id=doc_id,
        title=resolved_title,
        wiki_space=wiki_space,
        folder_token=folder_token,
    )
    payload = _run_lark_cli(command)
    data = payload.get("data") or {}

    resolved_doc_id = data.get("doc_id") or doc_id
    doc_url = data.get("doc_url") or _build_doc_url(resolved_doc_id)

    return {
        "action": "updated" if doc_id else "created",
        "doc_id": resolved_doc_id,
        "doc_url": doc_url,
        "title": resolved_title,
        "report": report,
        "response": payload,
    }


def _build_publish_command(
    *,
    lark_cli_path: str,
    markdown: str,
    doc_id: str | None,
    title: str,
    wiki_space: str | None,
    folder_token: str | None,
) -> list[str]:
    if doc_id:
        return [
            lark_cli_path,
            "docs",
            "+update",
            "--doc",
            doc_id,
            "--mode",
            "overwrite",
            "--new-title",
            title,
            "--markdown",
            markdown,
        ]

    command = [
        lark_cli_path,
        "docs",
        "+create",
        "--title",
        title,
        "--markdown",
        markdown,
    ]
    if wiki_space:
        command.extend(["--wiki-space", wiki_space])
    if folder_token:
        command.extend(["--folder-token", folder_token])
    return command


def _resolve_report_title(title: str, report: dict[str, Any]) -> str:
    """Return a daily-document title that includes the report date."""
    report_date = str(report.get("date") or "unknown")
    if "{date}" in title:
        return title.format(date=report_date)
    if report_date in title:
        return title
    return f"{title} - {report_date}"


def _build_doc_url(doc_id: str | None) -> str | None:
    if not doc_id:
        return None
    return f"{DEFAULT_FEISHU_DOC_BASE_URL}{doc_id}"


def _run_lark_cli(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        details = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"lark-cli command failed: {details}")

    stdout = (result.stdout or "").strip()
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from lark-cli: {exc}") from exc

    if not payload.get("ok"):
        error = payload.get("error") or {}
        message = error.get("message") or payload
        raise RuntimeError(f"lark-cli reported failure: {message}")

    return payload
