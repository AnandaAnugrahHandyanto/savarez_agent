#!/usr/bin/env python3
"""
benchmark/runner.py — Run 10-doc / 50-Q&A benchmark: DeepParser vs LlamaIndex.

Usage:
    # Set env vars first:
    export DEEPPARSER_API_KEY=dp_live_...
    export DEEPPARSER_BASE_URL=https://your-deepparser.fly.dev
    export OPENAI_API_KEY=sk-...   # used by LlamaIndex default embeddings

    python benchmark/runner.py [--system deepparser|llamaindex|both] [--doc D01]

Outputs:
    benchmark/results/deepparser.jsonl   — one JSON line per question
    benchmark/results/llamaindex.jsonl   — one JSON line per question

Re-running is safe: already-completed pairs are skipped (resume mode).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BENCH_DIR = Path(__file__).parent
DOCS_DIR = BENCH_DIR / "docs"
RESULTS_DIR = BENCH_DIR / "results"
QA_PAIRS_FILE = BENCH_DIR / "qa_pairs.json"

DEEPPARSER_OUT = RESULTS_DIR / "deepparser.jsonl"
LLAMAINDEX_OUT = RESULTS_DIR / "llamaindex.jsonl"

RESULTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_done(path: Path) -> set[str]:
    """Return set of question IDs already written to an output file."""
    done: set[str] = set()
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                done.add(json.loads(line)["question_id"])
            except Exception:
                pass
    return done


def _append(path: Path, record: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# DeepParser runner
# ---------------------------------------------------------------------------

async def run_deepparser(qa_pairs: dict, filter_doc: str | None) -> None:
    try:
        from deepparser import DeepParserClient, ParseFailedError, ParseTimeoutError
    except ImportError:
        print("ERROR: deepparser SDK not installed. Run: pip install -e .", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("DEEPPARSER_API_KEY")
    base_url = os.environ.get("DEEPPARSER_BASE_URL", "http://localhost:8000")
    if not api_key:
        print("ERROR: DEEPPARSER_API_KEY env var not set.", file=sys.stderr)
        sys.exit(1)

    done = _load_done(DEEPPARSER_OUT)
    docs = qa_pairs["docs"]
    if filter_doc:
        docs = [d for d in docs if d["id"] == filter_doc]

    async with DeepParserClient(api_key=api_key, base_url=base_url, debug=True) as client:
        for doc in docs:
            doc_path = DOCS_DIR / doc["filename"]
            if not doc_path.exists():
                print(f"  SKIP {doc['id']}: {doc['filename']} not found in benchmark/docs/")
                continue

            print(f"\n{'='*60}")
            print(f"Parsing {doc['id']} ({doc['category']}): {doc['filename']}")

            # Parse once per doc, reuse job_id for all questions
            job_id: str | None = None
            parse_error: str | None = None

            if any(q["id"] not in done for q in doc["questions"]):
                try:
                    t0 = time.monotonic()
                    job = await client.parse(doc_path, sync=True)
                    if job.status != "READY":
                        job = await client.wait_until_ready(job.job_id)
                    parse_ms = int((time.monotonic() - t0) * 1000)
                    job_id = job.job_id
                    print(f"  Parsed in {parse_ms}ms → job {job_id[:8]}...")
                except ParseFailedError as e:
                    parse_error = f"PARSE_FAILED: {e.detail}"
                    print(f"  Parse failed: {e.detail}")
                except ParseTimeoutError:
                    parse_error = "PARSE_TIMEOUT"
                    print(f"  Parse timed out")
                except Exception as e:
                    parse_error = f"ERROR: {e}"
                    print(f"  Unexpected error: {e}")

            for q in doc["questions"]:
                qid = q["id"]
                if qid in done:
                    print(f"  skip {qid} (already done)")
                    continue

                record: dict = {
                    "question_id": qid,
                    "doc_id": doc["id"],
                    "category": doc["category"],
                    "question": q["question"],
                    "system": "deepparser",
                }

                if parse_error:
                    record["answer"] = None
                    record["error"] = parse_error
                    record["latency_ms"] = None
                elif job_id:
                    try:
                        t0 = time.monotonic()
                        result = await client.ask(job_id, q["question"])
                        ask_ms = int((time.monotonic() - t0) * 1000)
                        record["answer"] = result.answer
                        record["citations"] = [c.model_dump() for c in result.citations]
                        record["latency_ms"] = ask_ms
                        record["error"] = None
                        print(f"  {qid}: {result.answer[:80]}...")
                    except Exception as e:
                        record["answer"] = None
                        record["error"] = str(e)
                        record["latency_ms"] = None
                        print(f"  {qid}: error — {e}")

                _append(DEEPPARSER_OUT, record)
                done.add(qid)

    print(f"\nDeepParser done. Results → {DEEPPARSER_OUT}")


# ---------------------------------------------------------------------------
# LlamaIndex runner
# ---------------------------------------------------------------------------

def run_llamaindex(qa_pairs: dict, filter_doc: str | None) -> None:
    try:
        from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Settings
        from llama_index.core.node_parser import SimpleNodeParser
    except ImportError:
        print(
            "ERROR: llama-index not installed.\n"
            "Run: pip install 'llama-index-core>=0.12,<0.13' 'llama-index-llms-openai>=0.3' "
            "'llama-index-embeddings-openai>=0.3'",
            file=sys.stderr,
        )
        sys.exit(1)

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print("ERROR: OPENAI_API_KEY env var not set (needed for LlamaIndex embeddings).", file=sys.stderr)
        sys.exit(1)

    done = _load_done(LLAMAINDEX_OUT)
    docs_list = qa_pairs["docs"]
    if filter_doc:
        docs_list = [d for d in docs_list if d["id"] == filter_doc]

    for doc in docs_list:
        doc_path = DOCS_DIR / doc["filename"]
        if not doc_path.exists():
            print(f"  SKIP {doc['id']}: {doc['filename']} not found in benchmark/docs/")
            continue

        unanswered = [q for q in doc["questions"] if q["id"] not in done]
        if not unanswered:
            print(f"  SKIP {doc['id']}: all questions already answered")
            continue

        print(f"\n{'='*60}")
        print(f"Indexing {doc['id']} ({doc['category']}): {doc['filename']}")

        index = None
        index_error: str | None = None
        try:
            t0 = time.monotonic()
            # LlamaIndex default: SimpleDirectoryReader + VectorStoreIndex (OpenAI embeddings)
            loaded_docs = SimpleDirectoryReader(input_files=[str(doc_path)]).load_data()
            index = VectorStoreIndex.from_documents(loaded_docs)
            index_ms = int((time.monotonic() - t0) * 1000)
            print(f"  Indexed in {index_ms}ms")
        except Exception as e:
            index_error = str(e)
            print(f"  Index failed: {e}")

        query_engine = index.as_query_engine() if index else None

        for q in unanswered:
            qid = q["id"]
            record: dict = {
                "question_id": qid,
                "doc_id": doc["id"],
                "category": doc["category"],
                "question": q["question"],
                "system": "llamaindex",
            }

            if index_error:
                record["answer"] = None
                record["error"] = f"INDEX_FAILED: {index_error}"
                record["latency_ms"] = None
            else:
                try:
                    t0 = time.monotonic()
                    response = query_engine.query(q["question"])
                    ask_ms = int((time.monotonic() - t0) * 1000)
                    record["answer"] = str(response)
                    record["latency_ms"] = ask_ms
                    record["error"] = None
                    print(f"  {qid}: {str(response)[:80]}...")
                except Exception as e:
                    record["answer"] = None
                    record["error"] = str(e)
                    record["latency_ms"] = None
                    print(f"  {qid}: error — {e}")

            _append(LLAMAINDEX_OUT, record)
            done.add(qid)

    print(f"\nLlamaIndex done. Results → {LLAMAINDEX_OUT}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="DeepParser vs LlamaIndex benchmark runner")
    parser.add_argument(
        "--system", choices=["deepparser", "llamaindex", "both"], default="both",
        help="Which system to run (default: both)"
    )
    parser.add_argument(
        "--doc", metavar="ID", default=None,
        help="Only run a single document by ID (e.g. D01)"
    )
    args = parser.parse_args()

    with open(QA_PAIRS_FILE) as f:
        qa_pairs = json.load(f)

    if args.system in ("deepparser", "both"):
        asyncio.run(run_deepparser(qa_pairs, args.doc))

    if args.system in ("llamaindex", "both"):
        run_llamaindex(qa_pairs, args.doc)


if __name__ == "__main__":
    main()
