from education.citations import validate_question_citations
from education.normalize import SourceBlock
from education.questions import ExtractedQuestion


def _block(block_id: str, document_id: str = "doc001") -> SourceBlock:
    return SourceBlock(
        block_id=block_id,
        document_id=document_id,
        block_index=1,
        kind="paragraph",
        content_markdown="1. 已知 $a^2+b^2=c^2$，求结论。",
        content_hash="hash",
        page_start=3,
        page_end=3,
    )


def _question(source_block_ids):
    return ExtractedQuestion(
        question_id="q001",
        document_id="doc001",
        question_number="1",
        question_type="short_answer",
        stem_markdown="已知 $a^2+b^2=c^2$，求结论。",
        options=[],
        answer_markdown=None,
        explanation_markdown=None,
        formula_count=1,
        source_block_ids=source_block_ids,
    )


def test_validate_question_citations_marks_complete_when_source_block_exists():
    result = validate_question_citations([_question(["blk_doc001_0001"])], [_block("blk_doc001_0001")])

    assert result.status_by_question_id == {"q001": "complete"}
    assert result.citations[0].question_id == "q001"
    assert result.citations[0].source_block_id == "blk_doc001_0001"
    assert result.citations[0].page_start == 3
    assert result.citations[0].integrity_status == "valid"


def test_validate_question_citations_marks_missing_when_no_source_blocks():
    result = validate_question_citations([_question([])], [_block("blk_doc001_0001")])

    assert result.status_by_question_id == {"q001": "missing"}
    assert result.citations == []


def test_validate_question_citations_marks_invalid_when_block_document_mismatches():
    result = validate_question_citations([_question(["blk_other_0001"])], [_block("blk_other_0001", document_id="other")])

    assert result.status_by_question_id == {"q001": "invalid"}
    assert result.citations[0].integrity_status == "mismatched_document"
