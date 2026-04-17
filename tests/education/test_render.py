from education.render import render_document_wiki, render_question_bank_markdown
from education.service import IngestResult
from education.questions import ExtractedQuestion


def _question():
    return ExtractedQuestion(
        question_id="q_doc001_1",
        document_id="doc001",
        question_number="1",
        question_type="single_choice",
        stem_markdown="已知 $a^2+b^2=c^2$，下列说法正确的是？",
        options=[
            {"label": "A", "text": "勾股定理"},
            {"label": "B", "text": "指数函数"},
        ],
        answer_markdown="A",
        explanation_markdown="由 $a^2+b^2=c^2$ 可知为勾股定理。",
        formula_count=2,
        source_block_ids=["blk_doc001_0001", "blk_doc001_0002"],
    )


def test_render_document_wiki_includes_document_summary_and_citation_warning(tmp_path):
    result = IngestResult(
        document_id="doc001",
        job_id="job001",
        status="indexed",
        raw_artifact_path=tmp_path / "raw.pdf",
        normalized_artifact_path=tmp_path / "normalized.md",
        question_count=1,
        citation_status="partial",
        error=None,
    )

    markdown = render_document_wiki(
        title="二次函数练习",
        source_digest="abc123",
        ingest_result=result,
        questions=[_question()],
    )

    assert "# 二次函数练习" in markdown
    assert "Source digest: `abc123`" in markdown
    assert "Status: `indexed`" in markdown
    assert "Citation coverage: `partial`" in markdown
    assert "## Question index" in markdown
    assert "Warning: citation coverage is partial" in markdown


def test_render_question_bank_markdown_includes_questions_and_citations():
    markdown = render_question_bank_markdown(
        title="数学题库导出",
        questions=[_question()],
        citations={
            "q_doc001_1": [
                {"page_start": 1, "page_end": 1, "source_block_id": "blk_doc001_0001"},
                {"page_start": 1, "page_end": 1, "source_block_id": "blk_doc001_0002"},
            ]
        },
    )

    assert "# 数学题库导出" in markdown
    assert "## q_doc001_1" in markdown
    assert "A. 勾股定理" in markdown
    assert "Answer: A" in markdown
    assert "$a^2+b^2=c^2$" in markdown
    assert "- page 1-1 / block `blk_doc001_0001`" in markdown
