# Extending tanner-stack

<!-- provenance: written from first principles -->

How to add new personas, skills, commands, rules, and workflows to this stack.

---

## Adding a Sub-Agent (formerly Persona)

Sub-agents live at `.claude/agents/*.md`. Each is a markdown file with YAML frontmatter (`name`, `description`, `tools`, `model`, optional `skills`, `color`) that Claude Code reads for native delegation. A mirror reference-doc copy lives at `personas/<name>.md` for historical continuity and extension guidance.

When adding a new one: create `.claude/agents/<name>.md` first (this is the operational form), then mirror the content to `personas/<name>.md` with a reference-doc header pointing back to the sub-agent file. Keep both in sync on major edits; the sub-agent file is authoritative.

The legacy persona template below still describes the body shape; adapt it to the YAML-frontmatter style used by existing sub-agents in `.claude/agents/`.

**Template:**
```markdown
# [Persona Name] — [One-line role description]

<!-- provenance: [source or "original"] -->

## Identity

[2–3 sentences describing this persona's operating posture. What does it care about? What is its failure mode it's designed to prevent?]

## Mode

- **Invocation:** Say "[persona name]" or use the `/[skill]` that activates it.
- **Duration:** Active for the rest of the session unless explicitly dismissed.
- **Default effort:** [high / max / standard]

## Behavior

[Numbered list of specific behaviors. Each should be greppable — specific enough that you could test whether the persona is following it.]

1. [Specific behavior]
2. [Specific behavior]
3. [Specific behavior]

## What This Persona Will NOT Do

[Things this persona refuses, to prevent scope creep or mode confusion.]

- Will not [X]
- Will not [Y]

## Output Format

[If this persona produces structured output, describe the format here.]
```

**Naming:** Use lowercase, hyphenated names. File: `personas/my-persona.md`.

---

## Adding a Skill

Skills live in `skills/{skill-name}/SKILL.md`. Each skill changes the session's operating standard.

**Template:**
```markdown
---
name: skill-name
description: One-line description — used to match invocations
trigger: /skill-name
---

# /skill-name — [Short title]

<!-- provenance: [source or "original"] -->

[What this skill activates. Write it as a direct instruction to the agent — it will be read at invocation time.]

ACTIVATING: [Behavior name]
- [Specific rule 1]
- [Specific rule 2]
- [Specific rule 3]

[If the skill requires a specific output format, describe it here.]
```

**Invocation:** Skills are invoked via `/skill-name`. Claude Code reads the SKILL.md file when the skill is triggered.

**Naming:** Use lowercase, hyphenated names. Directory: `.claude/skills/\1/SKILL.md`.

---

## Adding a Command

Commands live in `.claude/commands/`. Each is a markdown file containing a structured workflow prompt.

**Template:**
```markdown
[COMMAND NAME IN CAPS] for:

$ARGUMENTS

[Brief description of what this command does and why.]

STEP 1 — [STEP NAME]:
[Instructions for step 1. Be specific — include actual commands to run.]

STEP 2 — [STEP NAME]:
[Instructions for step 2.]

[Continue steps as needed.]

REPORT FORMAT:
[How the output should be structured.]

RULES:
- [Non-negotiable constraints on this command's behavior]
```

**Invocation:** Commands are invoked via `/command-name` in Claude Code. File: `.claude/commands/my-command.md`.

**Aliases:** If a command has a short alias, create a separate file that references the primary: `See .claude/commands/primary.md for the full protocol.`

---

## Adding a Rule File

Rules live in `.claude/rules/`. Each file governs a specific subsystem or path scope.

**Template:** See `.claude/rules/example-rule.md` for the full pattern.

**Key elements every rule file needs:**
1. `## paths` — which directory/file paths this rule applies to
2. `## DO NOT` — specific prohibitions (greppable, testable)
3. `## Architecture Notes` — entry points, source of truth, data flow
4. `## Key Files` — the 3–5 files that matter most for this subsystem

**Loading:** Claude Code loads rule files when the agent touches matching paths. Keep rules focused — a rule file that governs everything is read for nothing.

---

## Adding a Workflow

Workflows live in `workflows/`. Each is a template for a multi-step process.

Use workflows for:
- Structured templates that get filled in per-use (e.g., audit reports, post-mortems)
- Complex processes with branching that don't fit neatly into a single command

**Naming:** Descriptive, hyphenated. File: `workflows/my-workflow-template.md`.

---

## Provenance Headers

Every file added to this stack should include a provenance comment near the top:

```markdown
<!-- provenance: [source description] -->
```

Examples:
- `<!-- provenance: genericized from MyProject/path/to/file.md -->`
- `<!-- provenance: written from first principles; pattern from MyProject practice -->`
- `<!-- provenance: original -->`

This lets future sessions understand what's been adapted vs. what's new, without requiring git history.

---

## Quality Checklist for New Files

Before committing a new persona, skill, command, rule, or workflow:

- [ ] Provenance header present
- [ ] No hardcoded project-specific values (use `{placeholder}` for operator-fill slots)
- [ ] Behavior is specific enough to be testable (not "be careful" but "never do X")
- [ ] File is self-contained — a future session can read it cold and know exactly what to do
- [ ] Named following the lowercase-hyphenated convention
- [ ] Added to the appropriate directory with the correct file name
