from __future__ import annotations

import re
from dataclasses import dataclass

from education.normalize import SourceBlock


@dataclass(frozen=True)
class ExtractedQuestion:
    question_id: str
    document_id: str
    question_number: str
    question_type: str
    stem_markdown: str
    options: list[dict[str, str]]
    answer_markdown: str | None
    explanation_markdown: str | None
    formula_count: int
    source_block_ids: list[str]


_QUESTION_START_RE = re.compile(r"^(?P<number>\d+)\.\s*(?P<rest>[\s\S]+)$")
_OPTION_RE = re.compile(r"^([A-D])\.\s*(.+)$")
_ANSWER_RE = re.compile(r"^答案[:：]\s*(.+)$")
_EXPLANATION_RE = re.compile(r"^解析[:：]\s*(.+)$")
_INLINE_FORMULA_RE = re.compile(r"(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)", re.DOTALL)
_DISPLAY_FORMULA_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)


def _count_formulas(text: str) -> int:
    display_count = len(_DISPLAY_FORMULA_RE.findall(text))
    without_display = _DISPLAY_FORMULA_RE.sub("", text)
    inline_count = len(_INLINE_FORMULA_RE.findall(without_display))
    return display_count + inline_count


def _parse_question_block(content: str) -> tuple[str, str, list[dict[str, str]]]:
    match = _QUESTION_START_RE.match(content.strip())
    if not match:
        raise ValueError("Question block must start with a numbered question")

    number = match.group("number")
    lines = match.group("rest").splitlines()
    stem_lines: list[str] = []
    options: list[dict[str, str]] = []
    for line in lines:
        option_match = _OPTION_RE.match(line.strip())
        if option_match:
            options.append({"label": option_match.group(1), "text": option_match.group(2)})
        else:
            stem_lines.append(line)
    stem = "\n".join(line for line in stem_lines if line.strip()).strip()
    return number, stem, options


def extract_questions(blocks: list[SourceBlock]) -> list[ExtractedQuestion]:
    questions: list[ExtractedQuestion] = []
    current_question: dict | None = None
    source_block_ids: list[str] = []

    for block in blocks:
        content = block.content_markdown.strip()
        if _QUESTION_START_RE.match(content):
            if current_question is not None:
                questions.append(
                    ExtractedQuestion(
                        question_id=f"q_{current_question['document_id']}_{current_question['question_number']}",
                        document_id=current_question["document_id"],
                        question_number=current_question["question_number"],
                        question_type=current_question["question_type"],
                        stem_markdown=current_question["stem_markdown"],
                        options=current_question["options"],
                        answer_markdown=current_question.get("answer_markdown"),
                        explanation_markdown=current_question.get("explanation_markdown"),
                        formula_count=_count_formulas(
                            current_question["stem_markdown"]
                            + (current_question.get("answer_markdown") or "")
                            + (current_question.get("explanation_markdown") or "")
                        ),
                        source_block_ids=source_block_ids,
                    )
                )
            question_number, stem_markdown, options = _parse_question_block(content)
            current_question = {
                "document_id": block.document_id,
                "question_number": question_number,
                "question_type": "single_choice" if options else "short_answer",
                "stem_markdown": stem_markdown,
                "options": options,
                "answer_markdown": None,
                "explanation_markdown": None,
            }
            source_block_ids = [block.block_id]
            continue

        if current_question is None:
            continue

        answer_match = _ANSWER_RE.match(content)
        if answer_match:
            current_question["answer_markdown"] = answer_match.group(1).strip()
            source_block_ids.append(block.block_id)
            continue

        explanation_match = _EXPLANATION_RE.match(content)
        if explanation_match:
            current_question["explanation_markdown"] = explanation_match.group(1).strip()
            source_block_ids.append(block.block_id)
            continue

    if current_question is not None:
        questions.append(
            ExtractedQuestion(
                question_id=f"q_{current_question['document_id']}_{current_question['question_number']}",
                document_id=current_question["document_id"],
                question_number=current_question["question_number"],
                question_type=current_question["question_type"],
                stem_markdown=current_question["stem_markdown"],
                options=current_question["options"],
                answer_markdown=current_question.get("answer_markdown"),
                explanation_markdown=current_question.get("explanation_markdown"),
                formula_count=_count_formulas(
                    current_question["stem_markdown"]
                    + (current_question.get("answer_markdown") or "")
                    + (current_question.get("explanation_markdown") or "")
                ),
                source_block_ids=source_block_ids,
            )
        )

    return questions
