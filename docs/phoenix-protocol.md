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

## Real-World Examples

### Example 1: The Silent Breaking Change

A user reports: *"My Discord bot stopped responding after the latest update."*

After debugging, the root cause is a library update that changed how slash commands register — `guild=` instead of `guild_id=`. The fix is applied.

**Phoenix activates:**

1. *"This is a non-obvious error with a clear root cause — others will hit it too"*
2. Search Memory → no existing entry about Discord slash command registration errors
3. Search Skills → no relevant skill found
4. Create new Skill: `discord-slash-command-registration` documenting the library version, behavior change, and fix
5. Also update Memory with the specific error pattern so it's searchable next time
6. Done. Anyone else hitting this gets diagnosed in seconds instead of hours.

### Example 2: The Quirk That Keeps Reappearing

A model starts returning HTTP 500 errors intermittently. After investigation, it's a known server-side bug on the provider's end. The agent works around it by implementing a retry chain.

**Phoenix activates:**

1. *"This is a model/provider quirk that affects behavior — belongs in Memory"*
2. Search Memory → find existing entry about this provider
3. Update it: note the specific error pattern, the retry strategy, and the fallback model
4. Done. Next time the error happens, the agent already knows the workaround.

### Example 3: The Workflow Worth Sharing

A user asks how to set up WhatsApp bridging. The agent figures out the complete workflow — environment variables, configuration steps, testing approach.

**Phoenix activates:**

1. *"This is a useful workflow that took significant effort to discover — belongs in Skill"*
2. Search Skills → no existing WhatsApp bridging guide
3. Create new Skill: `whatsapp-bridge-setup` with the complete step-by-step procedure
4. Done. Future users get a ready-made guide instead of building from scratch.

## Summary

| | |
|---|---|
| **What** | Self-improvement loop after significant changes |
| **When** | After updates that change behavior, tools, or config |
| **How** | Determine category → Search → Update or create |
| **Where** | Memory / Skill / SOUL |
| **Who runs it** | The agent (guided by Corrections feedback) |

Phoenix ensures that every lesson learned — every fix, every discovery, every new capability — gets preserved. Not in a wiki nobody reads, but in the agent's own memory where it actually matters.
