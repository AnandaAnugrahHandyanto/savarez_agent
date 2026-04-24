# Skill Factory Memory Provider

The skill factory is a local-only memory provider that watches successful delegations and writes reusable draft skills when the same workflow repeats enough times.

## What it does

- Records delegated tasks and outcomes
- Counts repeated successful workflow fingerprints
- Writes draft `SKILL.md` files under `$HERMES_HOME/skill_factory/drafts/`
- Keeps all data local to the current Hermes profile

## What it does *not* do

- No external API calls
- No automatic skill installation
- No system prompt injection from the draft files
- No modification of other memory providers

## Setup

1. Run `hermes memory setup`
2. Choose `skill_factory`
3. Adjust the local config values if needed

## Config

Stored in `$HERMES_HOME/skill_factory.json`.

Useful keys:

- `enabled`: turn the provider on or off
- `auto_write`: write drafts automatically once the threshold is reached
- `min_hits`: minimum repeated successes before drafting
- `max_examples`: examples retained per fingerprint
- `draft_dir`: where draft skills are written
- `state_dir`: where counters and metadata are persisted

## Draft promotion

Drafts are intentionally isolated from `~/.hermes/skills/` so they do not load automatically.
When a draft looks good, copy or promote it into the normal skills directory with `skill_manage`.
