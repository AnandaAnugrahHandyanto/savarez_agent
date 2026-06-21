# Security Score Report Reference

## Purpose

Generate comprehensive security score and report.

## Inputs

- All capability results
- Risk assessments
- Compliance status

## Detection Logic

### Aggregate Scores

```bash
TOTAL=0
for CAPABILITY in "${CAPABILITIES[@]}"; do
    TOTAL=$((TOTAL + $CAPABILITY))
done

# Calculate base score
BASE=$((TOTAL / ${#CAPABILITIES[@]}))
```

### Calculate Penalty

```bash
PENALTY=$((CRITICAL_COUNT * 25 + HIGH_COUNT * 10 + MEDIUM_COUNT * 3 + LOW_COUNT * 1))
```

### Calculate Final Score

```bash
FINAL=$((BASE - PENALTY))
if [ "$FINAL" -lt 0 ]; then
    FINAL=0
fi
```

## Output Format

- Base score
- Penalty calculation
- Final score
- Category

## Scoring Formula

### Base Score

```
Base Score = (
    SELinux Score * 0.20 +
    Permission Score * 0.15 +
    Patch Level Score * 0.20 +
    Signing Score * 0.15 +
    Key Management Score * 0.10 +
    Network Score * 0.10 +
    Secure Boot Score * 0.10
)
```

### Penalty

```
Penalty = (
    CRITICAL_count * 25 +
    HIGH_count * 10 +
    MEDIUM_count * 3 +
    LOW_count * 1
)
```

### Final Score

```
Final Score = max(0, Base Score - Penalty)
```

## Categories

| Score | Category |
|-------|----------|
| 90-100 | SECURE |
| 70-89 | GOOD |
| 50-69 | MODERATE |
| 25-49 | WEAK |
| 0-24 | INSECURE |

## Example Calculation

```
Base Score: 85
Findings: 1 CRITICAL, 2 HIGH, 3 MEDIUM

Penalty = (1 * 25) + (2 * 10) + (3 * 3)
        = 25 + 20 + 9
        = 54

Final Score = max(0, 85 - 54) = 31
Category: WEAK
```

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Weighting too aggressive | Adjust weights if needed |
| Penalty too severe | Review penalty values |
| Category thresholds | Adjust based on testing |
