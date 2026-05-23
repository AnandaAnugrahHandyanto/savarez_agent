from __future__ import annotations

from pathlib import Path

DOC_PATHS = [
    Path("website/docs/user-guide/features/llm-wiki-memory.md"),
    Path("website/docs/user-guide/features/memory-providers.md"),
]

FORBIDDEN_PUBLIC_DOC_SNIPPETS = [
    "/home/kraut",
    "hermes-dev",
    "private repository",
    "@claude",
    "michaelkrauty",
    "http://localhost:8011",
    "gpt-4o-mini",
]


def test_llm_wiki_public_docs_do_not_leak_private_dogfood_paths():
    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_PUBLIC_DOC_SNIPPETS:
            assert snippet not in text, f"{path} contains private dogfood snippet: {snippet}"
