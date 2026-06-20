# Release Readiness Reference

## Purpose

Verify kernel release readiness.

## Checks

| Check | Description |
|-------|-------------|
| CHANGELOG | Changelog present |
| VERSION | Version defined |
| README | Documentation present |

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| CHANGELOG | +1 | 0 |
| VERSION | +1 | 0 |
| README | +1 | 0 |
| **Total** | **3** | |

## Common Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| No CHANGELOG | No history | Create CHANGELOG |
| No VERSION | No versioning | Add VERSION |
| No README | No docs | Create README |

## Example Output

```
=== Release Readiness ===

[✓] CHANGELOG.md
[✓] VERSION
[✓] README.md

Release Readiness: 3/3
```
