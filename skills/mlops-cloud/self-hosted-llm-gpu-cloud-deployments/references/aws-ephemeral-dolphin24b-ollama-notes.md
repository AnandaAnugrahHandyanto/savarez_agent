# AWS ephemeral Dolphin 24B / Ollama notes

Concrete example for short-lived self-hosted inference on AWS.

## Goal shape
- Host a 24B-class uncensored/generalist model for a few hours.
- Expose an OpenAI-compatible endpoint for Hermes.
- Keep cost sane.

## Practical recommendation from this session
- Model family: `Dolphin3.0-Mistral-24B` / `Dolphin-Mistral-24B`
- Runtime: Ollama with a GGUF quantization
- Practical quantization target: `Q4_K_M`
- Preferred instance: `g6.8xlarge`
- Preferred usage pattern: on-demand for 2–5 hour sessions, terminate after use

## Why this pairing
- 24B full-weight serving is heavier and costlier than needed for casual sessions.
- GGUF + Ollama cuts setup time and complexity sharply.
- `g6.8xlarge` is a practical middle ground for a single-user endpoint.

## Real blocker discovered
On this AWS account, the immediate blocker was not region support or AMI selection — it was GPU quota.

Relevant quota codes:
- `L-DB2E81BA` — Running On-Demand G and VT instances
- `L-3819A6DF` — All G and VT Spot Instance Requests

Observed state during the session:
- `us-east-1`: on-demand G/VT `0.0`, spot G/VT `0.0`
- spot and on-demand quota requests were submitted and remained at `CASE_OPENED`

Lesson: if both quotas are zero, do not keep discussing launch mechanics as if the instance can be started immediately.

## Region scan takeaway
A scan found `g6.8xlarge` offered in multiple regions, including `us-east-1`, `us-east-2`, `us-west-2`, `eu-central-1`, `ca-central-1`, `ap-south-1`, `ap-northeast-1`, `ap-northeast-2`, `eu-west-2`, `eu-west-3`, `eu-north-1`, `sa-east-1`, `ap-southeast-2`, and `ap-southeast-5`.

Key interpretation: this only proves the instance type is offered in-region, not that the account can launch it there.

## Cost framing that helped
For bursty use, hourly/session cost is more useful than monthly cost.

Example `g6.8xlarge` on-demand numbers observed in `us-east-1` during the session:
- about `$2.0144/hr`
- 2h: about `$4.03`
- 3h: about `$6.04`
- 4h: about `$8.06`
- 5h: about `$10.07`

Spot looked cheaper, but on-demand was still the better recommendation for short interactive sessions because interruption risk was not worth the hassle.

## Security pattern used
- dedicated EC2 key pair
- dedicated security group
- ingress on `22/tcp` and `11434/tcp`
- both restricted to the user’s current public IP as `/32`

This is a good default for personal self-hosted inference.

## Hermes hookup pattern
For Ollama-backed self-hosting:
- expose Ollama on `0.0.0.0:11434`
- use the OpenAI-compatible path at `/v1`
- point Hermes custom-provider `base_url` to `http://PUBLIC_IP:11434/v1`
- keep the served model name stable, e.g. `dolphin3-24b`

## Operational pattern worth reusing
When quota approval is the only blocker but the user wants forward motion:
1. prepare the security group, key pair, and bootstrap script now
2. prepare a one-command launcher now
3. create a quota watcher that polls periodically
4. auto-launch when quota becomes sufficient

This preserves momentum without pretending the quota blocker can be brute-forced away.
