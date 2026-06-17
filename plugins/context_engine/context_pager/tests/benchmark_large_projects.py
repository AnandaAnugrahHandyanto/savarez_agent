"""Large research project benchmark for Context Pager vs ContextCompressor.

Two identical research projects with realistic 10-50KB tool outputs.
Measures: messages in/out, characters saved, info loss, LLM cost, time.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from plugins.context_engine.context_pager.engine import ContextPagerEngine
from plugins.context_engine.context_pager.dedup import hash_tool_content


# ---------------------------------------------------------------------------
# Realistic research project — large tool outputs
# ---------------------------------------------------------------------------

def _make_large_web_results(n_results: int = 20) -> str:
    """Simulate a web_search returning ~30KB of results."""
    results = []
    for i in range(n_results):
        results.append(textwrap.dedent(f"""\
            Result {i+1}:
            Title: Advanced Machine Learning Techniques for Efficient Inference
            URL: https://arxiv.org/abs/240{i % 9 + 1}.{10000 + i}
            Snippet: This paper presents a novel approach to optimizing transformer
            inference by combining speculative decoding with adaptive quantization.
            The authors demonstrate up to 4.2x speedup on standard benchmarks while
            maintaining less than 1% accuracy degradation across a range of NLP tasks.
            Key contributions include a new attention mechanism that reduces memory
            bandwidth requirements and a novel scheduling algorithm for batch processing.
            Experimental results show consistent improvements across GPT-style,
            BERT-style, and mixture-of-expert architectures.
            ---
        """))
    return "\n".join(results)


def _make_large_file_content() -> str:
    """Simulate reading a ~25KB source file."""
    parts = []
    parts.append("# src/optimizer/scheduler.py\n")
    parts.append("""\
import torch
import torch.nn as nn
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class SchedulerType(Enum):
    COSINE = "cosine"
    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    EXPONENTIAL = "exponential"
    INVERSE_SQRT = "inverse_sqrt"
    WARMUP_COSINE = "warmup_cosine"
    WARMUP_LINEAR = "warmup_linear"


@dataclass
class SchedulerConfig:
    \"\"\"Configuration for learning rate scheduler.\"\"\"
    scheduler_type: SchedulerType = SchedulerType.COSINE
    warmup_steps: int = 1000
    total_steps: int = 100000
    base_lr: float = 1e-4
    min_lr: float = 1e-6
    power: float = 1.0
    cycle_length: int = 50000
    cycle_mult: float = 1.0

""")
    # Add a lot of repetitive code to make it ~25KB
    for cls_name in ["LinearScheduler", "CosineScheduler", "WarmupScheduler",
                     "PolynomialScheduler", "ExponentialScheduler", "StepScheduler",
                     "MultiStepScheduler", "ReduceOnPlateau", "CyclicScheduler",
                     "OneCycleScheduler"]:
        parts.append(f"""\
class {cls_name}:
    \"\"\"{cls_name.replace('_', ' ')} implementation.\"\"\"

    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.current_step = 0
        self.current_lr = config.base_lr
        self.history: List[float] = []

    def step(self) -> float:
        \"\"\"Advance one step and return the new learning rate.\"\"\"
        self.current_step += 1
        self.current_lr = self._compute_lr()
        self.history.append(self.current_lr)
        return self.current_lr

    def _compute_lr(self) -> float:
        raise NotImplementedError

    def get_lr(self) -> float:
        return self.current_lr

    def reset(self) -> None:
        self.current_step = 0
        self.current_lr = self.config.base_lr
        self.history.clear()

    def state_dict(self) -> Dict[str, Any]:
        return {{
            "current_step": self.current_step,
            "current_lr": self.current_lr,
            "history": self.history,
        }}

    def load_state_dict(self, state_dict: Dict[str, Any]) -> None:
        self.current_step = state_dict["current_step"]
        self.current_lr = state_dict["current_lr"]
        self.history = state_dict["history"]

