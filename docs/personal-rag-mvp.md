# Personal RAG MVP for Hermes

This document describes the first local personal-document RAG implementation for Hermes.
It is designed for sensitive personal documents such as VEFA/Esalia/SG documents, payslips, bank statements, tax documents, selected emails, and business documents.

## Goal

Keep the main Hermes model unchanged while adding a private searchable document layer.

Current target model setup can remain:

```yaml
model:
  provider: openai-codex
  default: gpt-5.5
```

The RAG tool does **not** replace the model. It returns sourced passages. Hermes then uses its active model to answer.

## Architecture

```text
Telegram / Discord / CLI
        |
        v
Hermes Agent
Provider: openai-codex
Model: gpt-5.5
        |
        | tool call
        v
personal_rag_search / personal_rag_ingest / personal_rag_list
        |
        v
$HERMES_HOME/personal-rag/personal_rag.db
SQLite tables:
  - documents
  - chunks
        |
        v
Sourced passages:
  - source_file
  - title
  - document_type
  - page_start / page_end
  - chunk_index
  - score
        |
        v
Hermes gpt-5.5 writes the final French answer with citations
```

## Why this MVP uses SQLite instead of Chroma/Qdrant

This first version is intentionally dependency-light:

- no server to run;
- no cloud vector database;
- no mandatory `chromadb` or `sentence-transformers` install;
- profile-safe storage via `get_hermes_home()`;
- works immediately for text PDFs and text/markdown files.

Embeddings are deterministic local hashed lexical vectors. This is less semantic than a transformer embedding model, but it is sufficient for a first private sourced-search MVP and keeps the public Hermes tool contract stable.

Later upgrades can replace the internal storage with Chroma/Qdrant and local embedding models without changing the conversation flow.

## Storage location

Default profile:

```text
~/.hermes/personal-rag/personal_rag.db
```

Named profiles use their own `$HERMES_HOME`, so the index is profile-local.

## Tools

### `personal_rag_ingest`

Indexes a local file.

Parameters:

```json
{
  "file_path": "/path/to/document.pdf",
  "document_type": "vefa",
  "title": "Acte notarié VEFA",
  "chunk_chars": 1800,
  "overlap_chars": 250
}
```

Supported file types in the MVP:

- `.pdf` via `pypdf`;
- `.txt`;
- `.md` / `.markdown`;
- `.log`.

Important limitation: scanned PDFs need OCR. This MVP returns a clear error when no extractable text is found.

### `personal_rag_search`

Searches the local index and returns passages.

Parameters:

```json
{
  "query": "apport personnel fonds propres résidence principale VEFA",
  "document_type": "vefa",
  "k": 6
}
```

Use `document_type: "all"` to search every indexed document.

### `personal_rag_list`

Lists indexed documents.

Parameters:

```json
{
  "document_type": "all",
  "limit": 50
}
```

## Example use cases

### VEFA / SG / Esalia / PEE

Question:

```text
Retrouve les passages qui prouvent que mon apport personnel finance ma résidence principale.
```

Hermes calls:

```json
{
  "query": "apport personnel fonds propres financement résidence principale VEFA",
  "document_type": "all",
  "k": 8
}
```

The tool returns sourced chunks. Hermes answers with facts, uncertainty, and source references.

### Payslips and taxes

Question:

```text
Quel document indique le net imposable annuel à comparer avec la case 1AJ ?
```

For now, the RAG can retrieve the relevant payslip page. A future specialized payroll layer should extract structured fields into SQLite tables such as `payslips`.

### Bank statements

Question:

```text
Retrouve les passages des relevés qui mentionnent les virements vers le notaire.
```

The MVP can retrieve text passages. For reliable totals and transaction analysis, add a future `bank_transactions` table.

## Recommended rollout for our use case

1. Enable the `personal_rag` toolset.
2. Index one or two non-sensitive test PDFs.
3. Test retrieval from Telegram/CLI.
4. Index VEFA/Esalia/SG documents.
5. Add OCR for scanned PDFs.
6. Add structured SQLite extraction for payslips and bank statements.
7. Add selective email/thread ingestion.

## Enabling

After this branch is installed, enable the toolset and restart the session/gateway:

```bash
hermes tools enable personal_rag
hermes gateway restart
```

Or use a targeted CLI session:

```bash
hermes chat --toolsets personal_rag,file,terminal -q "Liste mes documents RAG indexés"
```

## Privacy model

- Documents stay local.
- The index is local SQLite under `$HERMES_HOME`.
- The tool sends only selected passages back into Hermes context.
- The active LLM provider receives only the retrieved excerpts needed for the answer, not the full document corpus.

## Known MVP limitations

- Hashed lexical embeddings are not as semantically strong as transformer embeddings.
- No OCR yet for scanned PDFs.
- No table extraction yet for bank statements/payslips.
- No deduplication yet when the same file is ingested twice.
- No deletion tool yet.

## Future architecture

```text
                 +--------------------+
                 |  personal_rag_*    |
                 +---------+----------+
                           |
        +------------------+------------------+
        |                                     |
        v                                     v
SQLite structured data                 Vector store
payslips                               Chroma/Qdrant/pgvector
bank_transactions                      semantic embeddings
mail_threads                           reranking
        |                                     |
        +------------------+------------------+
                           |
                           v
                    Hermes gpt-5.5
                final answer + citations
```
