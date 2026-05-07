---
name: role-doc-index-maintenance
description: Rebuild or revise role-docs/index.json from the role files under role-docs/. Use when the user asks to regenerate, refresh, repair, or synchronize the role-doc index.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [role-docs, index, routing, maintenance]
    related_skills: [plan, writing-plans]
---

# Role-Doc Index Maintenance

Use this skill when the user asks to regenerate, refresh, repair, or synchronize the role-doc index used by the role-doc-router plugin.

## Goal

Maintain a single index file at role-docs/index.json that lists every usable role file and a concise description for each one.

The router reads this index instead of scanning every role file on each turn.

## Index schema

The file must be valid JSON with this structure:

```json
{
  "version": 1,
  "count": 2,
  "roles": [
    {
      "path": "cheif.md",
      "title": "厨师长",
      "summary": "一句到两句的角色简介"
    }
  ]
}
```

Rules:

- path is relative to role-docs/
- title is a short human-readable role name
- summary is concise and routing-oriented: what this role is for, what kinds of user requests it should handle, and any important tone or constraints
- count must equal the number of items in roles

## Update behavior

When updating the index:

1. Read role-docs/index.json if it exists.
2. Scan role-docs/ for role files.
3. Ignore index.json itself and non-role files.
4. For each role file that exists:
   - read the file content
   - infer or refresh its title
   - revise its summary based on the current file content
5. If a role exists in files but not in the index, add it.
6. If a role exists in both places, revise only that entry.
7. If an index entry points to a file that no longer exists, delete that entry.
8. Rewrite the full index.json with updated count.

## Working rules

- Do not guess from filenames alone. Read each role file before updating its summary.
- Keep summaries short and discriminative. They are for routing, not full duplication of the role prompt.
- Prefer precise capability descriptions over adjectives.
- Preserve stable relative paths unless the actual file moved.
- Use file tools, not shell cat/grep/sed, unless a shell command is genuinely necessary.

## Recommended execution steps

1. List files under role-docs/.
2. Read existing role-docs/index.json if present.
3. Read each role file under role-docs/ except index.json.
4. Build the updated JSON object.
5. Write role-docs/index.json.
6. Briefly report what was added, revised, and removed.

## Output expectations

When finished, summarize:

- how many roles are now indexed
- which entries were added
- which entries were revised
- which stale entries were removed
