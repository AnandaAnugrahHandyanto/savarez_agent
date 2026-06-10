# DeepSWE Routing Data — Why Model Routing Matters

## The Evidence

DeepSWE (deepswe.datacurve.ai) is the only contamination-free, real-complexity coding benchmark. Tasks are written from scratch, require 5.5× more code than SWE-bench Pro, and span 91 repositories across 5 languages.

## Key Finding: Models Collapse on Real Engineering Tasks

| Model | SWE-bench Pro | DeepSWE | Collapse |
|-------|:------------:|:-------:|:--------:|
| GPT-5.5 (xhigh) | 58.6% | **70%** | +11 — improves |
| GPT-5.4 (xhigh) | 57.7% | **56%** | −2 — holds |
| Claude Opus 4.7 | 64.3% | 54% | −10 |
| MiniMax M3 | 59.0% | 20% | **−39** |
| DeepSeek V4-Pro | 55.4% | **8%** | **−47** |

**Budget models that look competitive on SWE-bench Pro collapse on real tasks.** V4-Pro drops from 55% to 8%. M3 drops from 59% to 20%. The gap between "good enough" and "actually works" is invisible on contaminated benchmarks.

## Cost per Solved Task (DeepSWE)

| Model | Pass@1 | Avg Cost/Task | Cost per Solve |
|-------|:------:|:------------:|:--------------:|
| GPT-5.4 | 56% | $4.38 | **$7.82** |
| GPT-5.5 | 70% | $6.61 | $9.44 |
| GPT-5.4-Mini | 24% | $2.08 | $8.67 |
| Claude Opus 4.7 | 54% | $18.19 | $33.69 |
| MiniMax M3 | 20% | $5.57 | $27.85 |
| DeepSeek V4-Pro | 8% | $4.22 | **$52.75** |

V4-Pro is 6.7× more expensive per solved task than GPT-5.4 despite being 17× cheaper per token — because it barely solves anything.

## Terminal-Bench (Agentic CLI)

| Model | Score | $/1M Output |
|-------|:-----:|:-----------:|
| GPT-5.5 | 82.7% | $30.00 |
| DeepSeek V4-Pro | 67.9% | $0.87 |

V4-Pro is competitive at tool orchestration. The routing strategy preserves V4-Pro for CLI/tool work while dispatching coding to GPT-5.4+.

## Sources

- DeepSWE Leaderboard: https://deepswe.datacurve.ai/
- DeepSWE Blog: https://deepswe.datacurve.ai/blog
- SWE-bench Pro Leaderboard: https://codingfleet.com/blog/swe-bench-pro-leaderboard-2026/
- DeepSeek V4 Technical Report: https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf
- DeepSeek V4 Blog: https://huggingface.co/blog/deepseekv4
- Kilo Leaderboard: https://kilo.ai/leaderboard
- Vellum LLM Leaderboard: https://www.vellum.ai/llm-leaderboard
