"""Control Center dashboard plugin backend.

Provides a small LLM-wiki management API. The project Kanban tab reuses the
existing bundled Kanban plugin API directly from the browser, so this module
only owns wiki discovery, initialization, stats, page read/write, and lint.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from hermes_cli.config import get_hermes_home

router = APIRouter()

_ALLOWED_TOP_LEVEL = {
    "entities",
    "concepts",
    "comparisons",
    "queries",
    "raw",
    "_meta",
    "_archive",
}
_WIKI_NAME_RE = re.compile(r"^[A-Za-z0-9_. -]{1,80}$")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def _default_wiki_path() -> Path:
    raw = os.environ.get("WIKI_PATH") or str(Path.home() / "wiki")
    return Path(raw).expanduser().resolve()


def _registry_path() -> Path:
    return get_hermes_home() / "llm-wikis.json"


def _read_registry() -> list[dict[str, str]]:
    p = _registry_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            out.append({
                "name": str(item.get("name") or Path(item["path"]).name),
                "path": item["path"],
            })
    return out


def _write_registry(items: list[dict[str, str]]) -> None:
    p = _registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _wiki_candidates() -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get("WIKI_PATH")
    if env_path:
        paths.extend(
            Path(chunk).expanduser()
            for chunk in env_path.split(os.pathsep)
            if chunk.strip()
        )
    paths.extend([Path.home() / "wiki", get_hermes_home() / "wikis"])
    paths.extend(Path(item["path"]).expanduser() for item in _read_registry())
    # If ~/.hermes/wikis contains per-wiki dirs, include children too.
    root = get_hermes_home() / "wikis"
    if root.is_dir():
        paths.extend([p for p in root.iterdir() if p.is_dir()])

    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        try:
            r = p.expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        key = str(r)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _is_wiki(path: Path) -> bool:
    return (
        (path / "SCHEMA.md").exists()
        or (path / "index.md").exists()
        or (path / "log.md").exists()
    )


def _safe_wiki_path(path: str | None) -> Path:
    p = Path(path).expanduser().resolve() if path else _default_wiki_path()
    # Must either already look like an LLM wiki or be a registered path. This
    # prevents the dashboard from becoming a general filesystem editor.
    registered = {str(Path(x["path"]).expanduser().resolve()) for x in _read_registry()}
    if not _is_wiki(p) and str(p) not in registered:
        raise HTTPException(status_code=404, detail="Wiki not found or not registered")
    return p


def _safe_rel_path(wiki: Path, rel: str) -> Path:
    rel = (rel or "").strip().lstrip("/")
    if not rel.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only markdown files are supported")
    parts = Path(rel).parts
    if not parts or parts[0] not in _ALLOWED_TOP_LEVEL:
        raise HTTPException(
            status_code=400, detail="Path must live under a wiki content directory"
        )
    target = (wiki / rel).resolve()
    if not target.is_relative_to(wiki):
        raise HTTPException(status_code=403, detail="Path traversal blocked")
    return target


def _count_lines(path: Path) -> int:
    try:
        return path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
    except OSError:
        return 0


def _frontmatter_type(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    fm = text[3:end]
    m = re.search(r"^type:\s*([^\n#]+)", fm, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def _wiki_summary(path: Path) -> dict[str, Any]:
    md_files = [p for p in path.rglob("*.md") if ".git" not in p.parts]
    by_type: dict[str, int] = {}
    for p in md_files:
        try:
            t = (
                _frontmatter_type(p.read_text(encoding="utf-8", errors="replace"))
                or p.parent.name
            )
        except OSError:
            t = p.parent.name
        by_type[t] = by_type.get(t, 0) + 1
    log = path / "log.md"
    return {
        "name": path.name,
        "path": str(path),
        "exists": path.exists(),
        "initialized": _is_wiki(path),
        "page_count": len(md_files),
        "by_type": by_type,
        "schema": (path / "SCHEMA.md").exists(),
        "index": (path / "index.md").exists(),
        "log": log.exists(),
        "log_lines": _count_lines(log) if log.exists() else 0,
    }


class InitWikiBody(BaseModel):
    path: str | None = None
    name: str | None = None
    domain: str = Field(default="General research knowledge base", max_length=400)


class PageWriteBody(BaseModel):
    path: str
    content: str


class PromptBody(BaseModel):
    command: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=200)
    content: str | None = None
    tags: list[str] | None = None
    data: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    is_active: bool = True


_PROMPT_COMMAND_RE = re.compile(r"^/[A-Za-z0-9_.:-]{1,119}$")


def _prompts_path() -> Path:
    return get_hermes_home() / "prompts.json"


def _now() -> int:
    return int(time.time())


def _normalize_tags(tags: list[str] | None) -> list[str]:
    out: list[str] = []
    for tag in tags or []:
        t = str(tag).strip()
        if t and t not in out:
            out.append(t)
    return out


def _read_prompts() -> list[dict[str, Any]]:
    p = _prompts_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("prompts", [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def _write_prompts(prompts: list[dict[str, Any]]) -> None:
    p = _prompts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"prompts": prompts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_prompt_payload(body: PromptBody, *, partial: bool = False) -> None:
    if not partial and not (body.command and body.name and body.content is not None):
        raise HTTPException(
            status_code=400, detail="command, name, and content are required"
        )
    if body.command is not None and not _PROMPT_COMMAND_RE.match(body.command.strip()):
        raise HTTPException(
            status_code=400,
            detail="Command must start with / and contain only letters, numbers, dot, underscore, colon, or dash",
        )
    if body.name is not None and not body.name.strip():
        raise HTTPException(status_code=400, detail="Prompt name cannot be blank")


def _prompt_from_body(
    body: PromptBody,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = dict(existing or {})
    now = _now()
    if not existing:
        existing.update({"id": uuid.uuid4().hex, "source": "hermes", "created_at": now})
    if body.command is not None:
        existing["command"] = body.command.strip()
    if body.name is not None:
        existing["name"] = body.name.strip()
    if body.content is not None:
        existing["content"] = body.content
    if body.tags is not None:
        existing["tags"] = _normalize_tags(body.tags)
    if body.data is not None:
        existing["data"] = body.data
    if body.meta is not None:
        existing["meta"] = body.meta
    existing["is_active"] = bool(body.is_active)
    existing["updated_at"] = now
    existing.setdefault("tags", [])
    existing.setdefault("data", {})
    existing.setdefault("meta", {})
    return existing


def _open_webui_db_path() -> Path:
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        return Path(data_dir).expanduser().resolve() / "webui.db"
    return Path.home() / ".local" / "share" / "open-webui" / "data" / "webui.db"


def _jsonish(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _read_open_webui_prompts() -> list[dict[str, Any]]:
    db = _open_webui_db_path()
    if not db.exists():
        return []
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select id, command, user_id, name, content, data, meta, is_active, version_id, tags, created_at, updated_at from prompt order by updated_at desc"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        if con is not None:
            con.close()
    prompts = []
    for row in rows:
        item = dict(row)
        item["source"] = "open-webui"
        item["tags"] = _jsonish(item.get("tags"), [])
        item["data"] = _jsonish(item.get("data"), {})
        item["meta"] = _jsonish(item.get("meta"), {})
        item["is_active"] = bool(item.get("is_active"))
        prompts.append(item)
    return prompts


@router.get("/prompts")
def list_prompts(q: str | None = Query(None), tag: str | None = Query(None)):
    prompts = _read_prompts()
    needle = (q or "").lower().strip()
    tag_needle = (tag or "").lower().strip()
    if needle:
        prompts = [
            p
            for p in prompts
            if needle
            in "\n".join(
                str(p.get(k, "")) for k in ("command", "name", "content")
            ).lower()
        ]
    if tag_needle:
        prompts = [
            p
            for p in prompts
            if tag_needle in [str(t).lower() for t in p.get("tags", [])]
        ]
    prompts = sorted(prompts, key=lambda p: p.get("updated_at") or 0, reverse=True)
    return {"prompts": prompts, "total": len(prompts), "store": str(_prompts_path())}


@router.post("/prompts")
def create_prompt(body: PromptBody):
    _validate_prompt_payload(body)
    prompts = _read_prompts()
    command = (body.command or "").strip()
    if any(p.get("command") == command for p in prompts):
        raise HTTPException(status_code=409, detail="Prompt command already exists")
    prompt = _prompt_from_body(body)
    prompts.append(prompt)
    _write_prompts(prompts)
    return {"ok": True, "prompt": prompt}


@router.put("/prompts/{prompt_id}")
def update_prompt(prompt_id: str, body: PromptBody):
    _validate_prompt_payload(body, partial=True)
    prompts = _read_prompts()
    for idx, prompt in enumerate(prompts):
        if prompt.get("id") == prompt_id:
            new_command = (
                body.command.strip()
                if body.command is not None
                else prompt.get("command")
            )
            if any(
                p.get("id") != prompt_id and p.get("command") == new_command
                for p in prompts
            ):
                raise HTTPException(
                    status_code=409, detail="Prompt command already exists"
                )
            updated = _prompt_from_body(body, prompt)
            prompts[idx] = updated
            _write_prompts(prompts)
            return {"ok": True, "prompt": updated}
    raise HTTPException(status_code=404, detail="Prompt not found")


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: str):
    prompts = _read_prompts()
    kept = [p for p in prompts if p.get("id") != prompt_id]
    if len(kept) == len(prompts):
        raise HTTPException(status_code=404, detail="Prompt not found")
    _write_prompts(kept)
    return {"ok": True}


@router.get("/prompts/open-webui")
def preview_open_webui_prompts():
    prompts = _read_open_webui_prompts()
    return {"prompts": prompts, "total": len(prompts), "db": str(_open_webui_db_path())}


@router.post("/prompts/import-open-webui")
def import_open_webui_prompts():
    existing = _read_prompts()
    by_key = {
        (p.get("source"), p.get("external_id") or p.get("id")): p for p in existing
    }
    by_command = {p.get("command"): p for p in existing if p.get("command")}
    imported = 0
    updated = 0
    for src in _read_open_webui_prompts():
        key = ("open-webui", src.get("id"))
        prompt = {
            "id": by_key.get(key, {}).get("id") or uuid.uuid4().hex,
            "external_id": src.get("id"),
            "source": "open-webui",
            "command": src.get("command") or "",
            "name": src.get("name") or src.get("command") or "Open WebUI prompt",
            "content": src.get("content") or "",
            "data": src.get("data") or {},
            "meta": src.get("meta") or {},
            "tags": _normalize_tags(src.get("tags") or []),
            "is_active": bool(src.get("is_active", True)),
            "created_at": src.get("created_at") or _now(),
            "updated_at": src.get("updated_at") or _now(),
        }
        target = by_key.get(key) or by_command.get(prompt["command"])
        if target:
            target.update(prompt)
            updated += 1
        else:
            existing.append(prompt)
            imported += 1
    _write_prompts(existing)
    return {
        "ok": True,
        "imported": imported,
        "updated": updated,
        "total": len(existing),
        "store": str(_prompts_path()),
    }


@router.get("/wikis")
def list_wikis():
    items = [
        _wiki_summary(p)
        for p in _wiki_candidates()
        if p.exists() or str(p) == str(_default_wiki_path())
    ]
    # Keep likely wikis plus registered/default placeholders.
    filtered = [
        x
        for x in items
        if x["initialized"]
        or x["path"] == str(_default_wiki_path())
        or x["path"] in {r["path"] for r in _read_registry()}
    ]
    return {"wikis": filtered, "default_path": str(_default_wiki_path())}


@router.post("/wikis/init")
def init_wiki(body: InitWikiBody):
    path = Path(body.path).expanduser().resolve() if body.path else _default_wiki_path()
    if body.name and not _WIKI_NAME_RE.match(body.name):
        raise HTTPException(status_code=400, detail="Invalid wiki name")
    path.mkdir(parents=True, exist_ok=True)
    for sub in (
        "raw/articles",
        "raw/papers",
        "raw/transcripts",
        "raw/assets",
        "entities",
        "concepts",
        "comparisons",
        "queries",
    ):
        (path / sub).mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    schema = path / "SCHEMA.md"
    if not schema.exists():
        schema.write_text(
            f"# Wiki Schema\n\n## Domain\n{body.domain.strip()}\n\n## Conventions\n- File names are lowercase hyphenated markdown files.\n- Every wiki page uses YAML frontmatter with title, created, updated, type, tags, and sources.\n- Use [[wikilinks]] between related pages.\n- Update index.md and log.md after substantive changes.\n- raw/ is immutable source material.\n\n## Tag Taxonomy\n- reference\n- concept\n- entity\n- comparison\n- query\n\n## Page Thresholds\nCreate pages for central concepts/entities; avoid pages for passing mentions.\n",
            encoding="utf-8",
        )
    index = path / "index.md"
    if not index.exists():
        index.write_text(
            f"# Wiki Index\n\n> Last updated: {today} | Total pages: 0\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n",
            encoding="utf-8",
        )
    log = path / "log.md"
    if not log.exists():
        log.write_text(
            f"# Wiki Log\n\n## [{today}] create | Wiki initialized\n- Domain: {body.domain.strip()}\n",
            encoding="utf-8",
        )
    registry = _read_registry()
    if str(path) not in {r["path"] for r in registry}:
        registry.append({"name": body.name or path.name, "path": str(path)})
        _write_registry(registry)
    return {"ok": True, "wiki": _wiki_summary(path)}


@router.get("/wiki/stats")
def wiki_stats(path: str | None = Query(None)):
    return {"wiki": _wiki_summary(_safe_wiki_path(path))}


@router.get("/wiki/pages")
def list_pages(path: str | None = Query(None), q: str | None = Query(None)):
    wiki = _safe_wiki_path(path)
    pages = []
    needle = (q or "").lower().strip()
    for p in sorted(wiki.rglob("*.md")):
        if ".git" in p.parts:
            continue
        rel = str(p.relative_to(wiki))
        if rel in {"SCHEMA.md", "index.md", "log.md"}:
            bucket = "meta"
        else:
            bucket = p.parts[len(wiki.parts)] if len(p.parts) > len(wiki.parts) else ""
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        title_match = re.search(r"^title:\s*(.+)$", text, flags=re.MULTILINE)
        title = (
            title_match.group(1).strip().strip("\"'")
            if title_match
            else p.stem.replace("-", " ").title()
        )
        if (
            needle
            and needle not in rel.lower()
            and needle not in title.lower()
            and needle not in text.lower()
        ):
            continue
        pages.append({
            "path": rel,
            "title": title,
            "type": _frontmatter_type(text) or bucket,
            "lines": text.count("\n") + 1,
            "sha256": hashlib.sha256(text.encode()).hexdigest()[:12],
        })
    return {"pages": pages}


@router.get("/wiki/page")
def read_page(path: str | None = Query(None), file: str = Query(...)):
    wiki = _safe_wiki_path(path)
    if file in {"SCHEMA.md", "index.md", "log.md"}:
        target = (wiki / file).resolve()
        if not target.is_relative_to(wiki):
            raise HTTPException(status_code=403, detail="Path traversal blocked")
    else:
        target = _safe_rel_path(wiki, file)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    return {
        "path": str(target.relative_to(wiki)),
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


@router.put("/wiki/page")
def write_page(body: PageWriteBody, wiki_path: str | None = Query(None, alias="path")):
    wiki = _safe_wiki_path(wiki_path)
    target = _safe_rel_path(wiki, body.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return {
        "ok": True,
        "path": str(target.relative_to(wiki)),
        "sha256": hashlib.sha256(body.content.encode()).hexdigest()[:12],
    }


@router.get("/wiki/lint")
def lint_wiki(path: str | None = Query(None)):
    wiki = _safe_wiki_path(path)
    pages = [
        p
        for p in wiki.rglob("*.md")
        if ".git" not in p.parts
        and p.name not in {"SCHEMA.md", "index.md", "log.md"}
        and "raw" not in p.relative_to(wiki).parts
    ]
    slugs = {p.stem: p for p in pages}
    inbound: dict[str, int] = {p.stem: 0 for p in pages}
    broken = []
    missing_frontmatter = []
    large_pages = []
    for p in pages:
        text = p.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            missing_frontmatter.append(str(p.relative_to(wiki)))
        lines = text.count("\n") + 1
        if lines > 200:
            large_pages.append({"path": str(p.relative_to(wiki)), "lines": lines})
        for link in _WIKILINK_RE.findall(text):
            slug = Path(link.strip()).stem
            if slug in inbound:
                inbound[slug] += 1
            elif slug and slug not in slugs:
                broken.append({
                    "from": str(p.relative_to(wiki)),
                    "target": link.strip(),
                })
    orphans = [
        str(slugs[s].relative_to(wiki)) for s, count in inbound.items() if count == 0
    ]
    return {
        "issues": {
            "broken_links": broken,
            "orphans": orphans,
            "missing_frontmatter": missing_frontmatter,
            "large_pages": large_pages,
        },
        "counts": {
            "broken_links": len(broken),
            "orphans": len(orphans),
            "missing_frontmatter": len(missing_frontmatter),
            "large_pages": len(large_pages),
        },
    }
