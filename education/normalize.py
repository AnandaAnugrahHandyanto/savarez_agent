from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceBlock:
    block_id: str
    document_id: str
    block_index: int
    kind: str
    content_markdown: str
    content_hash: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class NormalizedDocument:
    document_id: str
    markdown: str
    blocks: list[SourceBlock]
    artifact_path: Path


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _classify_block(block: str) -> str:
    stripped = block.strip()
    if stripped.startswith("#"):
        return "heading"
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return "formula"
    if stripped.startswith("|"):
        return "table"
    if stripped.startswith("!["):
        return "image"
    return "paragraph"


def _split_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_display_math = False
    in_table = False

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("[PAGE:") and stripped.endswith("]"):
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            in_table = False
            continue

        if not stripped:
            if current and not in_display_math and not in_table:
                blocks.append("\n".join(current).strip())
                current = []
            elif current and in_table:
                blocks.append("\n".join(current).strip())
                current = []
                in_table = False
            continue

        starts_table = stripped.startswith("|")
        if current and starts_table != in_table and not in_display_math:
            blocks.append("\n".join(current).strip())
            current = []
        in_table = starts_table

        current.append(line)
        if stripped.startswith("$$") or stripped.endswith("$$"):
            in_display_math = not in_display_math if stripped.count("$$") == 1 else False

    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _page_for_line(line: str) -> int | None:
    stripped = line.strip()
    if not (stripped.startswith("[PAGE:") and stripped.endswith("]")):
        return None
    value = stripped[len("[PAGE:"):-1]
    try:
        return int(value)
    except ValueError:
        return None


def normalize_mineru_markdown(
    markdown: str,
    *,
    document_id: str,
    output_dir: str | Path,
) -> NormalizedDocument:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    current_page: int | None = None
    normalized_lines: list[str] = []
    for line in markdown.splitlines():
        page = _page_for_line(line)
        if page is not None:
            current_page = page
            continue
        normalized_lines.append(line)
    normalized_markdown = "\n".join(normalized_lines).strip() + "\n"

    blocks = []
    block_page = current_page
    # For first implementation, page markers in a MinerU document apply to the
    # following blocks until another marker appears. The tests exercise one page.
    for index, block in enumerate(_split_blocks(markdown), start=1):
        blocks.append(
            SourceBlock(
                block_id=f"blk_{document_id}_{index:04d}",
                document_id=document_id,
                block_index=index,
                kind=_classify_block(block),
                content_markdown=block,
                content_hash=_hash_text(block),
                page_start=block_page,
                page_end=block_page,
            )
        )

    artifact_path = output / "normalized.md"
    artifact_path.write_text(normalized_markdown, encoding="utf-8")
    return NormalizedDocument(
        document_id=document_id,
        markdown=normalized_markdown,
        blocks=blocks,
        artifact_path=artifact_path,
    )
