# Education Question Bank

This document describes the local-first education question-bank workflow implemented in Hermes.

## Storage layout

All runtime state is stored under `HERMES_HOME/education/`.

- `question_bank.db` — SQLite source of truth
- `artifacts/raw/` — copied source PDF/DOCX files
- `artifacts/mineru/` — MinerU markdown outputs
- `artifacts/normalized/` — normalized markdown blocks
- `artifacts/wiki/` — generated wiki pages and exports

## Supported inputs

- PDF files are supported through the local ingestion workflow.
- DOCX files are accepted at the intake boundary and routed through a preparation seam.
- DOCX conversion still requires a configured converter backend before full MinerU preparation can proceed.

## Tools

The education feature is exposed through Hermes tools:

- `education_ingest_document`
- `education_ingest_status`
- `education_search_questions`
- `education_render_wiki`
- `education_export_question_bank`

## Formula preservation

Formula content from MinerU markdown is preserved verbatim during normalization and question extraction. Inline math and display math remain in Markdown/LaTeX form so they can be rendered in generated wiki content and exports.

## Citation integrity

Each extracted question is linked back to one or more source blocks. Citation validation marks questions as `complete`, `missing`, or `invalid` so downstream wiki rendering and exports can surface incomplete provenance instead of hiding it.
