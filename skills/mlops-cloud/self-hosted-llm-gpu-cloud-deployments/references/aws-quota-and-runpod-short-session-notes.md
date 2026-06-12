# AWS quota blocker + RunPod short-session notes

## When AWS is the blocker
For new or lightly used AWS accounts, check EC2 GPU quotas before spending time on detailed launch plans. Durable quota codes used in this session:

- `L-DB2E81BA` — Running On-Demand G and VT instances
- `L-3819A6DF` — All G and VT Spot Instance Requests

Practical lesson: a region can offer the desired GPU instance type and still be unusable because both quota values are `0.0`.

## Useful answer framing
When a user asks cloud questions mid-deployment thread, keep the answer tied to the active provider context. If they ask whether a model is good, answer in terms of:
- whether the current cloud account can run it,
- what instance/GPU tier it needs,
- what it costs for the requested session length.

## Short-session pricing pattern
For short rental sessions, compute direct spend for the requested duration. In this thread, 5-hour examples were the key decision lever.

## RunPod heuristics for 24B-class quantized models
For a 24B-class quantized model, start with 48 GB VRAM GPUs. A practical value order from this session was:
1. A40 48GB
2. RTX A6000 48GB
3. L40S 48GB

This should be re-checked live each session because marketplace pricing moves.

## Operational takeaway
If the user values time-to-first-token more than AWS-native learning, recommend the alternate GPU provider plainly instead of continuing to theorize about blocked AWS capacity.
