# Rollback Planning Reference

## Purpose

Create rollback strategy for patches.

## Inputs

- Proposed patches
- Risk assessment
- Deployment plan

## Detection Logic

### Check Git History

```bash
git log --oneline -10
```

### Check Tags

```bash
git tag -l "backup/*"
```

### Check Branch State

```bash
git status --short
```

## Output Format

- Rollback trigger conditions
- Rollback procedure
- Backup verification
- Recovery steps

## Rollback Requirement

| Risk Level | Rollback Plan Required |
|------------|------------------------|
| LOW | Optional |
| MEDIUM | Recommended |
| HIGH | **Required** |
| CRITICAL | **Required** |

## Rollback Triggers

| Trigger | Criteria |
|---------|----------|
| Boot failure | System does not boot |
| System crash | Repeated crashes |
| Performance | Significant degradation |
| Feature loss | Core feature broken |

## Rollback Procedure

```
1. Identify backup point
   git log --oneline -10
   git tag -l "backup/*"

2. Verify backup integrity
   git show <backup-tag>

3. Execute rollback
   git revert <commit>
   # OR
   git reset --hard <backup-tag>

4. Verify system stability
   - Boot test
   - Functionality test
   - Performance test
```

## Example Rollback Plan

```
Rollback Triggers:
- Boot failure after patch
- System crash loop
- Performance degradation

Rollback Procedure:
1. Boot to recovery
2. Restore from backup
3. Verify system stability

Backup:
- Pre-patch tag: backup/pre-fix-20260621
- Verified: Yes
```

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Incomplete backup | Verify backup exists |
| Partial rollback | Check all changes |
| Data loss | Backup user data |
