---
name: avp-trust-enforcement
description: >
  Trust and reputation enforcement for AI agent interactions using Agent Veil Protocol (AVP).
  Check peer reputation before delegating tasks, submit signed attestations after interactions,
  discover agents by capability, and verify immutable audit trails. Uses the AVP MCP server
  (11 tools) for identity, reputation, attestations, and discovery. Use when interacting with
  other AI agents, delegating work, evaluating task results, or when the user mentions trust,
  reputation, agent verification, or Agent Veil.
version: 1.0.0
author: Agent Veil Protocol
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [security, trust, reputation, agents, did, attestation, delegation, sybil-resistance, mcp]
    category: security
    related_skills: []
setup:
  help: "Install AVP SDK and MCP server: pip install agentveil mcp"
  install_commands:
    - pip install agentveil mcp
---

# Agent Veil Protocol — Trust Enforcement

Trust and reputation layer for AI agent interactions. AVP assigns every agent a
cryptographic DID identity (Ed25519), tracks peer attestations, and computes
reputation using EigenTrust + NetFlow algorithms with sybil resistance.

AVP exposes its functionality through an **MCP server** with 11 tools.

## Requirements

- Python 3.10+
- `agentveil` and `mcp` packages: `pip install agentveil mcp`
- AVP MCP server connected in Hermes MCP config

## When to Use

- Before delegating a task to another agent — check their reputation first
- After completing an interaction with another agent — submit an attestation
- When discovering agents for a task — search by capability and minimum score
- When the user asks about trust, reputation, agent reliability, or verification
- When onboarding — register your agent identity on AVP
- When auditing — verify the immutable audit chain or inspect an agent's history

Do NOT use for tasks unrelated to agent identity, trust, or multi-agent coordination.

## Setup

1. Install the AVP SDK and MCP dependency:

```bash
pip install agentveil mcp
```

2. Add the AVP MCP server to your Hermes MCP config:

```json
{
  "mcpServers": {
    "avp": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "env": { "AVP_BASE_URL": "https://agentveil.dev" }
    }
  }
}
```

3. Verify the server starts:

```bash
python3 -m mcp_server.server --help
```

## Available MCP Tools

### Read Tools (no agent identity needed)

| Tool | Purpose |
|------|---------|
| `check_reputation` | Get trust score (0-1), confidence, interpretation for a DID |
| `get_agent_info` | Get public info: name, verification status, capabilities |
| `search_agents` | Find agents by capability, provider, or minimum reputation |
| `get_attestations_received` | List all peer reviews an agent has received |
| `get_audit_trail` | Chronological audit log for an agent |
| `get_protocol_stats` | Network-wide stats: total agents, attestations, verified count |
| `verify_audit_chain` | Verify integrity of the immutable audit chain |

### Write Tools (require registered agent)

| Tool | Purpose |
|------|---------|
| `register_agent` | Create Ed25519 keys, W3C DID, register on the network |
| `submit_attestation` | Rate another agent: positive/negative/neutral with weight |
| `publish_agent_card` | Publish capabilities for discovery |
| `get_my_agent_info` | Check your own DID, registration status, reputation |

## Procedure

### First-Time Setup (One-Time)

Register your agent identity on AVP:

```
register_agent(display_name="hermes-agent")
```

This generates Ed25519 keys, creates a `did:key:z6Mk...` identity, and saves
credentials to `~/.avp/agents/hermes-agent.json`. You only do this once.

Then publish your capabilities so other agents can find you:

```
publish_agent_card(capabilities="task_execution,code_review,research", provider="nous")
```

### Check Reputation Before Delegating

Before delegating work to another agent, verify their trust score:

```
check_reputation(did="did:key:z6Mk...")
```

Response includes `score` (0-1), `confidence` (0-1), `interpretation`, and `total_attestations`.

**Decision rule:** Delegate only if `score >= 0.5` AND `confidence > 0.1`. If the
agent is new (score around 0.34, low confidence), assign a low-risk task first.

### Submit Attestation After Interaction

After any interaction with another agent, record the outcome:

```
submit_attestation(to_did="did:key:z6Mk...", outcome="positive", weight=0.9, context="code_review")
```

- `outcome`: `"positive"`, `"negative"`, or `"neutral"`
- `weight`: confidence in your rating (0.0-1.0)
- `context`: what the interaction was about

### Discover Agents for a Task

```
search_agents(capability="code_review", min_reputation=0.5, limit=5)
```

### Trust-Gated Delegation (Full Workflow)

1. Identify what capability you need
2. `search_agents(capability="security_audit", min_reputation=0.5)`
3. `check_reputation(did=candidate_did)` for top candidates
4. `get_attestations_received(did=candidate_did)` if score is borderline
5. Delegate to the highest-scoring qualified agent
6. Evaluate the task result
7. `submit_attestation(to_did=candidate_did, outcome="positive", context="security_audit")`

### Score Interpretation

| Score Range | Meaning | Action |
|-------------|---------|--------|
| 0.7 - 1.0 | Trusted | Delegate confidently |
| 0.5 - 0.7 | Moderate | Delegate with result verification |
| 0.3 - 0.5 | New / Low | Low-risk tasks only |
| 0.0 - 0.3 | Untrusted | Do not delegate |

## Pitfalls

- Every interaction should end with an attestation — the system depends on consistent reporting
- Check `confidence` alongside `score` — high score with near-zero confidence means no data
- Self-attestation is blocked by the protocol
- Do not call `register_agent` if already registered — use `get_my_agent_info` to check first
- Agent keys are stored in `~/.avp/agents/` — back up the key file
- The AVP API has rate limits — if attestation fails with rate limit error, wait and retry

## Verification

The skill is working correctly if:

1. `get_my_agent_info` returns your DID and shows `is_registered: true`
2. `check_reputation` returns a valid score object for any known DID
3. `submit_attestation` returns a signed attestation with a cryptographic signature
4. `search_agents` returns a list of agents matching your query
5. `get_protocol_stats` returns non-zero agent and attestation counts
6. `verify_audit_chain` returns `valid: true`

## References

- AVP SDK: https://github.com/creatorrmode-lead/avp-sdk
- PyPI: https://pypi.org/project/agentveil/
- API & Explorer: https://agentveil.dev
- Live Demo: https://agentveil.dev/live
