# SELinux Denial Analysis Reference

## Purpose

Analyze SELinux avc denials for policy issues.

## Inputs

- dmesg with avc denials
- audit.log
- sepolicy files

## Detection Logic

### Count Denials

```bash
dmesg 2>/dev/null | grep -c "avc:.*denied"
```

### Denial Patterns

```bash
dmesg 2>/dev/null | grep "avc:.*denied" | awk '{print $NF}' | sort | uniq -c | sort -rn | head -10
```

### Source Contexts

```bash
dmesg 2>/dev/null | grep "avc:.*denied" | grep -o "scontext=[^ ]*" | sort | uniq -c | sort -rn | head -10
```

### Target Contexts

```bash
dmesg 2>/dev/null | grep "avc:.*denied" | grep -o "tcontext=[^ ]*" | sort | uniq -c | sort -rn | head -10
```

## Output Format

- Denial count
- Top denial patterns
- Source/target contexts
- Policy fix recommendations

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Clear denial pattern with context |
| PROBABLE | Pattern identified, context partial |
| POSSIBLE | Multiple denial types |
| UNKNOWN | Insufficient denial data |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Expected denials | Filter by context |
| Transient denials | Check pattern |
| Permissive mode | Report mode |
