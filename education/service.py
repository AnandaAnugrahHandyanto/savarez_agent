from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from education.artifacts import ArtifactStore
from education.citations import validate_question_citations
from education.db import EducationDB
from education.mineru import CliMinerUBackend
from education.normalize import normalize_mineru_markdown
from education.questions import ExtractedQuestion, extract_questions
from education.render import render_document_wiki as render_document_wiki_markdown
from education.render import render_question_bank_markdown


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    job_id: str
    status: str
    raw_artifact_path: Path
    normalized_artifact_path: Path | None
    question_count: int
    citation_status: str
    error: str | None = None


class EducationService:
    def __init__(self, *, mineru_backend=None, db: EducationDB | None = None, artifact_store: ArtifactStore | None = None):
        self.mineru_backend = mineru_backend or CliMinerUBackend()
        self.db = db or EducationDB()
        self.artifact_store = artifact_store or ArtifactStore()

    def _document_id_for_sha(self, sha256: str) -> str:
        return f"doc_{sha256[:16]}"

    def _job_id(self) -> str:
        return f"job_{uuid.uuid4().hex[:12]}"

    def _hash_file(self, source_file: Path) -> str:
        digest = hashlib.sha256()
        with source_file.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def ingest_file(self, source_file: str | Path) -> IngestResult:
        source = Path(source_file).expanduser().resolve()
        sha256 = self._hash_file(source)
        document_id = self._document_id_for_sha(sha256)
        job_id = self._job_id()
        raw_artifact = self.artifact_store.store_source_file(source)

        existing = self.db.get_document(document_id)
        if existing is None:
            self.db.create_document(
                id=document_id,
                sha256=sha256,
                source_uri=str(source),
                source_type="local_file",
                original_filename=source.name,
                raw_artifact_path=str(raw_artifact.path),
                status="pending",
            )
        self.db.create_ingest_job(
            id=job_id,
            document_id=document_id,
            input_path=str(source),
            status="pending",
            stage="intake",
        )
        self.db.add_artifact(
            id=f"artifact_raw_{job_id}",
            document_id=document_id,
            job_id=job_id,
            kind="raw",
            path=str(raw_artifact.path),
            sha256=raw_artifact.sha256,
        )

        try:
            parse_output_dir = self.artifact_store.root / "mineru" / document_id
            mineru_result = self.mineru_backend.parse_document(source, parse_output_dir)
            mineru_markdown = self.artifact_store.write_named_artifact(
                kind="mineru",
                artifact_id=document_id,
                filename="mineru.md",
                content=mineru_result.markdown,
            )
            self.db.add_artifact(
                id=f"artifact_mineru_{job_id}",
                document_id=document_id,
                job_id=job_id,
                kind="mineru",
                path=str(mineru_markdown.path),
                sha256=mineru_markdown.sha256,
            )

            normalized_output_dir = self.artifact_store.root / "normalized" / document_id
            normalized = normalize_mineru_markdown(
                mineru_result.markdown,
                document_id=document_id,
                output_dir=normalized_output_dir,
            )
            self.db.add_artifact(
                id=f"artifact_normalized_{job_id}",
                document_id=document_id,
                job_id=job_id,
                kind="normalized",
                path=str(normalized.artifact_path),
                sha256=hashlib.sha256(normalized.markdown.encode("utf-8")).hexdigest(),
            )
            self.db.add_source_blocks(
                [
                    {
                        "id": block.block_id,
                        "document_id": block.document_id,
                        "block_index": block.block_index,
                        "page_start": block.page_start,
                        "page_end": block.page_end,
                        "kind": block.kind,
                        "content_markdown": block.content_markdown,
                        "content_hash": block.content_hash,
                        "created_at": time.time(),
                    }
                    for block in normalized.blocks
                ]
            )

            questions = extract_questions(normalized.blocks)
            citation_result = validate_question_citations(questions, normalized.blocks)
            self.db.add_questions(
                [
                    {
                        "id": question.question_id,
                        "document_id": question.document_id,
                        "question_number": question.question_number,
                        "question_type": question.question_type,
                        "stem_markdown": question.stem_markdown,
                        "options": question.options,
                        "answer_markdown": question.answer_markdown,
                        "explanation_markdown": question.explanation_markdown,
                        "formula_count": question.formula_count,
                        "citation_status": citation_result.status_by_question_id.get(question.question_id, "missing"),
                        "created_at": time.time(),
                        "updated_at": time.time(),
                    }
                    for question in questions
                ]
            )
            self.db.add_question_citations(
                [
                    {
                        "id": f"citation_{index:04d}_{question_citation.question_id}",
                        "question_id": question_citation.question_id,
                        "document_id": question_citation.document_id,
                        "source_block_id": question_citation.source_block_id,
                        "page_start": question_citation.page_start,
                        "page_end": question_citation.page_end,
                        "quote_markdown": question_citation.quote_markdown,
                        "citation_kind": question_citation.citation_kind,
                        "integrity_status": question_citation.integrity_status,
                    }
                    for index, question_citation in enumerate(citation_result.citations, start=1)
                ]
            )
            self.db.update_ingest_job(
                job_id,
                status="indexed",
                stage="complete",
                finished_at=time.time(),
            )
            self.db._execute_write(
                "UPDATE documents SET status = ?, updated_at = ? WHERE id = ?",
                ("indexed", time.time(), document_id),
            )
            citation_status = next(iter(citation_result.status_by_question_id.values()), "missing")
            return IngestResult(
                document_id=document_id,
                job_id=job_id,
                status="indexed",
                raw_artifact_path=raw_artifact.path,
                normalized_artifact_path=normalized.artifact_path,
                question_count=len(questions),
                citation_status=citation_status,
            )
        except Exception as exc:
            self.db.update_ingest_job(
                job_id,
                status="failed",
                stage="failed",
                finished_at=time.time(),
                error=str(exc),
            )
            self.db._execute_write(
                "UPDATE documents SET status = ?, last_error = ?, updated_at = ? WHERE id = ?",
                ("failed", str(exc), time.time(), document_id),
            )
            return IngestResult(
                document_id=document_id,
                job_id=job_id,
                status="failed",
                raw_artifact_path=raw_artifact.path,
                normalized_artifact_path=None,
                question_count=0,
                citation_status="missing",
                error=str(exc),
            )

    def search_questions(self, query: str, limit: int = 20):
        return self.db.search_questions(query, limit=limit)

    def render_document_wiki(self, document_id: str) -> str:
        document = self.db.get_document(document_id)
        if document is None:
            raise ValueError(f"Unknown document: {document_id}")

        question_rows = self.db.conn.execute(
            "SELECT * FROM questions WHERE document_id = ? ORDER BY question_number, id",
            (document_id,),
        ).fetchall()
        questions = [
            ExtractedQuestion(
                question_id=row["id"],
                document_id=row["document_id"],
                question_number=row["question_number"] or "",
                question_type=row["question_type"] or "unknown",
                stem_markdown=row["stem_markdown"],
                options=[],
                answer_markdown=row["answer_markdown"],
                explanation_markdown=row["explanation_markdown"],
                formula_count=row["formula_count"],
                source_block_ids=[],
            )
            for row in question_rows
        ]
        return render_document_wiki_markdown(
            title=document["title"] or document["original_filename"],
            source_digest=document["sha256"],
            ingest_result=IngestResult(
                document_id=document_id,
                job_id="",
                status=document["status"],
                raw_artifact_path=Path(document["raw_artifact_path"]),
                normalized_artifact_path=None,
                question_count=len(questions),
                citation_status=questions[0].question_id and (question_rows[0]["citation_status"] if question_rows else "missing"),
                error=document["last_error"],
            ),
            questions=questions,
        )

    def export_question_bank(self, title: str = "Education Question Bank") -> str:
        question_rows = self.db.conn.execute(
            "SELECT * FROM questions ORDER BY document_id, question_number, id"
        ).fetchall()
        questions = [
            ExtractedQuestion(
                question_id=row["id"],
                document_id=row["document_id"],
                question_number=row["question_number"] or "",
                question_type=row["question_type"] or "unknown",
                stem_markdown=row["stem_markdown"],
                options=[],
                answer_markdown=row["answer_markdown"],
                explanation_markdown=row["explanation_markdown"],
                formula_count=row["formula_count"],
                source_block_ids=[],
            )
            for row in question_rows
        ]
        citations: dict[str, list[dict]] = {}
        for question in questions:
            citation_rows = self.db.conn.execute(
                "SELECT page_start, page_end, source_block_id FROM question_citations WHERE question_id = ? ORDER BY id",
                (question.question_id,),
            ).fetchall()
            citations[question.question_id] = [dict(row) for row in citation_rows]
        return render_question_bank_markdown(
            title=title,
            questions=questions,
            citations=citations,
        )
