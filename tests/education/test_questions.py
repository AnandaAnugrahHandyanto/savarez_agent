from education.normalize import SourceBlock
from education.questions import extract_questions


def _block(block_id: str, index: int, content: str) -> SourceBlock:
    return SourceBlock(
        block_id=block_id,
        document_id="doc001",
        block_index=index,
        kind="paragraph",
        content_markdown=content,
        content_hash=f"hash-{index}",
        page_start=1,
        page_end=1,
    )


def test_extract_questions_handles_numbered_multiple_choice_with_answer_and_explanation():
    blocks = [
        _block(
            "blk_doc001_0001",
            1,
            "1. 已知 $a^2+b^2=c^2$，下列说法正确的是？\nA. 勾股定理\nB. 一元二次方程\nC. 指数函数\nD. 对数函数",
        ),
        _block("blk_doc001_0002", 2, "答案：A"),
        _block("blk_doc001_0003", 3, "解析：由 $a^2+b^2=c^2$ 可知为勾股定理。"),
    ]

    questions = extract_questions(blocks)

    assert len(questions) == 1
    question = questions[0]
    assert question.question_number == "1"
    assert question.question_type == "single_choice"
    assert "$a^2+b^2=c^2$" in question.stem_markdown
    assert question.options == [
        {"label": "A", "text": "勾股定理"},
        {"label": "B", "text": "一元二次方程"},
        {"label": "C", "text": "指数函数"},
        {"label": "D", "text": "对数函数"},
    ]
    assert question.answer_markdown == "A"
    assert "$a^2+b^2=c^2$" in question.explanation_markdown
    assert question.source_block_ids == ["blk_doc001_0001", "blk_doc001_0002", "blk_doc001_0003"]


def test_extract_questions_preserves_display_formula_in_stem():
    blocks = [
        _block("blk_doc001_0001", 1, "2. 计算：\n$$x^2+y^2$$"),
        _block("blk_doc001_0002", 2, "答案：无法确定"),
    ]

    questions = extract_questions(blocks)

    assert len(questions) == 1
    assert "$$x^2+y^2$$" in questions[0].stem_markdown
    assert questions[0].formula_count == 1
