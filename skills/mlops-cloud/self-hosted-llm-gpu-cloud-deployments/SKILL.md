---
name: self-hosted-llm-gpu-cloud-deployments
description: Deploy self-hosted LLMs on cloud GPUs with pragmatic provider selection, quota checks, cost framing, and fallback strategy for short-lived sessions.
---

# Self-hosted LLM GPU cloud deployments

Use this when the user wants to run an open model on rented cloud GPUs (AWS, RunPod, etc.), compare hosting options, or wire a self-hosted model into an OpenAI-compatible client.

## Trigger signals
- "Run this model on AWS / RunPod / cloud GPU"
- "How much will it cost for 2–5 hours?"
- "Which GPU should I pick for this model?"
- "Can Hermes / my client connect to a self-hosted endpoint?"
- "Should I wait for AWS or use another provider?"

## Core principle
Do not start with generic model chatter when the user is asking about deployment. Start with:
1. provider constraints,
2. GPU/VRAM fit,
3. hourly cost for the requested session length,
4. operational blockers,
5. fallback path.

If the conversation is already anchored on AWS, keep answers AWS-framed unless the user explicitly pivots. If comparing models mid-deployment thread, answer in terms of AWS suitability, instance fit, and cost first.

## Workflow
1. **Clarify the real goal**
   - Short-lived testing (2–5h) vs always-on serving.
   - Cheapest viable path vs AWS-native learning.
   - API compatibility needs (OpenAI-compatible, Ollama, vLLM, etc.).
2. **Check the hard blockers before doing design work**
   - Account quotas/capacity limits.
   - Region support for the target instance family.
   - Whether the target GPU class is even launchable on the current account.
3. **Fit the model to a practical GPU tier**
   - Prefer quantized deployment for 20B–30B models when the user wants cheap short sessions.
   - Recommend the smallest GPU class that leaves a bit of headroom, not the biggest GPU available.
4. **Price the real session**
   - Compute the user’s requested time window (for example 2h/3h/4h/5h), not just monthly/day rates.
   - Put the cloud options side by side so the tradeoff is obvious.
5. **Pick runtime by operational goal**
   - **Ollama** when the user wants the easiest path and can tolerate its API/runtime conventions.
   - **vLLM** when the user wants a cleaner OpenAI-compatible serving layer and higher-throughput inference.
6. **If AWS is blocked, say it plainly**
   - Don’t keep theorizing about instance types after quotas are confirmed as zero.
   - Pivot to another provider if the user values time-to-first-token more than AWS-specific practice.
7. **Keep the original path warm**
   - If the user still wants AWS eventually, leave quota requests/watchers/scripts in place while using a faster temporary provider.

## AWS-specific playbook

### First checks
- Check **service quotas** before assuming any EC2 GPU launch is possible.
- For short-lived single-GPU sessions, G-family quotas are often the blocker.
- Also verify that the target instance type is offered in the chosen region/AZ.

### Durable pitfalls
**Instance offering availability is not enough.** A region can offer `g6.8xlarge` while the account still has zero GPU quota and cannot launch anything.

**`CASE_CLOSED` is not approval.** For AWS Service Quotas GPU requests, do not infer success from a closed request/case. Always verify the live quota value with `get-service-quota` for the exact quota code. A request for `32` vCPUs can show `CASE_CLOSED` while both `All G and VT Spot Instance Requests` (`L-3819A6DF`) and `Running On-Demand G and VT instances` (`L-DB2E81BA`) remain `0.0`, meaning the launch path is still blocked.

**Support cases may be unavailable.** `aws support describe-cases` requires a Premium Support plan. Prefer Service Quotas APIs (`list-requested-service-quota-change-history`, `get-service-quota`) for quota status checks unless Support access is known to exist.

### Practical answer framing
When the user asks "what GPU can I use?" answer in two layers:
1. what the model would ideally use,
2. what the account can actually launch right now.

### Short-session recommendation pattern
For a user who wants a model for a few hours and then to stop it:
- prefer **on-demand** over spot when interruption risk would be annoying,
- estimate total session spend directly,
- recommend termination/shutdown immediately after use.

### Ephemeral EC2 inference pattern
Use this AWS sub-playbook when the deployment is intentionally short-lived and the target client is Hermes or another OpenAI-compatible tool:
1. Verify AWS caller identity, profile, and region before changing anything.
2. Check G/VT on-demand and spot quotas (`L-DB2E81BA`, `L-3819A6DF`) before designing launch mechanics.
3. If quotas are zero, treat quota approval as the blocker; prepare scripts/watchers only if that preserves momentum.
4. For 20B-30B quantized experiments, evaluate `g6.8xlarge` first, with `g5.12xlarge`/`g6.12xlarge` as fallbacks only when model/context demands it.
5. Prefer Ollama + GGUF for the lowest-friction single-user endpoint; prefer vLLM when throughput, batching, or HF-format serving matters.
6. Use a dedicated key pair and security group; restrict SSH and inference ports to the current public IP `/32` by default.
7. Expose OpenAI-compatible endpoints deliberately: Ollama commonly serves at `http://PUBLIC_IP:11434/v1`.
8. Create a terminate/auto-shutdown path before declaring the deployment safe.
9. If using a cron/quota watcher that can auto-launch cloud compute, treat it as billing-adjacent: make the script idempotent, print only on state changes, keep output silent while blocked, and recommend pausing or adding a manual confirmation gate once the user no longer wants automatic launch.

For a concrete 24B Dolphin/Ollama AWS example, see `references/aws-ephemeral-dolphin24b-ollama-notes.md`.

## RunPod / alternate provider playbook
Use alternate providers when:
- AWS quotas are zero or slow,
- the user wants fast results today,
- the deployment is experimental or short-lived.

For 24B-class quantized models, start by looking at **48 GB VRAM** GPUs. Recommend in value order based on live pricing/availability, then compute the requested session cost.

## Model-sizing heuristics
- **7B–8B**: cheap testing, low-cost cloud GPUs, easier first deployment.
- **20B–30B quantized**: strong practical tradeoff for cloud rental.
- **70B+**: only recommend when the user explicitly accepts much higher cost and slower setup.

## Communication rules for this user
- Be direct and cost-first.
- If the user is frustrated that the answer drifted away from the active cloud context, snap back to that context immediately and answer there.
- Prefer blunt practical recommendations over open-ended option dumps.

## Verification
Before saying a plan is viable, verify:
- quota/capacity blockers,
- region/instance support,
- session cost math,
- runtime/API fit for the client that will consume the model.

## References
- `references/aws-quota-and-runpod-short-session-notes.md` — quota codes, blocker pattern, and practical cost heuristics from a real deployment thread.
- `references/aws-ephemeral-dolphin24b-ollama-notes.md` — concrete 24B-class Dolphin/Ollama EC2 example covering `g6.8xlarge`, quota blockers, OpenAI-compatible Ollama hookup, restricted ingress, and short-session pricing.
