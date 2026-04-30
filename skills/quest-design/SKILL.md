---
name: quest-design
description: Quest/narrative design for emergent roguelikes — procedural story hooks, faction-based quests, dialogue tree patterns, reward scaling, quest chain structure, sandbox-friendly non-linear narrative.
---

# Quest design for Aeonmarked

Aeonmarked uses a dialogue and quest scaffold that supports sandbox-friendly, non-linear narrative. Quests emerge from faction interactions, world state, and player choices — not scripted sequences.

## Core Philosophy
1. **Quests emerge from world state.** Faction relations, NPC dispositions, and player reputation drive available quests organically.
2. **Non-linear by default.** Players can complete, fail, ignore, or chain quests in any order.
3. **Rewards scale with difficulty and player investment.** Loot, reputation, and progression rewards adjust based on quest complexity.
4. **Dialogue trees are data-driven.** Dialogue lives in YAML, not code.

## Quest YAML Structure

### Basic Quest Definition
```yaml
type: quest
id: core:goblin_problem
faction: goblins
title: "The Goblin Situation"
description: "The local goblins have been causing trouble. Deal with them."
objectives:
  - id: kill_goblins
    type: kill
    target: core:goblin
    count: 5
    description: "Kill 5 goblins in the area"
  - id: return_to_faction
    type: speak
    npc: core:guard_captain
    description: "Report back to the guard captain"
rewards:
  gold: "2d10+10"
  reputation:
    guard_faction: 15
  items:
    - id: core:copper_ring
      guaranteed: true
min_level: 3
prerequisites:
  quests: []
  reputation:
    guard_faction: 0
```

### Quest Types
| Type | Description | Example |
|------|-------------|---------|
| `kill` | Eliminate N targets | Kill 5 goblins |
| `retrieve` | Fetch an item from location | Find the ancient relic |
| `escort` | Safely guide NPC to destination | Escort merchant to outpost |
| `speak` | Talk to NPC with condition | Report back to captain |
| `discover` | Visit/interact with location | Explore the abandoned mine |
| `craft` | Create item using recipe | Craft a healing potion |

## Dialogue Tree Patterns

### Dialogue YAML
```yaml
type: dialogue
id: core:guard_captain
npc: core:guard_captain
greetings:
  - condition: "player.reputation < -20"
    text: "I should have known you'd show up here."
    options:
      - text: "I'm here to help."
        responses:
          - text: "Prove it."
            triggers_quest: core:goblin_problem
      - text: "Leave me alone."
        responses:
          - text: "Fine, get out of my sight."
  - condition: "player.reputation >= 20"
    text: "Welcome back, hero. We need your help again."
    options:
      - text: "What's the situation?"
        responses:
          - text: "The goblins have doubled in number..."
            triggers_quest: core:goblin_invasion
```

### Dialogue Rules
1. **Condition evaluation is deterministic.** Use only world state, not RNG.
2. **Branch depth ≤ 4.** Deep dialogues become navigation hell.
3. **Every branch has consequences.** Reputation changes, quest triggers, or world state updates.
4. **NPCs remember.** Dialogue choices persist across sessions; NPCs reference past interactions.

## Faction-Based Quest Design

### Faction Relationship System
Factions have relationships with each other and the player:
- **Alignment:** hostile, neutral, friendly, allied
- **Dynamic shifts:** Player actions and world events shift alignment
- **Cross-faction quests:** Completing one faction's quest may affect other factions

### Quest Generation from Factions
Each faction generates quest hooks based on:
1. **Current state:** At war with faction X needs military quests
2. **Player reputation:** High reputation unlocks advanced quests
3. **World events:** Goblin migration creates emergent quest opportunities
4. **Quest chains:** Completed quests unlock follow-ups naturally

## Reward Scaling

### Reward Formula
```
base_gold = difficulty_rating * 5d4 + player_level * 2
reputation_gain = difficulty_rating * 3 + faction_alignment_bonus
item_drop_chance = min(0.8, difficulty_rating / 10 + player_reputation / 100)
```

### Reward Types
- **Gold** — dice-based (always randomized)
- **Reputation** — faction-specific alignment changes
- **Items** — guaranteed or chance-based from faction's item pool
- **Unlock** — new areas, quests, NPCs, or abilities

## Quest Chain Structure

### Linear Progression
```
Quest A → Quest B → Quest C (reputation unlock)
```

### Branching Progression
```
           /→ Quest C (Faction A path)
Quest A →
           \\→ Quest D (Faction B path)
```

### Emergent Chaining
Quests chain based on world state, not hardcoded links:
- Killing goblin chief triggers "power vacuum" quest
- Saving merchant spawns "merchant's gratitude" quest
- Exploring cave reveals hidden faction → new quest line

## Sandbox-Friendly Design Patterns

### Never Block Progression
- Players can ignore any quest forever without penalty
- No "fail state" permanently locks content
- Abandoned quests re-generate after world state changes

### Context-Aware Generation
- Quests reference current world state (locations, NPCs, items that actually exist)
- NPC dialogue adapts to player's inventory, reputation, and quest history
- Reward pools reflect faction's actual resources

### Testing Quest Design
- **Playtest all branches** — every dialogue path must lead somewhere
- **Verify reward scaling** — low-level quests shouldn't give high-level loot
- **Test faction conflict** — completing one quest shouldn't break another
- **Check determinism** — same inputs produce same quest outcomes

## Checklist
- [ ] Quest has YAML definition with all required fields
- [ ] Objectives use valid types and references
- [ ] Dialogue branches all terminate (no dead ends)
- [ ] Reward scaling is appropriate for difficulty
- [ ] Faction reputation effects are defined
- [ ] Prerequisites don't create impossible loops
- [ ] Quest is sandbox-friendly (ignorable, no permanent locks)
