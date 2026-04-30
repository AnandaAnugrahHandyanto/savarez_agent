---
name: yaml-content-packing
description: YAML content pack design for Aeonmarked — data pack structure, item/creature/plant/ability definitions, syntax validation, content registry patterns, data-first content authoring.
---

# YAML content packing for Aeonmarked

All content data lives in YAML files under `data/core/`. Data-first game — if it has stats, it's a YAML file.

## Key Rules
1. IDs are globally unique: `domain:local_name` (e.g., `core:short_sword`)
2. Every entity type has a required schema
3. No circular references
4. Version all packs: `schema_version` field

## Item YAML Template
```yaml
type: weapon
id: core:short_sword
name: "short sword"
glyph: "/"
palette: bronze
damage: "1d6"
damage_type: slashing
range: 1
modes: [melee]
two_handed: false
can_mine: false
description: "A light, single-handed blade."
tags: [weapon, melee, slashing]
```

## Common Mistakes
- Duplicate IDs (last-loaded wins silently)
- Missing required fields (registry throws at load)
- Invalid references (dangling IDs load fine but crash at runtime)
- Wrong indentation (YAML silently nests incorrectly)

## Validation Checklist
- ID follows domain:name format
- All required fields present
- References resolve
- Numerical values in valid ranges
- Glyph is valid single char
- Palette exists in Palette.cs
