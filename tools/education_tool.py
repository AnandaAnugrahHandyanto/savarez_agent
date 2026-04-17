from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from education.service import EducationService
from tools.registry import registry


def _serialize_result(value):
    if is_dataclass(value):
        payload = asdict(value)
    else:
        payload = value
    for key, item in list(payload.items()):
        if isinstance(item, Path):
            payload[key] = str(item)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _education_ingest_document(args, **kwargs):
    service = EducationService()
    result = service.ingest_file(args["path"])
    return _serialize_result(result)


def _education_ingest_status(args, **kwargs):
    return json.dumps({"error": "not implemented"}, ensure_ascii=False, sort_keys=True)


def _education_search_questions(args, **kwargs):
    service = EducationService()
    rows = service.search_questions(args["query"], limit=int(args.get("limit", 20)))
    return json.dumps([dict(row) for row in rows], ensure_ascii=False, sort_keys=True)


def _education_render_wiki(args, **kwargs):
    service = EducationService()
    markdown = service.render_document_wiki(args["document_id"])
    return json.dumps({"markdown": markdown}, ensure_ascii=False, sort_keys=True)


def _education_export_question_bank(args, **kwargs):
    service = EducationService()
    markdown = service.export_question_bank(args.get("title", "Education Question Bank"))
    return json.dumps({"markdown": markdown}, ensure_ascii=False, sort_keys=True)


registry.register(
    name="education_ingest_document",
    toolset="education",
    schema={
        "name": "education_ingest_document",
        "description": "Ingest a local PDF or DOCX into the education question bank.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    handler=_education_ingest_document,
)

registry.register(
    name="education_ingest_status",
    toolset="education",
    schema={
        "name": "education_ingest_status",
        "description": "Get ingestion status for an education document job.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
            },
        },
    },
    handler=_education_ingest_status,
)

registry.register(
    name="education_search_questions",
    toolset="education",
    schema={
        "name": "education_search_questions",
        "description": "Search extracted education questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    handler=_education_search_questions,
)

registry.register(
    name="education_render_wiki",
    toolset="education",
    schema={
        "name": "education_render_wiki",
        "description": "Render a document wiki page from the education question bank.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
            },
            "required": ["document_id"],
        },
    },
    handler=_education_render_wiki,
)

registry.register(
    name="education_export_question_bank",
    toolset="education",
    schema={
        "name": "education_export_question_bank",
        "description": "Export markdown from the education question bank.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
            },
        },
    },
    handler=_education_export_question_bank,
)
