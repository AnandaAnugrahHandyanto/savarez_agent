"""Compare Context Pager vs built-in ContextCompressor on realistic data.

Measures:
  - Messages in → out
  - Compression ratio
  - Execution time
  - Token/char budget
  - Whether compression is lossless or lossy
  - LLM calls vs hash lookups
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from typing import Any, Dict, List

# Ensure we can import from the hermes-agent repo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from plugins.context_engine.context_pager.engine import ContextPagerEngine
from plugins.context_engine.context_pager.store import SQLiteStore
from plugins.context_engine.context_pager.dedup import (
    hash_tool_content,
    extract_turns,
    apply_dedup_compression,
)

# ---------------------------------------------------------------------------
# Build realistic conversation data
# ---------------------------------------------------------------------------

def _make_tool_output(tool_name: str, content: str, tool_call_id: str) -> Dict:
    return {
        "role": "tool",
        "content": content,
        "tool_call_id": tool_call_id,
        "name": tool_name,
    }

def _make_assistant_with_tool(tool_id: str) -> Dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": tool_id, "type": "function",
                         "function": {"name": "web_search", "arguments": "{}"}}],
    }


# Three test scenarios of increasing complexity
SCENARIOS = {}


def _build_simple_conversation():
    """10 turns, some repeated tool outputs."""
    msgs = [{"role": "system", "content": "You are a helpful assistant."}]
    for i in range(10):
        msgs.append({"role": "user", "content": f"Question {i}: what is the weather?"})
        msgs.append(_make_assistant_with_tool(f"c{i}"))
        if i % 3 == 0:
            msgs.append(_make_tool_output("weather", '{"temp": 22, "condition": "sunny"}', f"c{i}"))
        elif i % 3 == 1:
            msgs.append(_make_tool_output("weather", '{"temp": 15, "condition": "rain"}', f"c{i}"))
        else:
            msgs.append(_make_tool_output("weather", '{"temp": 22, "condition": "sunny"}', f"c{i}"))
        msgs.append({"role": "assistant", "content": f"Answer {i}: The weather is..."})
    return msgs


def _build_medium_conversation():
    """25 turns, many repeated tool outputs, 2 unique ones."""
    msgs = [{"role": "system", "content": "You are a helpful assistant with many tools."}]
    outputs = {
        0: '{"results": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}',
        1: '{"results": [{"id": 3, "name": "Charlie"}]}',
        2: '{"results": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}',  # same as 0
        3: '{"results": []}',
    }
    for i in range(25):
        msgs.append({"role": "user", "content": f"Query {i}: search for something"})
        msgs.append(_make_assistant_with_tool(f"c{i}"))
        output_key = i % 4
        msgs.append(_make_tool_output("search", outputs[output_key], f"c{i}"))
        msgs.append({"role": "assistant", "content": f"Found {output_key} results."})
    return msgs


def _build_large_conversation():
    """50 turns with high repetition — 3 distinct outputs repeated 15+ times each."""
    msgs = [{"role": "system", "content": "You are a data-analysis assistant."}]
    outputs = {
        "status_ok": '{"status": "ok", "data": {"count": 42, "items": ["a","b","c"]}}',
        "status_err": '{"status": "error", "message": "rate limited"}',
        "data_large": '{"data": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}',
    }
    for i in range(50):
        msgs.append({"role": "user", "content": f"Analysis step {i}: run query"})
        msgs.append(_make_assistant_with_tool(f"c{i}"))
        if i % 5 == 3:
            msgs.append(_make_tool_output("api_call", outputs["status_err"], f"c{i}"))
        elif i % 3 == 0:
            msgs.append(_make_tool_output("api_call", outputs["status_ok"], f"c{i}"))
        else:
            msgs.append(_make_tool_output("api_call", outputs["data_large"], f"c{i}"))
        msgs.append({"role": "assistant", "content": f"Step {i} complete."})
    return msgs


SCENARIOS["simple"] = _build_simple_conversation()
SCENARIOS["medium"] = _build_medium_conversation()
SCENARIOS["large"] = _build_large_conversation()


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------

def char_len(msgs: List[Dict]) -> int:
    """Total character length of all messages."""
    total = 0
    for m in msgs:
        c = m.get("content", "")
        if isinstance(c, str):
            total += len(c)
        elif isinstance(c, (dict, list)):
            total += len(json.dumps(c))
    return total


def count_tool_msgs(msgs: List[Dict]) -> int:
    return sum(1 for m in msgs if m.get("role") == "tool")


def count_unique_tool_contents(msgs: List[Dict]) -> int:
    """Number of unique tool output hashes."""
    hashes = set()
    for m in msgs:
        if m.get("role") == "tool":
            hashes.add(hash_tool_content(m.get("content", "")))
    return len(hashes)


# ---------------------------------------------------------------------------
# Test Context Pager (lossless dedup)
# ---------------------------------------------------------------------------

def benchmark_context_pager(scenario_name: str, msgs: List[Dict]) -> Dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        engine = ContextPagerEngine(
            protect_first_n=2,
            protect_last_n=4,
            threshold_percent=0.50,
            context_length=200_000,
            sqlite_path=db_path,
            openviking_enabled=False,
        )

        engine.on_session_start(scenario_name)

        # First pass: cold DB (no pre-existing hashes — only adjacent-turn merging works)
        start = time.perf_counter()
        result_pass1 = engine.compress(msgs)
        elapsed_pass1 = time.perf_counter() - start
        stubs_pass1 = [m for m in result_pass1
                       if m.get("role") == "tool"
                       and isinstance(m.get("content"), str)
                       and m["content"].startswith("[repeated")]

        # Second pass: warm DB (previous compress stored middle hashes)
        start = time.perf_counter()
        result_pass2 = engine.compress(msgs)
        elapsed_pass2 = time.perf_counter() - start
        stubs_pass2 = [m for m in result_pass2
                       if m.get("role") == "tool"
                       and isinstance(m.get("content"), str)
                       and m["content"].startswith("[repeated")]

        original_len = len(msgs)
        original_chars = char_len(msgs)

        return {
            "engine": "Context Pager (lossless dedup)",
            "scenario": scenario_name,
            "original_messages": original_len,
            "original_chars": original_chars,
            # Pass 1 (cold DB — adjacent-turn merge only)
            "pass1_messages": len(result_pass1),
            "pass1_saved": original_len - len(result_pass1),
            "pass1_ratio": f"{(1 - len(result_pass1) / max(original_len, 1)) * 100:.1f}%",
            "pass1_stubs": len(stubs_pass1),
            "pass1_secs": f"{elapsed_pass1:.4f}",
            # Pass 2 (warm DB — hash dedup also works)
            "pass2_messages": len(result_pass2),
            "pass2_saved": original_len - len(result_pass2),
            "pass2_ratio": f"{(1 - len(result_pass2) / max(original_len, 1)) * 100:.1f}%",
            "pass2_stubs": len(stubs_pass2),
            "pass2_char_saved": original_chars - char_len(result_pass2),
            "pass2_secs": f"{elapsed_pass2:.4f}",
            "llm_calls": 0,
            "lossless": True,
        }


# ---------------------------------------------------------------------------
# Test built-in ContextCompressor (LLM summarization)
# ---------------------------------------------------------------------------

def benchmark_context_compressor(scenario_name: str, msgs: List[Dict]) -> Dict:
    from agent.context_compressor import ContextCompressor

    # ContextCompressor needs a model name even in quiet/benchmark mode
    compressor = ContextCompressor(
        model="test-benchmark",
        quiet_mode=True,
        config_context_length=200_000,
    )

    start = time.perf_counter()
    result = compressor.compress(list(msgs))
    elapsed = time.perf_counter() - start

    original_len = len(msgs)
    original_chars = char_len(msgs)
    compressed_len = len(result)
    compressed_chars = char_len(result)

    # Check if it's lossy — compressor makes new summary messages
    summary_msgs = [m for m in result
                    if isinstance(m.get("content"), str)
                    and (m["content"].startswith("[CONTEXT COMPACTION]")
                         or "compacted" in m["content"][:80])]

    return {
        "engine": "ContextCompressor (LLM summarization)",
        "scenario": scenario_name,
        "original_messages": original_len,
        "compressed_messages": compressed_len,
        "messages_saved": original_len - compressed_len,
        "ratio": f"{(1 - compressed_len / max(original_len, 1)) * 100:.1f}%",
        "original_chars": original_chars,
        "compressed_chars": compressed_chars,
        "chars_saved": original_chars - compressed_chars,
        "char_ratio": f"{(1 - compressed_chars / max(original_chars, 1)) * 100:.1f}%",
        "summary_messages_found": len(summary_msgs),
        "llm_calls": 1 if compressor.compression_count > 0 else 0,
        "lossless": False,
        "elapsed_seconds": f"{elapsed:.4f}",
    }


# ---------------------------------------------------------------------------
# Run all benchmarks
# ---------------------------------------------------------------------------

def print_table(results: List[Dict]):
    """Print a clean comparison table."""
    header = [
        f"{'Engine':<36} {'Scenario':<10} {'In':>4} {'P1/Saved':>9} {'P2/Saved':>9} "
        f"{'Chars↓':>8} {'LLM':>4} {'Lossless':>8} {'P1 Secs':>8} {'P2 Secs':>8}"
    ]
    sep = "─" * len(header[0])
    lines = [sep, header[0], sep]
    for r in results:
        if "Context Pager" in r["engine"]:
            lines.append(
                f"{r['engine']:<36} {r['scenario']:<10} {r['original_messages']:>4} "
                f"{r['pass1_saved']:>+4}/{r['pass1_ratio']:>4} "
                f"{r['pass2_saved']:>+4}/{r['pass2_ratio']:>4} "
                f"{r['pass2_char_saved']:>8,} "
                f"{r['llm_calls']:>4} {str(r['lossless']):>8} {r['pass1_secs']:>8} {r['pass2_secs']:>8}"
            )
        else:
            lines.append(
                f"{r['engine']:<36} {r['scenario']:<10} {r['original_messages']:>4} "
                f"{'—':>9} "
                f"{r['messages_saved']:>+4}/{r['ratio']:>4} "
                f"{r['chars_saved']:>8,} "
                f"{r['llm_calls']:>4} {str(r['lossless']):>8} {'—':>8} {'—':>8}"
            )
    lines.append(sep)
    print("\n".join(lines))


def print_scenario_details(scenario_name: str, msgs: List[Dict]):
    tool_count = count_tool_msgs(msgs)
    unique_count = count_unique_tool_contents(msgs)
    print(f"\n{'='*65}")
    print(f"  SCENARIO: {scenario_name}")
    print(f"{'='*65}")
    print(f"  Total messages:    {len(msgs)}")
    print(f"  Tool messages:     {tool_count}")
    print(f"  Unique tool outs:  {unique_count}")
    print(f"  Duplicate ratio:   {(1 - unique_count / max(tool_count, 1)) * 100:.0f}%")
    print(f"  Total chars:       {char_len(msgs):,}")


if __name__ == "__main__":
    all_results = []

    for name, msgs in SCENARIOS.items():
        print_scenario_details(name, msgs)

        # Context Pager
        r1 = benchmark_context_pager(name, msgs)
        all_results.append(r1)

        # ContextCompressor
        r2 = benchmark_context_compressor(name, msgs)
        all_results.append(r2)

    print(f"\n\n{'='*95}")
    print("  COMPARISON RESULTS")
    print(f"{'='*95}")
    print_table(all_results)

    print(f"\n\n{'='*95}")
    print("  KEY DIFFERENCES")
    print(f"{'='*95}")
    cp = [r for r in all_results if "Pager" in r["engine"]]
    cc = [r for r in all_results if "Compressor" in r["engine"]]

    for cpr, ccr in zip(cp, cc):
        print(f"\n  [{cpr['scenario']}]")
        print(f"    Context Pager (cold):  {cpr['pass1_saved']} msgs saved ({cpr['pass1_ratio']}), "
              f"{cpr['pass1_stubs']} stubs, {cpr['pass1_secs']}s")
        print(f"    Context Pager (warm):  {cpr['pass2_saved']} msgs saved ({cpr['pass2_ratio']}), "
              f"{cpr['pass2_stubs']} stubs, {cpr['pass2_char_saved']:,} chars↓, {cpr['pass2_secs']}s, "
              f"lossless={cpr['lossless']}")
        print(f"    ContextCompressor:    {ccr['messages_saved']} msgs saved ({ccr['ratio']}), "
              f"{ccr['chars_saved']:,} chars, {ccr['llm_calls']} LLM calls, "
              f"lossless={ccr['lossless']}")
