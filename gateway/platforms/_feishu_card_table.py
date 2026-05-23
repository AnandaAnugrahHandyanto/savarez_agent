"""Markdown → Feishu Card JSON 2.0 table conversion (pure-stdlib helpers).

Isolated module so the conversion logic can be unit-tested without loading
the full ``gateway.platforms.feishu`` stack (which pulls in ``hermes_cli``,
``lark_oapi``, websockets, aiohttp, etc.). The dispatch is wired up in
``gateway.platforms.feishu._build_outbound_payload``.

Why a dedicated module:

- Feishu Card JSON 1.0 (used by ``send_exec_approval`` / ``send_update_prompt``)
  has no ``tag: "table"`` component. Card JSON 2.0 introduces it (Lark V7.4+),
  and the two schemas may be mixed across messages within the same chat —
  each ``send_message`` payload is independent.
- We invoke 2.0 only when the outbound content actually contains a markdown
  table; everything else stays on the existing text / post / 1.0 card paths.
- Keeping the helpers in their own module makes them trivially unit-testable
  with the stdlib alone (``re``, ``json``, ``typing``).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


_MD_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[-|: ]+\|\s*$")


def _split_md_table_row(row_line: str) -> List[str]:
    """Split one markdown table row line into cell strings.

    Strips the leading / trailing ``|`` and trims surrounding whitespace
    on each cell.
    """
    stripped = row_line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _split_content_at_tables(content: str) -> List[Tuple[str, str]]:
    """Split content into alternating ('text', str) and ('table', str) segments.

    A table starts at a pipe-row whose next line matches the separator
    pattern ``^\\s*\\|[-|: ]+\\|\\s*$``. The table extends through every
    following line that begins with ``|``. Non-table chunks (including
    blank lines) are returned verbatim.
    """
    segments: List[Tuple[str, str]] = []
    lines = content.splitlines(keepends=True)
    n = len(lines)
    i = 0
    while i < n:
        is_table_start = (
            i + 1 < n
            and lines[i].lstrip().startswith("|")
            and lines[i].rstrip().endswith("|")
            and _MD_TABLE_SEPARATOR_RE.match(lines[i + 1] or "")
        )
        if is_table_start:
            j = i + 2
            while j < n and lines[j].lstrip().startswith("|"):
                j += 1
            segments.append(("table", "".join(lines[i:j])))
            i = j
            continue
        # Accumulate non-table lines until next table start or EOF.
        j = i
        while j < n:
            if (
                j + 1 < n
                and lines[j].lstrip().startswith("|")
                and lines[j].rstrip().endswith("|")
                and _MD_TABLE_SEPARATOR_RE.match(lines[j + 1] or "")
            ):
                break
            j += 1
        segments.append(("text", "".join(lines[i:j])))
        i = j
    return segments


def _parse_markdown_table_to_card_element(table_text: str) -> Dict[str, Any]:
    """Parse a markdown table block into a Feishu Card JSON 2.0 table element.

    First content row is treated as the header. Subsequent rows are data.
    Columns use ``data_type: "markdown"`` so cell content can carry inline
    formatting (bold / links / emoji ✅/❌ etc.) that scout-mcp commonly
    emits. ``page_size: 10`` keeps long shortlists scrollable without
    making the card huge.
    """
    rows_raw = [ln for ln in table_text.splitlines() if ln.strip().startswith("|")]
    if len(rows_raw) < 2:
        return {"tag": "markdown", "content": table_text}
    header_cells = _split_md_table_row(rows_raw[0])
    data_rows_raw = rows_raw[2:]  # rows_raw[1] is the |---| separator
    columns: List[Dict[str, Any]] = []
    for idx, cell in enumerate(header_cells):
        col_name = f"col{idx + 1}"
        columns.append(
            {
                "name": col_name,
                "display_name": cell or col_name,
                "data_type": "markdown",
            }
        )
    rows: List[Dict[str, Any]] = []
    for row_line in data_rows_raw:
        cells = _split_md_table_row(row_line)
        while len(cells) < len(columns):
            cells.append("")
        rows.append({columns[i]["name"]: cells[i] for i in range(len(columns))})
    return {
        "tag": "table",
        "page_size": 10,
        "columns": columns,
        "rows": rows,
    }


def _build_card_with_table_payload(
    content: str,
    sheet_url: Optional[str] = None,
) -> str:
    """Build a Feishu interactive card (JSON 2.0) preserving markdown tables.

    Splits ``content`` at each markdown table block: prose around the table
    becomes ``tag: "markdown"`` element(s); each table becomes a native
    ``tag: "table"`` element. Renders as sortable / paginated table UI on
    Lark V7.4+ clients instead of the previously-broken md-table fallback
    that produced blank messages.

    When ``sheet_url`` is supplied, a "Open in Lark Sheet" button (rendered
    as a bold markdown link, schema-safe across Lark client versions) is
    appended right after the **first** table. Multiple tables in one
    message still get hints + raw source, but only the first table maps
    to a Sheets-API-backed spreadsheet (single-message single-sheet to
    keep the API call count predictable).
    """
    segments = _split_content_at_tables(content)
    elements: List[Dict[str, Any]] = []
    table_index = 0
    for seg_kind, seg_text in segments:
        if seg_kind == "table":
            elements.append(_parse_markdown_table_to_card_element(seg_text))
            is_first_table = table_index == 0
            attached_sheet = sheet_url if is_first_table else None
            if attached_sheet:
                # Visible CTA right after the table — markdown link is the
                # most schema-portable button surface (no ``tag: "button"``
                # field-name guessing across Card JSON v1 / v2).
                elements.append(_build_sheet_open_element(attached_sheet))
            # Hint text adapts to whether the sheet CTA is present.
            elements.append(
                _build_table_hint_element(has_sheet=bool(attached_sheet))
            )
            # Raw markdown source for long-press select + paste workflows.
            elements.append(_build_raw_source_disclosure(seg_text))
            table_index += 1
        elif seg_text.strip():
            elements.append({"tag": "markdown", "content": seg_text})
    if not elements:
        elements = [{"tag": "markdown", "content": content}]
    card: Dict[str, Any] = {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {"elements": elements},
    }
    return json.dumps(card, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Self-check entry point — `python3 gateway/platforms/_feishu_card_table.py`
# ---------------------------------------------------------------------------
#
# Runs a minimal end-to-end check using a real Scout / Feishu transcript
# fragment (the 2026-05-21 office-furniture incident). Does NOT import the
# full gateway package, so it works in a sparse checkout without hermes_cli
# or lark_oapi installed.
#
# Run via:
#     python3 gateway/platforms/_feishu_card_table.py
#
# Exits non-zero on any assertion failure; on success, dumps the produced
# card JSON so a human can eyeball the structure before shipping.


_SCOUT_FEISHU_FRAGMENT = (
    "结果出来了,先做个初步筛选:\n"
    "\n"
    "| 关键词 | AMZ123排名 | 亚马逊竞品数 | 竞品<2000? |\n"
    "|---|---|---|---|\n"
    "| office desk | 2961 | **123,664** | ❌ |\n"
    "| office chair | 201 | **62,794** | ❌ |\n"
    "| ergonomic office chair | 3546 | **16,873** | ❌ |\n"
    "| filing cabinet | 9120 | **18,600** | ❌ |\n"
    "| office desk accessories | 3043 | **111,356** | ❌ |\n"
    "| ✅ **criss cross office chair** | **7256** | **1,410** | ✅ |\n"
    "\n"
    "**主要发现:** 办公家具类目主词竞品数都 >1 万,符合 <2000 的就一个\n"
)


_TABLE_HINT_NO_SHEET = (
    "💡 **复制 / 下载提示** · 长按 cell 复制单元格 · "
    "长按下方原始数据可全选复制并粘贴到飞书表格 / Excel · "
    "「保存到飞书表格」按钮需 sheets:spreadsheet OAuth scope (v3 上线中)"
)

_TABLE_HINT_WITH_SHEET = (
    "💡 长按 cell 复制单元格 · 长按下方原始数据全选复制 · "
    "点击上方 📊 按钮在飞书表格中查看 / 编辑 / 分享 / 导出 CSV"
)


def _build_table_hint_element(has_sheet: bool = False) -> Dict[str, Any]:
    """Inline markdown hint educating users about copy / download paths.

    When the card carries a Lark Sheet CTA (``has_sheet=True``), the hint
    points users to the button and drops the "v3 coming soon" caveat.
    Otherwise it explains the long-press fallback and flags that the
    Sheet button is pending OAuth scope provisioning.
    """
    content = _TABLE_HINT_WITH_SHEET if has_sheet else _TABLE_HINT_NO_SHEET
    return {"tag": "markdown", "content": content}


def _build_sheet_open_element(sheet_url: str) -> Dict[str, Any]:
    """Render the "Open in Lark Sheet" CTA as a bold markdown link.

    A markdown link works across both Card JSON 1.0 and 2.0 renderers
    without depending on the ``tag: "button"`` field-name (which differs
    between schema versions and Lark client builds). The cell rendering
    is clickable on every Lark client + browser surface.
    """
    return {
        "tag": "markdown",
        "content": (
            f"[**📊 在飞书表格中打开 · 编辑 · 分享 · 导出 CSV**]({sheet_url})"
        ),
    }


def _build_raw_source_disclosure(table_text: str) -> Dict[str, Any]:
    """Re-emit the original markdown table inside a fenced code block.

    Feishu cards render fenced ``markdown`` content as plain monospace,
    so long-press select-all on this block lets users copy the table as
    valid markdown to paste into Lark Sheets, Excel, or any md-capable
    surface. This is the closest we can ship without a backend Sheets
    API integration.
    """
    stripped = table_text.rstrip("\n")
    return {
        "tag": "markdown",
        "content": f"```markdown\n{stripped}\n```",
    }


def _run_selfcheck() -> int:
    # === Case A: no sheet_url — v2 layout (hint + raw source only) ===
    raw = _build_card_with_table_payload(_SCOUT_FEISHU_FRAGMENT)
    card = json.loads(raw)
    assert card["schema"] == "2.0", f"expected schema 2.0, got {card['schema']!r}"
    elements = card["body"]["elements"]
    tags = [e["tag"] for e in elements]
    assert tags == [
        "markdown", "table", "markdown", "markdown", "markdown"
    ], f"case A: unexpected element order: {tags}"
    assert "长按 cell 复制单元格" in elements[2]["content"], "case A: hint missing copy text"
    assert "v3 上线中" in elements[2]["content"], "case A: hint should flag v3 pending"
    assert elements[3]["content"].startswith("```markdown"), "case A: raw-source missing fence"
    assert "| 关键词 |" in elements[3]["content"], "case A: raw-source missing original table"

    # === Case B: with sheet_url — v3 layout (CTA button + adjusted hint) ===
    mock_url = "https://feishu.cn/sheets/shtcnMOCKTOKEN12345"
    raw_b = _build_card_with_table_payload(_SCOUT_FEISHU_FRAGMENT, sheet_url=mock_url)
    card_b = json.loads(raw_b)
    elements_b = card_b["body"]["elements"]
    tags_b = [e["tag"] for e in elements_b]
    # Order: intro / table / sheet-cta / hint / raw-source / footer
    assert tags_b == [
        "markdown", "table", "markdown", "markdown", "markdown", "markdown"
    ], f"case B: unexpected element order: {tags_b}"
    assert mock_url in elements_b[2]["content"], "case B: sheet-cta missing URL"
    assert "📊" in elements_b[2]["content"], "case B: sheet-cta missing button emoji"
    assert "v3 上线中" not in elements_b[3]["content"], "case B: hint should drop v3-pending caveat"
    assert "点击上方 📊 按钮" in elements_b[3]["content"], "case B: hint should reference CTA"

    table = elements[1]
    assert len(table["columns"]) == 4, f"expected 4 columns, got {len(table['columns'])}"
    assert table["columns"][0]["display_name"] == "关键词"
    assert len(table["rows"]) == 6, f"expected 6 rows, got {len(table['rows'])}"

    last = table["rows"][5]
    assert "criss cross office chair" in last["col1"], f"row 5 col1 wrong: {last['col1']!r}"
    assert last["col4"] == "✅", f"row 5 col4 wrong: {last['col4']!r}"

    # Dump for visual eyeballing
    print("=" * 72)
    print("SELF-CHECK: Scout / Feishu 2026-05-21 office-furniture transcript")
    print("=" * 72)
    print("Input markdown content:")
    print("-" * 72)
    print(_SCOUT_FEISHU_FRAGMENT)
    print("-" * 72)
    print("Output card JSON (msg_type=interactive payload):")
    print("-" * 72)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    print("-" * 72)
    print(f"Element count: {len(elements)}")
    for i, e in enumerate(elements):
        if e["tag"] == "table":
            print(
                f"  [{i}] table: {len(e['columns'])} cols, {len(e['rows'])} rows, "
                f"page_size={e['page_size']}"
            )
        else:
            content_preview = e.get("content", "")[:60].replace("\n", " ")
            print(f"  [{i}] {e['tag']}: {content_preview!r}")
    print("=" * 72)
    print("OK")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_run_selfcheck())
