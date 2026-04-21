---
sidebar_position: 16
title: "Hermes Mesh Memory Policy"
description: "Operator-facing guidance for where facts should live in Hermes Mesh: built-in memory, external memory, session history, docs, and inventory"
---

# Hermes Mesh Memory Policy

This is the operator-facing version of the Hermes Mesh memory and knowledge-placement policy.

## Goal

Keep one authoritative home per fact.

Hermes works better when memory stays small, docs stay authoritative, and session history stays the recorder of what actually happened.

## Default split

Use this default split when deciding where a fact belongs:

- **Built-in memory (`MEMORY.md` / `USER.md`)** — small, curated facts Hermes should know every session
- **External memory providers (for example Hindsight)** — durable cross-session recall for facts that should be rememberable but not always loaded
- **Session history / session search** — exact chronology, prior discussions, and incident context
- **Docs / skills** — authoritative architecture, policy, procedures, and reusable playbooks
- **Structured inventory/config** — machine-readable operational truth used by automation

## Placement rules

- If Hermes should know it by default every session, put it in built-in memory.
- If Hermes should remember it across sessions but it does not need to be preloaded every time, prefer external memory.
- If the exact conversation, timeline, or reason matters, rely on session history.
- If humans or operators need an authoritative reference, write docs or a skill instead of trusting memory alone.
- If automation depends on it, prefer structured inventory/config over prose.

## Default Hermes Mesh v1 posture

- one external memory provider per instance
- built-in memory stays enabled
- separate banks per machine or role by default
- shared writable external memory only by explicit decision
- docs, inventory, and policy beat memory when they conflict

## What not to do

- Do not let built-in memory turn into a second documentation system.
- Do not store large procedures or architecture notes in built-in memory.
- Do not use cron reports as the long-term source of truth.
- Do not mirror the same fact across memory, docs, and inventory unless there is a clear reason.

## Quick operator test

Before saving something, ask:

1. Does Hermes need this every session?
2. Does exact chronology matter?
3. Is this a human-readable rule or procedure?
4. Does automation need a structured source?

If those questions point to docs, inventory, session history, or external memory, do not stuff it into `MEMORY.md` or `USER.md` just because it is convenient.
