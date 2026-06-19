"""Hermes-specific benchmark: built-in memory vs Cortext.

Honest comparison of what each approach actually injects per turn:

  BASELINE (Hermes built-in provider): the ENTIRE MEMORY.md + USER.md text
    is placed in the system prompt on EVERY turn (always-on context).

  CORTEX: only the W5H memories the parser deems relevant to the current
    query are injected (cortex.recall(query)).

Metrics per query:
  - tokens injected (tiktoken cl100k_base if available, else chars/4)
  - precision@k: fraction of returned memories that are relevant
  - hit: did the relevant chunk appear at all (recall)

Run:
    HERMES_HOME=~/.hermes python plugins/memory/cortex/bench_hermes.py
"""

from __future__ import annotations

import os
from pathlib import Path


def _count_tokens(text: str) -> int:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text or ""))
    except Exception:
        return len(text or "") // 4


# Labeled queries: each expects the relevant memory's `what` to contain `expect`.
QUERIES = [
    ("Qual o projeto principal atual?", "LIVRO + PREPRINT"),
    ("O que é o projeto Cortex?", "sistema de memória cognitiva"),
    ("Qual o status atual do Cortex e do detector?", "refactor/v4-extensions"),
    ("Como o usuário prefere trabalhar?", "CONTRIBUIR com resultados concretos"),
    ("O que é o vendedor-blindado?", "VENDEDOR-BLINDADO"),
    ("Quais são os 5 elementos do detector?", "alfabeto discreto"),
    ("Que skill antiga existe de marketplace?", "copy-marketplace-vb"),
]


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

    from cortext import CortexV5

    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    mem_dir = home / "memories"

    # --- Baseline: full profile text injected every turn ---
    full_text = ""
    for fname in ("MEMORY.md", "USER.md"):
        p = mem_dir / fname
        if p.exists():
            full_text += p.read_text(encoding="utf-8") + "\n"
    baseline_tokens = _count_tokens(full_text)

    # --- Cortex: populate a fresh graph from the same files ---
    from plugins.memory.cortex.migrate import _split_chunks, _candidate_who

    cortex = CortexV5(namespace="bench-hermes")
    for fname, where in (("MEMORY.md", "hermes-memory"), ("USER.md", "hermes-user")):
        p = mem_dir / fname
        if not p.exists():
            continue
        for chunk in _split_chunks(p.read_text(encoding="utf-8")):
            cortex.remember(
                who=_candidate_who(chunk), what=chunk, where=where,
                importance=0.85, lang="pt", validate=False,
            )

    print("=" * 78)
    print("BENCHMARK: Hermes built-in (full context) vs Cortext (recall)")
    print("=" * 78)
    print(f"Memórias migradas: {len(cortex.graph)} | baseline = {baseline_tokens} tokens/turno\n")

    print(f"{'Query':<42} {'Cortex tok':>10} {'Save%':>7} {'P@5':>6} {'hit':>4}")
    print("-" * 78)

    savings = []
    precisions = []
    hits = 0
    cortex_token_list = []

    for query, expect in QUERIES:
        context, result = cortex.recall(query, lang="pt")
        ctok = _count_tokens(context)
        cortex_token_list.append(ctok)
        save = (baseline_tokens - ctok) / baseline_tokens * 100 if baseline_tokens else 0
        savings.append(save)

        returned = result.memories
        relevant_flags = [expect.lower() in (m.what or "").lower() for m in returned]
        p_at_5 = (sum(relevant_flags[:5]) / min(5, len(returned))) if returned else 0.0
        precisions.append(p_at_5)
        hit = any(relevant_flags)
        hits += 1 if hit else 0

        precisions[-1] = p_at_5
        print(f"{query[:42]:<42} {ctok:>10} {save:>6.1f}% {p_at_5:>6.2f} {'✓' if hit else '✗':>4}")

    n = len(QUERIES)
    avg_cortex = sum(cortex_token_list) / n
    avg_save = sum(savings) / n
    avg_p = sum(precisions) / n
    recall_pct = hits / n * 100

    print("-" * 78)
    print(f"\nRESUMO ({n} queries):")
    print(f"  Tokens/turno:   baseline={baseline_tokens}  →  cortex(média)={avg_cortex:.0f}")
    print(f"  Economia média: {avg_save:.1f}%  de tokens injetados por turno")
    print(f"  Precisão@5:     {avg_p:.2f}  (fração dos retornados que são relevantes)")
    print(f"  Recall (hit):   {recall_pct:.0f}%  (queries que acharam o chunk certo)")
    print()
    # Cumulative view over a session of N turns
    print(f"  Em uma sessão de {n} turnos:")
    print(f"    baseline injeta {baseline_tokens * n} tokens acumulados")
    print(f"    cortex   injeta {sum(cortex_token_list)} tokens acumulados")
    print(f"    → {(1 - sum(cortex_token_list)/(baseline_tokens*n))*100:.1f}% menos tokens no total")


if __name__ == "__main__":
    main()
