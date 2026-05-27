---
title: RL Training
description: The integrated RL training pipeline has been removed from Hermes Agent. This page points to alternatives.
---

# RL Training

The integrated RL training pipeline (Tinker-Atropos) has been removed from Hermes Agent. The `rl_*` tools, environments, and the `tinker-atropos` submodule are no longer available.

## What was removed

- `rl_list_environments`, `rl_select_environment`, `rl_start_training`, `rl_check_status`, `rl_stop_training`, `rl_get_results`, `rl_test_inference`, and other `rl_*` tools
- The `environments/` directory (Atropos RL environments)
- The `tinker-atropos` git submodule
- `rl_cli.py` and `tools/rl_training_tool.py`

## Alternatives

For RL training on language models, use these standalone frameworks:

| Framework | Description |
|-----------|-------------|
| [TRL](https://huggingface.co/docs/trl) | Transformer Reinforcement Learning — GRPO, PPO, DPO |
| [OpenRLHF](https://github.com/OpenRLHF/OpenRLHF) | Scalable RLHF/GRPO with Ray + vLLM |
| [slime](https://github.com/THUDM/slime) | Megatron-LM + SGLang for RL scaling |

## Skills still available

Hermes Agent ships optional skills for ML training workflows:

- **[TRL Fine-Tuning](/user-guide/skills/optional/mlops/mlops-training-trl-fine-tuning)** — SFT, DPO, PPO, GRPO with TRL
- **[Axolotl](/user-guide/skills/optional/mlops/mlops-training-axolotl)** — YAML-driven fine-tuning for 100+ models
- **[Slime RL Training](/user-guide/skills/optional/mlops/mlops-slime)** — Megatron-LM + SGLang RL scaling

## Trajectory format

Hermes Agent still saves conversation trajectories in ShareGPT-compatible JSONL format, suitable as training data. See [Trajectory Format](/developer-guide/trajectory-format) for details.
