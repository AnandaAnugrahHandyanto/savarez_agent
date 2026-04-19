import json
from io import BytesIO
from typing import Iterable

from .config import get_settings
from .embedding import EmbeddingService
from .models import Chunk

settings = get_settings()


SECTION_RE = __import__("re").compile(r"^\s{0,3}(#+\s+.+|\d+\.\s+.+|[A-Z][A-Za-z0-9\s]{2,80}:)\s*$")


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> Iterable[tuple[str, int, int, str]]:
    size = size or settings.chunk_size_chars
    overlap = overlap or settings.chunk_overlap_chars

    normalized = (text or "").replace("\r\n", "\n")
    if not normalized.strip():
        return []

    # Build a map of section boundaries from source lines.
    section_points: list[tuple[int, str]] = [(0, "")]
    cursor = 0
    for line in normalized.split("\n"):
        stripped = line.strip()
        if stripped and SECTION_RE.match(line):
            section_points.append((cursor, stripped[:255]))
        cursor += len(line) + 1

    chunks = []
    n = len(normalized)
    start = 0
    while start < n:
        end = min(start + size, n)
        chunk = normalized[start:end].strip()
        if chunk:
            section_label = ""
            for point, label in section_points:
                if point <= start:
                    section_label = label
                else:
                    break
            chunks.append((chunk, start, end, section_label))
        if end == n:
            break
        start = max(0, end - overlap)

    return chunks


def extract_text_from_bytes(filename: str, content: bytes) -> str:
    lower = filename.lower()

    if lower.endswith((".txt", ".md", ".csv", ".json")):
        return content.decode("utf-8", errors="ignore")

    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            pages = [p.extract_text() or "" for p in reader.pages]
            return "\n".join(pages)
        except Exception:
            return content.decode("utf-8", errors="ignore")

    return content.decode("utf-8", errors="ignore")


def index_document_chunks(db, *, tenant_id: int, document_id: int, roles_allowed: list[str], raw_text: str) -> int:
    embedder = EmbeddingService()
    chunks = list(chunk_text(raw_text))

    created = 0
    for i, (text, start_char, end_char, section_label) in enumerate(chunks):
        db.add(
            Chunk(
                tenant_id=tenant_id,
                document_id=document_id,
                chunk_index=i,
                text=text,
                embedding_json=json.dumps(embedder.embed(text)),
                roles_allowed_json=json.dumps(roles_allowed),
                start_char=start_char,
                end_char=end_char,
                section_label=section_label,
                page_number=None,
            )
        )
        created += 1

    return created
