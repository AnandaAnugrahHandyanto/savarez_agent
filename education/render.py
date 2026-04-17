from __future__ import annotations

from typing import Iterable, Mapping

from education.questions import ExtractedQuestion


def _render_options(question: ExtractedQuestion) -> list[str]:
    return [f"{option['label']}. {option['text']}" for option in question.options]


def render_document_wiki(*, title: str, source_digest: str, ingest_result, questions: Iterable[ExtractedQuestion]) -> str:
    lines = [
        f"# {title}",
        "",
        f"Source digest: `{source_digest}`",
        f"Status: `{ingest_result.status}`",
        f"Citation coverage: `{ingest_result.citation_status}`",
        f"Question count: `{ingest_result.question_count}`",
        "",
    ]
    if ingest_result.citation_status != "complete":
        lines.extend([
            f"> Warning: citation coverage is {ingest_result.citation_status}",
            "",
        ])
    lines.extend(["## Question index", ""])
    for question in questions:
        lines.append(f"- `{question.question_id}` — {question.stem_markdown.splitlines()[0]}")
    lines.append("")
    return "\n".join(lines)


def render_question_bank_markdown(
    *,
    title: str,
    questions: Iterable[ExtractedQuestion],
    citations: Mapping[str, list[dict]],
) -> str:
    lines = [f"# {title}", ""]
    for question in questions:
        lines.extend([
            f"## {question.question_id}",
            "",
            question.stem_markdown,
            "",
        ])
        option_lines = _render_options(question)
        if option_lines:
            lines.extend(option_lines)
            lines.append("")
        if question.answer_markdown is not None:
            lines.extend([f"Answer: {question.answer_markdown}", ""])
        if question.explanation_markdown is not None:
            lines.extend(["Explanation:", question.explanation_markdown, ""])
        lines.extend(["Citations:"])
        for citation in citations.get(question.question_id, []):
            lines.append(
                f"- page {citation.get('page_start')}-{citation.get('page_end')} / "
                f"block `{citation.get('source_block_id')}`"
            )
        lines.append("")
    return "\n".join(lines)
