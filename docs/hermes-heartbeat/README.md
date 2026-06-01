# Hermes Heartbeat

Goal: Add a lightweight proactive heartbeat system to Hermes-Agent.

Status:
- Discovery: Complete
- Implementation Spec v0.1: Drafted for Review
- Implementation: In Progress

Operator enablement:

1. Enable the standalone plugin: `hermes plugins enable heartbeat`
2. Add `heartbeat.enabled: true` to `~/.hermes/config.yaml`
3. Run the gateway. Automatic Heartbeat scheduling is gateway-hosted in v0.1.

Read order:

1. 01-Discovery/Hermes_Heartbeat_Discovery_Spec_v0.1.md
2. 01-Discovery/Hermes_Heartbeat_Codex_Tasking.md
3. 01-Discovery/Hermes_Heartbeat_Research_Log.md
4. 02-Specs/Hermes_Heartbeat_Implementation_Spec_v0.1.md
5. 02-Specs/Hermes_Heartbeat_SDD_v0.2.md

Codex must review the Implementation Spec before implementation.
