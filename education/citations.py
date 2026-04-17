from __future__ import annotations

from dataclasses import dataclass

from education.normalize import SourceBlock
from education.questions import ExtractedQuestion


@dataclass(frozen=True)
class QuestionCitation:
    question_id: str
    document_id: str
    source_block_id: str | None
    page_start: int | None
    page_end: int | None
    quote_markdown: str | None
    citation_kind: str
    integrity_status: str


@dataclass(frozen=True)
class CitationValidationResult:
    citations: list[QuestionCitation]
    status_by_question_id: dict[str, str]


def validate_question_citations(
    questions: list[ExtractedQuestion],
    source_blocks: list[SourceBlock],
) -> CitationValidationResult:
    blocks_by_id = {block.block_id: block for block in source_blocks}
    citations: list[QuestionCitation] = []
    status_by_question_id: dict[str, str] = {}

    for question in questions:
        if not question.source_block_ids:
            status_by_question_id[question.question_id] = "missing"
            continue

        question_status = "complete"
        for block_id in question.source_block_ids:
            block = blocks_by_id.get(block_id)
            if block is None:
                question_status = "invalid"
                citations.append(
                    QuestionCitation(
                        question_id=question.question_id,
                        document_id=question.document_id,
                        source_block_id=block_id,
                        page_start=None,
                        page_end=None,
                        quote_markdown=None,
                        citation_kind="stem",
                        integrity_status="missing_block",
                    )
                )
                continue
            if block.document_id != question.document_id:
                question_status = "invalid"
                citations.append(
                    QuestionCitation(
                        question_id=question.question_id,
                        document_id=question.document_id,
                        source_block_id=block_id,
                        page_start=block.page_start,
                        page_end=block.page_end,
                        quote_markdown=block.content_markdown,
                        citation_kind="stem",
                        integrity_status="mismatched_document",
                    )
                )
                continue
            citations.append(
                QuestionCitation(
                    question_id=question.question_id,
                    document_id=question.document_id,
                    source_block_id=block.block_id,
                    page_start=block.page_start,
                    page_end=block.page_end,
                    quote_markdown=block.content_markdown,
                    citation_kind="stem",
                    integrity_status="valid",
                )
            )
        status_by_question_id[question.question_id] = question_status

    return CitationValidationResult(
        citations=citations,
        status_by_question_id=status_by_question_id,
    )
