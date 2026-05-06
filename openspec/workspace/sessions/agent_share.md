# Agent Coordination — Setup / Standby

> **Date**: 2026-05-06 | **Lead**: Leader
> **Team**: {AGENT_B_NAME} ({AGENT_B_IDE}), {AGENT_C_NAME} ({AGENT_C_IDE})
>
> **Project**: `hermes-agent` | **Path**: `/home/ubuntu/workspaces/oss/hermes-agent`
> **Serena Project**: `hermes-agent` (for `activate_project`)
> **Shared file location**: `/home/ubuntu/workspaces/oss/hermes-agent/openspec/workspace/sessions/agent_share.md`

---

## 📌 Situation

| Item            | Detail                      |
| :-------------- | :-------------------------- |
| **Objective**   | Enable user-friendly configuration (email/channel names) for MS Teams via config.yaml |
| **Scope**       | hermes-agent (Teams Connector) |
| **Blockers**    | None                        |
| **Code Status** | Stable                      |
| **Services**    | None active                 |

---

## 📋 OpenSpec Status

| Item           | Detail                                          |
| :------------- | :---------------------------------------------- |
| **Change**     | `teams-config-yaml-support`  |
| **Phase**      | Propose → Ready for Apply |
| **Proposal**   | ✅ Done     |
| **Specs**      | ✅ Done (2 capabilities: `teams-config-auth`, `teams-channel-policy`) |
| **Design**     | ✅ Done                      |
| **Tasks**      | ✅ Done (22 tasks across 6 groups) |
| **Compliance** | ⬜ Pending |

---

## 🏗️ Execution Phases

```
Phase 0: SETUP (Leader)                                      ✅ DONE
Phase 1: TBD                                                 ⬜ NOT STARTED
Phase 2: TBD                                                 ⬜ NOT STARTED
Phase 3: TBD                                                 ⬜ NOT STARTED
```

**Status legend**: ⬜ Not Started | 🔄 In Progress | ✅ Done | 🟡 Blocked | ❌ Failed

---

## 📋 Action Items

|  #  | Action                                    | Owner   |     Status     |
| :-: | :---------------------------------------- | :------ | :------------: |
|  1  | Verify Teams Config exploration findings  | Reviewer | ⬜ Not Started |

---

## 🔒 File Ownership

> List files that are being actively modified. Other agents MUST NOT modify locked files.

| File       | Owner   |  Status   |
| :--------- | :------ | :-------: |
| agent_share.md | Leader | 🔓 UNLOCKED |

**Rule**: When your work on a file is complete, update this table to 🔓 UNLOCKED.

---

## 📣 Live Status Dashboard

| Agent       | Phase | Role / Mode |   Status   | Current Action             | Project |
| :---------- | :---- | :---------- | :--------: | :------------------------- | :------ |
| **Leader**  | 0     | Lead        | 🔄 ACTIVE  | Booting up, standing by    | hermes-agent |

---

## ⚠️ Ground Rules (All Agents MUST Follow)

1. **Read this file** before starting any work
2. **Read this file again** before updating it (get latest version)
3. **Only edit your own sections** (your status row, your action items, your Shared Notes subsections, the Updates Log)
4. **Do NOT modify locked files** — request unlock in the Updates Log
5. **If you encounter a conflict** — STOP, log it, and wait for human facilitation
6. **Use thinking/verification** before executing: "Do I have all the context I need?"
7. **Append-only** for the Updates Log — never delete or modify other agents' entries
8. **Shared Notes** — Add your subsections with `### [YOUR_ID] : Topic`. Edit only your own. Leader may synthesize notes into other sections.
9. **Operational Constraints (Pointer)**: All agents MUST adhere to the Artifact File Location Strategies and Core Mandates defined in the OpenSpec workflow SKILL and local project specs. Do NOT inject static behavioral rules into this file.

---

## 📝 Shared Notes

> Any agent may add a subsection below. Use format: `### [AGENT_ID] : Topic Title`
> You may edit YOUR OWN subsections. Do NOT edit other agents' subsections.
> For long content, link to external files instead of embedding.
> The Leader may synthesize shared notes into Action Items or Situation updates.

<!-- AGENTS: Add your subsections below this line -->

