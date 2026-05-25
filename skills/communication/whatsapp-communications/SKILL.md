---
name: whatsapp-communications
description: Draft bounded WhatsApp outreach decisions.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: communication
    tags:
      - whatsapp
      - outreach
      - communications
---

# WhatsApp Communications Skill

Use this skill to decide one bounded WhatsApp outreach step for one already-resolved target. Do not resolve targets, widen scope, or call any bridge directly.

## When to Use

- A workflow already resolved one exact WhatsApp target.
- Preserved history is available.
- The workflow needs one bounded decision: send, no-send, or handoff.

## Prerequisites

- The workflow must supply the canonical `WhatsAppCommunicationDraftRequest` JSON.
- The target is already resolved.
- Any real send stays outside this skill.

## How to Run

Read the provided request.
Return one JSON object only.

## Quick Reference

- Allowed `draft_outcome`: `send_message`, `no_send_required`, `handoff_required`
- Include `outbound_message_text` only for `send_message`
- Include `handoff_reason` only for `handoff_required`
- Keep the decision bounded to the exact target and supplied objective

## Procedure

1. Read `communication_stage`, `operator_objective`, `resolved_target`, and `history_rows`.
2. Decide whether Hermes should send now, not send now, or hand off.
3. If sending, draft one concise WhatsApp message grounded in the history.
4. If not sending, return `no_send_required` with no extra text fields.
5. If handoff is needed, return `handoff_required` and a short `handoff_reason`.

## Pitfalls

- Do not invent new targets.
- Do not ask the workflow to call tools.
- Do not return prose outside the JSON object.
- Do not include `outbound_message_text` for non-send outcomes.
- Do not include `handoff_reason` unless handoff is required.

## Verification

The output must be valid JSON with exactly the bounded fields the workflow expects.
