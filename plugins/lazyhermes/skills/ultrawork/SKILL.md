---
name: ultrawork
description: Hermes-native Ultrawork execution discipline for durable, evidence-backed implementation.
---

# LazyHermes Ultrawork

Use this skill when the user invokes `ulw`, `ultrawork`, `/ulw-loop`, or asks
for an implementation to be carried through with strong verification.

1. State the completion promise in concrete user-visible terms.
2. Preserve unrelated user changes and work inside the active repository.
3. Keep a short checklist for multi-step work.
4. Prefer existing Hermes APIs, plugins, skills, and LSP support over new sidecars.
5. Add focused tests for changed behavior.
6. Verify with targeted commands and record the evidence before claiming done.
7. Store durable plan/run artifacts under `plans/` or `.hermes/lazyhermes/` when useful.
