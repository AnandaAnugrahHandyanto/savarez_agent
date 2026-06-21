# Risk Assessment Reference

## Purpose

Assess risk of proposed patches.

## Inputs

- Proposed changes
- Affected files
- Change scope

## Detection Logic

### File Criticality

```bash
git log --oneline -5 -- <file>
```

### Change Size

```bash
git diff --stat <patch>
```

### Component Analysis

```bash
# Check component history
git log --oneline -10 -- <component>/
```

## Output Format

- Risk level (LOW/MEDIUM/HIGH/CRITICAL)
- Affected components
- Potential side effects
- Testing requirements

## Risk Matrix

| Factor | LOW | MEDIUM | HIGH | CRITICAL |
|--------|-----|--------|------|----------|
| File count | 1-2 | 3-5 | 6-10 | 10+ |
| Component | Peripheral | Core | Critical | System |
| Testing | Unit | Integration | System | Full |

## Risk Level Definitions

| Level | Criteria | Approval |
|-------|----------|----------|
| LOW | 1-2 files, peripheral | Auto-approve |
| MEDIUM | 3-5 files, core | Review required |
| HIGH | 6-10 files, critical | Approval required |
| CRITICAL | 10+ files, system | Full review |

## Risk Factors

| Factor | Weight |
|--------|--------|
| File count | 25% |
| Component criticality | 25% |
| Change scope | 25% |
| Testing coverage | 25% |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Underestimated risk | Check all factors |
| Missing dependencies | Check imports |
| Side effects | Check consumers |
