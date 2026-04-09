# The Phoenix Protocol: Proactive Self-Improvement Loop

## What Is It?

The Phoenix Protocol is a standing behavioral directive that ensures the agent continuously learns and updates its own knowledge base after every significant change to its configuration, behavior, or tooling.

Instead of knowledge becoming stale after an update or fix, Phoenix guarantees that relevant Memory, Skills, and SOUL entries are reviewed and updated — keeping the agent's self-awareness current at all times.

## Why Does It Exist?

Over time, three problems compound:

1. **Stale Memory** — New configurations, tool changes, or environment facts get discovered but never saved to Memory
2. **Lost Procedures** — Useful workflows get figured out once, then forgotten after the next update
3. **Forgotten Lessons** — Errors get fixed in one session but the same mistake repeats in future sessions because no one recorded the fix

Phoenix is the self-healing loop that prevents these problems. Every time a significant change happens, the agent asks: *"Do I know this already? Should I remember this?"*

## When Does It Fire?

Phoenix activates after **significant** updates or fixes — specifically those that:

- Change existing behavior
- Introduce new tools or capabilities
- Affect persistent configuration
- Fix a recurring error or establish a new pattern

Routine actions (gateway restarts, one-off config patches, simple queries) do not trigger Phoenix — the search step naturally filters noise.

## How It Works: The Decision Tree

After every significant change, follow this sequence:

### Step 1 — Determine the Category

Ask: *"Where does this knowledge belong?"*

| Category | What it stores | Examples |
|---|---|---|
| **Memory** | Durable facts about environment, user preferences, tool quirks | API key locations, platform IDs, model behavior quirks, cron schedules |
| **Skill** | Reusable procedures for recurring task types | Debugging workflows, setup guides, deployment steps |
| **SOUL** | Identity, purpose, values — rare, use sparingly | Behavioral directives, personality rules, platform routing |
| **AGENTS.md** | Upstream developer docs — **do not edit** | — |

### Step 2 — Search the Relevant Category

Use the appropriate search:

- **Memory** → `session_search` (keyword search across past sessions)
- **Skill** → `skills_list` / `skill_view` (browse or read specific skill)
- **SOUL** → Read `~/.hermes/SOUL.md` directly

### Step 3 — Update or Create

- **Found an existing entry?** → Update it with the new information
- **Nothing relevant found?** → Create a new entry in the correct category

For SOUL specifically, use `patch` to edit `~/.hermes/SOUL.md` directly.

## Implementation

Phoenix lives in three places:

1. **SOUL.md** — The canonical behavioral directive, loaded into context on every session
2. **Corrections Loop** — If Phoenix is skipped, the user corrects the agent and it retroactively executes the search → update cycle
3. **Post-Update Hook** — `~/.hermes/hooks/post-update/04-phoenix-protocol.sh` fires after every `hermes update`, reminding to check Memory/Skill for significant changes

## Example

**Scenario:** After a routine `hermes update`, the agent discovers that platform slash commands have changed registration behavior due to a library update.

**Phoenix response:**

1. *"This changed how Discord commands work — relevant to Memory and possibly Skill"*
2. Search Memory → find any existing entry about slash command registration
3. Update it: note the library version, the behavior change, and the fix
4. Search Skills → check if a relevant skill exists
5. If not, create one: `discord-slash-command-registration` with the root cause and fix
6. Done. Future sessions won't hit the same issue blind.

**Scenario:** A user reports the agent isn't responding in a specific channel. After debugging, the root cause is a misconfigured channel routing rule.

**Phoenix response:**

1. *"This is a non-obvious configuration pattern — relevant to Memory"*
2. Search Memory → find existing channel routing entries
3. Update with the new misconfiguration pattern and resolution
4. Done. If it happens again, the agent knows immediately.

## Summary

| | |
|---|---|
| **What** | Self-improvement loop after significant changes |
| **When** | After updates that change behavior, tools, or config |
| **How** | Determine category → Search → Update or create |
| **Where** | Memory / Skill / SOUL |
| **Who runs it** | The agent (guided by Corrections feedback) |

Phoenix ensures that every lesson learned — every fix, every discovery, every new capability — gets preserved. Not in a wiki nobody reads, but in the agent's own memory where it actually matters.
