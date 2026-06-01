# Hermes Heartbeat

Goal: Add a lightweight proactive heartbeat system to Hermes-Agent.

Status:
- Discovery: Complete
- Implementation Spec v0.1: Implemented
- Implementation: Ready for live gateway smoke testing

Operator enablement:

1. Enable the standalone plugin: `hermes plugins enable heartbeat`
2. Add `heartbeat.enabled: true` to `~/.hermes/config.yaml`
3. Run the gateway. Automatic Heartbeat scheduling is gateway-hosted in v0.1.

Operator notes:

- Configure `heartbeat.delivery.targets` to send external notifications.
- With no delivery targets, accepted findings still enter the durable inbox and
  are injected into later Main-agent turns.
- Restart the gateway after changing `interval_minutes` or `jitter_minutes`;
  scheduling values are read when the plugin registers.

Read order:

1. 01-Discovery/Hermes_Heartbeat_Discovery_Spec_v0.1.md
2. 01-Discovery/Hermes_Heartbeat_Codex_Tasking.md
3. 01-Discovery/Hermes_Heartbeat_Research_Log.md
4. 02-Specs/Hermes_Heartbeat_Implementation_Spec_v0.1.md
5. 02-Specs/Hermes_Heartbeat_SDD_v0.2.md

Codex must review the Implementation Spec before implementation.