### [Leader] : Teams Config Exploration Findings
I have completed the exploration for the MS Teams `config.yaml` bug. The findings explain why `config.yaml` is skipped (due to plugin platform enumeration), why `user_id` is UUID instead of email, and the missing channel logic.
**Artifact**: [2026-05-06-teams-config-investigation.md](file:///home/ubuntu/workspaces/oss/hermes-agent/openspec/workspace/explorations/2026-05-06-teams-config-investigation.md)
**Action**: Requesting Reviewer to verify the exploration and confirm if we should proceed to `/opsx-propose`.

### [Reviewer] : Teams Connector Review + Remediation Handoff
I completed an independent review against the current repo, local config, and Teams docs. The main correction is that `platforms.teams.extra` is loaded successfully, but Teams auth still reads env allowlists only. Email allowlists do not work because Teams auth compares against `aad_object_id`, and Teams channel policy keys are not implemented in the adapter.
**Audit Findings**: [/home/ubuntu/workspaces/oss/hermes-agent/openspec/workspace/audits/2026-05-06/teams-connector-review-findings.md](/home/ubuntu/workspaces/oss/hermes-agent/openspec/workspace/audits/2026-05-06/teams-connector-review-findings.md)
**Remediation Exploration**: [/home/ubuntu/workspaces/oss/hermes-agent/openspec/workspace/explorations/2026-05-06-teams-connector-remediation-exploration.md](/home/ubuntu/workspaces/oss/hermes-agent/openspec/workspace/explorations/2026-05-06-teams-connector-remediation-exploration.md)
**Action**: Use the remediation exploration as the implementation handoff. Do not implement directly from the earlier Hermes proposal without correcting the config-path assumption.

### [Coder] : Implementation & Verification Complete
I have completed the `/opsx-apply` tasks for `remove-teams-email-resolution` (which replaced the earlier email-resolution approach) and resolved the Microsoft Teams channel mapping and substring edge cases.
Here is the verification report for the Reviewer:
```
## Verification Report: remove-teams-email-resolution
### Summary
| Dimension    | Status           |
|--------------|------------------|
| Completeness | 9/9 tasks, 2 reqs|
| Correctness  | 2/2 reqs covered |
| Coherence    | Followed         |
| Archive Readiness | Safe        |
```
All tasks, tests, and documentation are updated. The `hermes-gateway` was successfully tested with actual MS Teams webhooks and raw IDs mapping works perfectly.
**Addendum**: Based on user feedback during testing, three operational enhancements were also added:
1. Removed spammy `TeamsAdapter dropping message` warnings for background channel messages.
2. Silenced the `opentelemetry.context` logger to prevent massive Python tracebacks from polluting logs when LLM streaming connections drop.
3. Injected the MS Teams Bot Token into `cache_image_from_url` headers to successfully download image attachments, resolving a `401 Unauthorized` issue.

**Action**: Requesting Reviewer to confirm implementation so we can proceed with `/opsx-archive`.

---

## 💬 Updates Log

> **Format**: `[AGENT_ID] HH:MM: message`
> **Rule**: Append-only. Never edit or delete entries from other agents.

- **[Leader] 10:35**: Shared file created. Project activated. Waiting for tasks.
- **[Leader] 10:55**: Handover Teams config exploration document to Reviewer for verification.
- **[Reviewer] 11:10**: Independent review completed. Findings saved to `openspec/workspace/audits/2026-05-06/teams-connector-review-findings.md`. Remediation handoff saved to `openspec/workspace/explorations/2026-05-06-teams-connector-remediation-exploration.md`.
- **[Leader] 11:32**: `/opsx-propose` completed. Change `teams-config-yaml-support` created with all 4 artifacts (proposal, design, specs, tasks). Commander decisions applied: Option C (email aliases), AAD IDs + emails, Both IDs + names for channels. Ready for `/opsx-apply`.
- **[Coder] 16:15**: Completed `/opsx-apply` for `remove-teams-email-resolution` (simplifying auth by enforcing raw IDs). Implementation verified. Verification report handed over to Reviewer.
- **[Coder] 17:26**: Added operational log cleanup enhancements (removing noisy Teams logs and silencing opentelemetry tracebacks). Verification report updated.
- **[Coder] 18:01**: Fixed 401 Unauthorized attachment download bug by injecting MS Teams bot token. Tasks and report updated.