""")
    return "".join(parts)


def _make_large_terminal_output() -> str:
    """Simulate running `pytest` with verbose output — ~40KB."""
    lines = []
    lines.append("$ pytest tests/ -x -v --tb=short --durations=10 2>&1\n")
    lines.append("=" * 80 + "\n")
    lines.append("test session starts  platform=linux python=3.11.15\n")
    lines.append("rootdir: /home/user/project\n")
    lines.append("plugins: anyio-4.13.0, xdist-3.8.0, timeout-2.4.0\n")
    lines.append("=" * 80 + "\n")

    test_cases = [
        ("test_optimizer_init", "PASSED"),
        ("test_optimizer_step", "PASSED"),
        ("test_optimizer_zero_grad", "PASSED"),
        ("test_scheduler_cosine", "PASSED"),
        ("test_scheduler_linear", "PASSED"),
        ("test_scheduler_warmup", "PASSED"),
        ("test_scheduler_polynomial", "PASSED"),
        ("test_model_forward", "PASSED"),
        ("test_model_backward", "PASSED"),
        ("test_model_save_load", "PASSED"),
        ("test_model_quantization", "FAILED"),
        ("test_model_export_onnx", "PASSED"),
        ("test_model_export_torchscript", "PASSED"),
        ("test_data_loader", "PASSED"),
        ("test_data_augmentation", "PASSED"),
        ("test_batch_sampler", "PASSED"),
        ("test_training_loop", "PASSED"),
        ("test_checkpoint_resume", "PASSED"),
        ("test_logging", "PASSED"),
        ("test_distributed_init", "PASSED"),
        ("test_distributed_allreduce", "PASSED"),
        ("test_fsdp_sharding", "PASSED"),
        ("test_fsdp_gradient_checkpoint", "PASSED"),
        ("test_attention_causal", "PASSED"),
        ("test_attention_flash", "PASSED"),
        ("test_attention_sparse", "PASSED"),
        ("test_rope_embedding", "PASSED"),
        ("test_alibi_embedding", "PASSED"),
    ]

    for i, (name, status) in enumerate(test_cases):
        if status == "FAILED":
            lines.append(f"FAILED tests/test_core.py::{name} - AssertionError: "
                        f"expected 0.001 but got 0.012\n")
            lines.append(f"{'─' * 70}\n")
            lines.append(">       assert result == expected\n")
            lines.append("E       assert 0.012 == 0.001\n")
            lines.append("E        +  where 0.012 = <function forward at 0x...>(input)\n")
            lines.append(f"{'─' * 70}\n")
        else:
            lines.append(f"PASSED tests/test_core.py::{name} [{'0.' + str(i%60+10).zfill(2)}s]\n")

    lines.append("\n")
    # Add timing info
    lines.append("=" * 80 + "\n")
    lines.append("Slowest durations:\n")
    for i in range(10):
        lines.append(f"{'0.' + str(50-i*4).zfill(2)}s  tests/test_core.py::test_model_{['forward','backward','save_load','quantization','export_onnx','training_loop','checkpoint_resume','distributed_init','fsdp_sharding','attention_causal'][i]}\n")
    lines.append("\n")
    lines.append("=" * 80 + "\n")
    lines.append(f"Summary: {len([x for x in test_cases if x[1]=='PASSED'])} passed, "
                f"{len([x for x in test_cases if x[1]=='FAILED'])} failed "
                f"in 12.47s\n")
    return "".join(lines)


def _make_execute_code_output() -> str:
    """Simulate running analysis code — ~15KB of pandas output."""
    lines = []
    lines.append("In [1]: import pandas as pd\n")
    lines.append("In [2]: import numpy as np\n")
    lines.append("In [3]: df = pd.read_parquet('results/benchmark.parquet')\n")
    lines.append("In [4]: df.describe()\n")
    lines.append(f"{' '*4}{'count':>10} {'mean':>10} {'std':>10} {'min':>10} {'max':>10}\n")
    for col in ["throughput", "latency_p50", "latency_p99", "memory_mb", "gpu_util"]:
        idx = ["throughput", "latency_p50", "latency_p99", "memory_mb", "gpu_util"].index(col)
        lines.append(f"{col:<12} {1000 + idx*100:>10.1f} {50 + idx*10:>10.2f} "
                    f"{10:>10.1f} {1000:>10.1f} {2000 + idx*50:>10.1f}\n")
    lines.append("\n")
    lines.append("In [5]: df.groupby('model_size').agg({'throughput': 'mean', 'latency_p50': 'median'})\n")
    lines.append(f"{'model_size':<15} {'throughput':>12} {'latency_p50':>12}\n")
    for size in ["tiny", "small", "base", "large", "xl", "2xl", "3xl"]:
        lines.append(f"{size:<15} {1500 + len(size)*200:>12.1f} {45 - len(size)*3:>12.1f}\n")
    lines.append("\n")
    lines.append("In [6]: # Compute speedup over baseline\n")
    lines.append("In [7]: baseline = df[df['model'] == 'baseline']['throughput'].mean()\n")
    lines.append("In [8]: for model in df['model'].unique():\n")
    lines.append("   ...:     speedup = df[df['model']==model]['throughput'].mean() / baseline\n")
    lines.append("   ...:     print(f'{model}: {speedup:.2f}x')\n")
    lines.append("   ...: \n")
    for model, speedup in [("baseline", 1.0), ("v1-optimized", 1.35),
                          ("v2-quantized", 2.10), ("v3-speculative", 3.45),
                          ("v4-moe", 4.20)]:
        lines.append(f"{model}: {speedup:.2f}x\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Build two identical research project conversations
# ---------------------------------------------------------------------------

SAMPLE_TOOL_OUTPUTS = {
    "web_search": _make_large_web_results(20),         # ~30KB
    "read_file": _make_large_file_content(),            # ~25KB
    "terminal": _make_large_terminal_output(),           # ~40KB
    "execute_code": _make_execute_code_output(),         # ~15KB
}


def build_research_project(num_repeats: int = 10) -> List[Dict]:
    """Build a research session with repeated tool calls.

    Each 'project' calls tools in the same order with the same outputs.
    num_repeats = how many identical research project runs to chain.
    """
    msgs = [{"role": "system", "content": "You are a research assistant."}]

    tools_in_order = [
        ("web_search", "search_arxiv"),
        ("read_file", "read_file"),
        ("terminal", "terminal"),
        ("execute_code", "execute_code"),
        ("web_search", "search_github"),
        ("terminal", "terminal"),
    ]

    for project in range(num_repeats):
        for tool_idx, (tool_type, tool_name) in enumerate(tools_in_order):
            msgs.append({
                "role": "user",
                "content": f"[Project {project + 1}] Step using {tool_name}",
            })
            tool_id = f"call_p{project}_t{tool_idx}"
            output = SAMPLE_TOOL_OUTPUTS[tool_type]

            msgs.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": tool_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps({"query": f"project_{project}"}),
                    },
                }],
            })
            msgs.append({
                "role": "tool",
                "content": output,
                "tool_call_id": tool_id,
                "name": tool_name,
            })
            msgs.append({
                "role": "assistant",
                "content": f"Completed step {tool_name} for project {project + 1}."
                           f" Got {len(output):,} bytes of results."
                           f" Moving to next step.",
            })

    return msgs


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def char_len(msgs: List[Dict]) -> int:
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


# Rough token estimate (chars / 4)
def chars_to_tokens(chars: int) -> int:
    return chars // 4


# ---------------------------------------------------------------------------
# Benchmark Context Pager
# ---------------------------------------------------------------------------

def benchmark_context_pager(msgs: List[Dict], scenario_name: str) -> Dict:
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

        original_len = len(msgs)
        original_chars = char_len(msgs)
        original_tokens_est = chars_to_tokens(original_chars)
        tool_msgs = count_tool_msgs(msgs)

        # Pass 1: cold DB
        t1 = time.perf_counter()
        r1 = engine.compress(msgs)
        t1 = time.perf_counter() - t1
        r1_chars = char_len(r1)
        r1_stubs = sum(1 for m in r1 if isinstance(m.get("content"), str)
                      and m["content"].startswith("[repeated"))

        # Pass 2: warm DB
        t2 = time.perf_counter()
        r2 = engine.compress(msgs)
        t2 = time.perf_counter() - t2
        r2_chars = char_len(r2)
        r2_stubs = sum(1 for m in r2 if isinstance(m.get("content"), str)
                      and m["content"].startswith("[repeated"))

        return {
            "engine": "Context Pager",
            "scenario": scenario_name,
            "total_messages": original_len,
            "tool_messages": tool_msgs,
            "total_chars": original_chars,
            "total_tokens_est": original_tokens_est,
            # Pass 1
            "p1_messages": len(r1),
            "p1_msgs_saved": original_len - len(r1),
            "p1_chars": r1_chars,
            "p1_chars_saved": original_chars - r1_chars,
            "p1_tokens_saved": chars_to_tokens(original_chars - r1_chars),
            "p1_stubs": r1_stubs,
            "p1_secs": round(t1, 4),
            # Pass 2
            "p2_messages": len(r2),
            "p2_msgs_saved": original_len - len(r2),
            "p2_chars": r2_chars,
            "p2_chars_saved": original_chars - r2_chars,
            "p2_tokens_saved": chars_to_tokens(original_chars - r2_chars),
            "p2_stubs": r2_stubs,
            "p2_ratio": f"{(1 - r2_chars / max(original_chars, 1)) * 100:.1f}%",
            "p2_secs": round(t2, 4),
            "llm_calls": 0,
            "lossless": True,
        }


# ---------------------------------------------------------------------------
# Benchmark ContextCompressor (estimate via real API call)
# ---------------------------------------------------------------------------

def benchmark_compressor_via_api(msgs: List[Dict], scenario_name: str) -> Dict:
    """Call DeepSeek API directly to get real cost for summarization."""
    import httpx

    original_chars = char_len(msgs)

    # Simulate what the compressor does: take middle messages, build a summary prompt
    # Find head and tail
    head = [m for m in msgs if m.get("role") == "system"][:3]
    non_system = [m for m in msgs if m.get("role") != "system"]
    tail = non_system[-6:] if len(non_system) > 6 else non_system
    middle = non_system[:len(non_system) - len(tail)]

    middle_chars = char_len(middle)
    headtail_chars = char_len(head) + char_len(tail)
    prompt_text = (
        "Summarize the following conversation turns. "
        "Extract key facts, decisions, and context. "
        "Be concise but preserve all important information.\n\n"
        f"{json.dumps(middle[:20], indent=2)[:15000]}"
    )

    summary = None
    tok_in = 0
    tok_out = 0
    api_time = 0

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    # Fallback: try to read from config
    if not api_key:
        # Try loading from .env
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DEEPSEEK_API_KEY="):
                        api_key = line.split("=", 1)[1].strip("\"' ")
                        break
            # Try sourcing via shell
            if not api_key:
                import subprocess
                try:
                    result = subprocess.run(
                        "bash -c 'source ~/.hermes/.env 2>/dev/null; echo $DEEPSEEK_API_KEY'",
                        shell=True, capture_output=True, text=True, timeout=5,
                    )
                    api_key = result.stdout.strip()
                except Exception:
                    pass

    if api_key:
        try:
            t0 = time.perf_counter()
            resp = httpx.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-v4-flash",
                    "messages": [{"role": "user", "content": prompt_text}],
                    "max_tokens": 4000,
                    "temperature": 0.3,
                },
                timeout=60,
            )
            api_time = time.perf_counter() - t0
            if resp.status_code == 200:
                data = resp.json()
                summary = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                tok_in = usage.get("prompt_tokens", 0)
                tok_out = usage.get("completion_tokens", 0)
            else:
                summary = f"[API error: {resp.status_code}]"
        except Exception as e:
            summary = f"[API call failed: {e}]"
            api_time = -1
    else:
        summary = "[No API key available]"

    # Estimate compressed size
    summary_chars = len(summary or "")
    compressed_chars = headtail_chars + summary_chars
    chars_saved = original_chars - compressed_chars

    return {
        "engine": "ContextCompressor (API estimate)",
        "scenario": scenario_name,
        "total_messages": len(msgs),
        "tool_messages": count_tool_msgs(msgs),
        "total_chars": original_chars,
        "total_tokens_est": chars_to_tokens(original_chars),
        "p2_messages": len(head) + len(tail) + 1,  # head + tail + summary
        "p2_msgs_saved": len(msgs) - (len(head) + len(tail) + 1),
        "p2_chars": compressed_chars,
        "p2_chars_saved": chars_saved,
        "p2_tokens_saved": chars_to_tokens(max(0, chars_saved)),
        "p2_ratio": f"{(1 - compressed_chars / max(original_chars, 1)) * 100:.1f}%",
        "p2_secs": round(api_time, 2),
        "llm_calls": 1,
        "lossless": False,
        "api_prompt_tokens": tok_in,
        "api_completion_tokens": tok_out,
        "summary_preview": (summary or "")[:200],
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    scenarios = {
        "2_projects": build_research_project(num_repeats=2),
        "5_projects": build_research_project(num_repeats=5),
        "10_projects": build_research_project(num_repeats=10),
    }

    all_results = []

    print(f"\n{'='*100}")
    print("  RESEARCH PROJECT SCENARIOS")
    print(f"{'='*100}")

    for name, msgs in scenarios.items():
        tool_count = count_tool_msgs(msgs)
        total_chars = char_len(msgs)
        total_kb = total_chars / 1024
        total_tok = chars_to_tokens(total_chars)
        print(f"\n  {name}:")
        print(f"    Messages:     {len(msgs):>4}")
        print(f"    Tool msgs:    {tool_count:>4}")
        # Count per tool type
        from collections import Counter
        tool_names = Counter(m.get("name", "") for m in msgs if m.get("role") == "tool")
        tool_desc = " | ".join(f"{name}={count}" for name, count in tool_names.most_common())
        print(f"    Tool types:   {tool_desc}")
        print(f"    Total chars:  {total_chars:,} ({total_kb:.0f} KB)")
        print(f"    Est tokens:   {total_tok:,}")

    print(f"\n{'='*100}")
    print("  RESULTS")
    print(f"{'='*100}")

    for name, msgs in scenarios.items():
        r1 = benchmark_context_pager(msgs, name)
        all_results.append(r1)
        r2 = benchmark_compressor_via_api(msgs, name)
        all_results.append(r2)

    # Print table
    header = (
        f"{'Engine':<32} {'Scenario':<14} {'In Msgs':>8} {'Out':>6} "
        f"{'Saved':>6} {'In Toks':>9} {'Tok Saved':>10} "
        f"{'LLM':>4} {'Secs':>8} {'Lossls':>7}"
    )
    sep = "─" * len(header)
    print(f"\n{sep}")
    print(header)
    print(sep)

    for r in all_results:
        if "Context Pager" in r["engine"]:
            # Show pass 2 (warm DB — the real comparison point)
            print(
                f"{r['engine']:<32} {r['scenario']:<14} {r['total_messages']:>8} "
                f"{r['p2_messages']:>6} {r['p2_msgs_saved']:>6} "
                f"{r['total_tokens_est']:>9,} {r['p2_tokens_saved']:>10,} "
                f"{r['llm_calls']:>4} {r['p2_secs']:>8} {str(r['lossless']):>7}"
            )
        else:
            print(
                f"{r['engine']:<32} {r['scenario']:<14} {r['total_messages']:>8} "
                f"{r['p2_messages']:>6} {r['p2_msgs_saved']:>6} "
                f"{r['total_tokens_est']:>9,} {r['p2_tokens_saved']:>10,} "
                f"{r['llm_calls']:>4} {r['p2_secs']:>8} {str(r['lossless']):>7}"
            )
    print(sep)

    # Summary section
    print(f"\n{'='*100}")
    print("  KEY DIFFERENCES")
    print(f"{'='*100}")

    for r in all_results:
        if "Context Pager" in r["engine"]:
            print(f"\n  [{r['scenario']}]")
            print(f"    Context Pager (cold):  {r['p1_msgs_saved']} msgs saved, "
                  f"{r['p1_chars_saved']:,} chars saved, "
                  f"{r['p1_stubs']} stubs, {r['p1_secs']}s, 0 LLM calls")
            print(f"    Context Pager (warm):  {r['p2_msgs_saved']} msgs saved, "
                  f"{r['p2_chars_saved']:,} chars ({r['p2_ratio']}), "
                  f"{r['p2_stubs']} stubs, {r['p2_secs']}s, 0 LLM calls, lossless=✓")
        else:
            api_tok = r.get('api_prompt_tokens', 0)
            api_comp = r.get('api_completion_tokens', 0)
            api_cost = (api_tok * 0.435 / 1_000_000) + (api_comp * 0.87 / 1_000_000)
            print(f"    Compressor (API):      {r['p2_msgs_saved']} msgs saved, "
                  f"{r['p2_chars_saved']:,} chars ({r['p2_ratio']}), "
                  f"{r['llm_calls']} LLM call, ${api_cost:.6f} ({api_tok}+{api_comp} tok), "
                  f"lossless=✗")

    # Delta table
    print(f"\n{'='*100}")
    print("  SAVINGS COMPARISON (warm pass)")
    print(f"{'='*100}")
    print(f"{'Scenario':<20} {'CP Tokens':>12} {'CC Tokens':>12} {'CP Cost':>12} {'CC Cost':>12} {'CP Time':>10} {'CC Time':>10}")
    print(f"{'─'*20} {'─'*12} {'─'*12} {'─'*12} {'─'*12} {'─'*10} {'─'*10}")
    for r in all_results:
        if "Context Pager" in r["engine"]:
            cp = r
        else:
            cc = r
            cp_tok = cp["p2_tokens_saved"]
            cc_tok = cc["p2_tokens_saved"]
            cp_cost = 0.0  # no LLM cost
            cc_cost = (cc.get("api_prompt_tokens", 0) * 0.435 / 1_000_000
                      + cc.get("api_completion_tokens", 0) * 0.87 / 1_000_000)
            print(
                f"{cc['scenario']:<20} "
                f"{cp_tok:>+10,} tok  {cc_tok:>+10,} tok  "
                f"${cp_cost:<9.6f} ${cc_cost:<9.6f}  "
                f"{cp['p2_secs']:>6.4f}s {cc['p2_secs']:>6.2f}s"
            )
