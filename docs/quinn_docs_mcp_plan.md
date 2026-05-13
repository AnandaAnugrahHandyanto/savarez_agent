# Scoped Docs and Notes MCP Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a scoped docs/notes MCP that lets Quinn search, summarize, and propose edits to selected Hermes/Quinn source-of-truth documents without browsing arbitrary files or exposing private values.

**Architecture:** Build a local stdio MCP server with an explicit document allowlist. Version 1 is read-first: it inventories approved documents, searches headings/content, returns bounded excerpts, and can generate proposed patch text without applying changes. Actual writes are deferred to a later approval-gated phase.

**Tech Stack:** Python 3.11, MCP SDK, pathlib, regex, markdown heading parser, pytest with temp document fixtures.

---

## Security Contract

- No arbitrary filesystem browsing.
- Only exact allowlisted paths and allowlisted directories are visible.
- No auth files, session transcript directories, logs, or env files.
- No writes in v1.
- Excerpts are bounded by line count and character count.
- Redaction runs on all returned text.
- Search results return path aliases and line numbers, not hidden absolute paths unless approved.
- Proposed edits are returned as text patches only; they are not applied.

## Initial Allowlist Proposal

Exact files:

- `/home/quinn/docs/quinn-hermes-server.md`
- `/home/quinn/.hermes/hermes-agent/docs/quinn_ops_mcp.md`
- `/home/quinn/.hermes/hermes-agent/docs/quinn_ops_snapshot_diff_design.md`
- `/home/quinn/.hermes/hermes-agent/docs/quinn_ops_github_mcp_plan.md`
- `/home/quinn/.hermes/hermes-agent/docs/quinn_ops_observability_mcp_plan.md`

Optional exact files after review:

- `/home/quinn/quinn/docs/QUINN_V1_V35_INSTALL_REPORT.md`
- `/home/quinn/docs/quinn-hermes-server.md`
- `/home/quinn/quinn/runtime/quinn_loader_order.json` metadata only, not raw full dump unless approved

Do not allow:

- `/home/quinn/.hermes/.env`
- `/home/quinn/.hermes/auth.json`
- `/home/quinn/.hermes/sessions/`
- `/home/quinn/.hermes/logs/`
- arbitrary `/home/quinn/quinn/runtime/` private runtime files

## Tool Set v1

1. `healthcheck()` — server readiness and allowlist counts.
2. `list_documents()` — aliases, titles, size, mtime, type, readability.
3. `get_document_outline(doc_id: str)` — Markdown headings and line numbers.
4. `search_documents(query: str, limit: int = 20)` — bounded search across allowlisted docs.
5. `read_document_excerpt(doc_id: str, start_line: int = 1, limit: int = 80)` — bounded redacted excerpt.
6. `get_document_summary(doc_id: str)` — metadata plus heading outline and short non-LLM extractive summary.
7. `check_source_of_truth_freshness()` — reports stale/missing source-of-truth docs by metadata and expected headings.
8. `propose_document_patch(doc_id: str, change_request: str)` — returns a safe patch proposal template; does not apply.

## Task 1: Add Failing Allowlist Tests

**Objective:** Prove only approved docs can be accessed.

**Files:**
- Create: `tests/test_quinn_docs_mcp.py`

**Tests:**
- Allowlisted document can be listed/read.
- Non-allowlisted path is rejected.
- Path traversal is rejected.
- Auth/env/session/log-like paths are rejected even if user asks directly.
- Redaction removes private-looking values from fixture text.

**Verification:**
```bash
venv/bin/python -m pytest tests/test_quinn_docs_mcp.py -q
```

Expected: FAIL until server exists.

## Task 2: Scaffold Server and Document Registry

**Objective:** Create importable server with strict document identity mapping.

**Files:**
- Create: `scripts/mcp/quinn_docs_server.py`
- Modify: `tests/test_quinn_docs_mcp.py`

**Implementation requirements:**
- `DOC_REGISTRY` maps stable doc IDs to exact paths.
- `resolve_doc_id(doc_id)` never accepts raw paths.
- `response()`, `sanitize()`, `file_meta()` helpers.
- Importable without MCP SDK.

