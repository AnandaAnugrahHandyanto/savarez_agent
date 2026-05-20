---
title: "RL Training"
sidebar_label: "RL Training"
sidebar_position: 9
---

# RL Training

Hermes can generate agent trajectories that are useful for reinforcement learning, evaluation, and fine-tuning workflows. Treat this as an advanced workflow: first get normal sessions, tools, and provider routing working, then export trajectories and feed them into your training stack.

:::info Experimental surface
Hermes does not hide that RL pipelines are sharp tools. Use this page as the product entrypoint for trajectory generation and RL-oriented exports; model-specific training recipes live in the optional ML skills and external training frameworks.
:::

## What Hermes Provides

Hermes helps with the data side of RL and post-training workflows:

- **Session trajectories** — conversations, tool calls, tool results, and final answers saved as structured records.
- **Batch processing** — run many prompts through the agent to create comparable trajectories.
- **ShareGPT-compatible exports** — convert sessions into JSONL datasets for downstream tooling.
- **Provider routing** — run generation/evaluation on one provider and auxiliary tasks on cheaper models.
- **Skills** — load domain procedures so trajectories include consistent expert behavior.

Hermes does not magically make bad prompts into good training data. The quality of the resulting dataset still depends on task design, verification, filtering, and evaluation.

## Recommended Workflow

1. **Configure a reliable model/provider**

   Start with [Configuration](../configuration.md) and [Provider Routing](provider-routing.md). For expensive reasoning models, configure cheaper auxiliary models before generating many trajectories.

2. **Create representative tasks**

   Use prompts that match the behavior you actually want to train or evaluate. Prefer tasks with verifiable outputs over vague chat transcripts.

3. **Run trajectories through batch processing**

   Use [Batch Processing](batch-processing.md) when you want repeatable, multi-prompt runs instead of ad hoc sessions.

4. **Export sessions**

   Use [Sessions](../sessions.md) to inspect and export the relevant runs:

   ```bash
   hermes sessions export trajectories.jsonl
   ```

5. **Filter and evaluate**

   Remove failed, low-signal, unsafe, or unverified trajectories before training. Keep the raw exports as audit artifacts.

6. **Train outside Hermes or with ML skills**

   For training mechanics, use the optional ML skills for TRL, Axolotl, Unsloth, vLLM, and evaluation harnesses where appropriate.

## Good Trajectory Sources

High-signal RL/evaluation data usually comes from tasks with clear success criteria:

- code changes with tests
- document extraction with known expected fields
- tool-use workflows with explicit receipts
- web research with cited sources
- debugging sessions with reproducible failures and fixes
- structured outputs validated by schemas

Low-signal sources:

- generic chat
- unverified summaries
- tasks where the assistant guessed
- long sessions with unrelated context mixed together
- tool failures summarized as success

## Verification Checklist

Before treating a trajectory as training data:

- Did the agent use the required tools instead of guessing?
- Are file edits, commands, or external actions verified?
- Are secrets absent or redacted?
- Is the final answer consistent with tool receipts?
- Can the task outcome be scored by tests, validators, or human review?
- Is the task representative of the behavior you want more of?

## Related Docs

- [Batch Processing](batch-processing.md)
- [Sessions](../sessions.md)
- [Provider Routing](provider-routing.md)
- [Fallback Providers](fallback-providers.md)
- [Trajectory Format](../../developer-guide/trajectory-format.md)
- [LM Evaluation Harness skill](../skills/bundled/mlops/mlops-evaluation-lm-evaluation-harness.md)
- [TRL Fine-Tuning skill](../skills/optional/mlops/mlops-training-trl-fine-tuning.md)