**Verification:**
```bash
python3 -m py_compile scripts/mcp/quinn_docs_server.py tests/test_quinn_docs_mcp.py
venv/bin/python -m pytest tests/test_quinn_docs_mcp.py -q
```

## Task 3: List Documents and Outlines

**Objective:** Provide safe document discovery.

**Files:**
- Modify: `scripts/mcp/quinn_docs_server.py`
- Modify: `tests/test_quinn_docs_mcp.py`

**Implementation requirements:**
- `list_documents()` returns doc ID, title, size, mtime, exists, and doc type.
- `get_document_outline()` parses Markdown headings with line numbers.
- JSON files return top-level keys only, not full raw content unless specifically allowed.

**Tests:**
- Markdown headings parsed correctly.
- Missing doc returns metadata and warning.
- JSON metadata-only behavior works.

## Task 4: Search and Excerpts

**Objective:** Let Quinn find relevant source-of-truth content safely.

**Files:**
- Modify: `scripts/mcp/quinn_docs_server.py`
- Modify: `tests/test_quinn_docs_mcp.py`

**Implementation requirements:**
- `search_documents(query, limit=20)` searches allowlisted Markdown text.
- Clamp query length and result limit.
- Return doc ID, title, line number, and short redacted snippet.
- `read_document_excerpt(doc_id, start_line=1, limit=80)` clamps line count and character total.

**Tests:**
- Search finds expected lines.
- Excerpt clamps line count.
- Private fixture values are redacted.
- Query cannot be used as a regex denial-of-service vector.

## Task 5: Freshness Checks

**Objective:** Surface stale or missing source-of-truth docs without reading everything.

**Files:**
- Modify: `scripts/mcp/quinn_docs_server.py`
- Modify: `tests/test_quinn_docs_mcp.py`

**Implementation requirements:**
- `check_source_of_truth_freshness()` verifies required docs exist.
- Report missing expected headings like `Change Log`, `Security Boundaries`, or `Live Promotion` where relevant.
- Report mtime age and size changes, not content diffs.

**Tests:**
- Missing file -> warning.
- Missing heading -> warning.
- Healthy docs -> ok.

## Task 6: Patch Proposal Only

**Objective:** Prepare edits without applying them.

**Files:**
- Modify: `scripts/mcp/quinn_docs_server.py`
- Modify: `tests/test_quinn_docs_mcp.py`

**Implementation requirements:**
- `propose_document_patch(doc_id, change_request)` returns a patch template or TODO checklist.
- It must not call write/patch/file mutation APIs.
- It must include `requires_approval=true`.
- It must include doc ID and target section.

**Tests:**
- Patch proposal contains no applied side effects.
- Denied doc cannot receive proposal.
- Proposal result says approval required.

## Task 7: Register MCP Tools and Docs

**Objective:** Make the server usable and documented without live enablement.

**Files:**
- Modify: `scripts/mcp/quinn_docs_server.py`
- Create: `docs/quinn_docs_mcp.md`

**Implementation requirements:**
- Add `TOOL_FUNCTIONS` and MCP stdio startup.
- Document registry, tools, non-goals, security boundaries, and live promotion steps.

**Verification:**
```bash
python3 -m py_compile scripts/mcp/quinn_docs_server.py tests/test_quinn_docs_mcp.py
venv/bin/python -m pytest tests/test_quinn_docs_mcp.py -q
```

## Live Promotion Gate

Do not promote automatically. Before live use:

1. Frank approval.
2. Confirm exact document registry.
3. Repo tests pass.
4. Backup existing live server, if any.
5. Copy repo server to live MCP path.
6. Add MCP config only if approved.
7. Restart gateway.
8. Verify `hermes mcp test quinn_docs`.
9. Verify denied paths fail and allowlisted excerpts are redacted.

## Acceptance Criteria

- No arbitrary path access.
- No write actions in v1.
- Allowlisted docs can be listed, outlined, searched, and excerpted.
- Runtime JSON files are metadata/top-level only unless specifically approved.
- Patch proposals require approval and do not mutate files.

## Open Questions Requiring Frank

1. Which exact docs belong in the first allowlist?
2. Should Quinn runtime JSON be metadata-only forever, or can protected contexts read bounded raw sections?
3. Should v1 support patch proposal text, or should even proposals wait for approval-ops MCP?
