# Build Readiness Score Reference

## Overview

Build Readiness Score provides a quantified measure of ROM build readiness.
Score ranges from 0-100, with hard-fail logic for critical failures.

---

## Scoring Components

| Component | Weight | Max Points | Category |
|-----------|--------|------------|----------|
| Kernel Ecosystem | 16% | 16 | CRITICAL |
| VINTF | 15% | 15 | CRITICAL |
| Vendor Tree | 15% | 15 | CRITICAL |
| Device Tree | 15% | 15 | MEDIUM |
| Board Config | 14% | 14 | MEDIUM |
| Boot & Recovery | 12% | 12 | MEDIUM |
| SELinux | 8% | 8 | MEDIUM |
| API-Level | 5% | 5 | LOWER |
| **Total** | **100%** | **100** | |

---

## Hard-Fail Logic

### Conditions

| Condition | Max Score | Category |
|-----------|-----------|----------|
| 1 critical failure | 49 | BRING-UP |
| 2 critical failures | 25 | BRING-UP |
| 3 critical failures | 10 | NOT READY |

### Critical Components

- Kernel Ecosystem (score = 0)
- VINTF (score = 0)
- Vendor Tree (score = 0)

### Implementation

```bash
FAIL_COUNT=0
[ "$KRN_SCORE" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))
[ "$VINTF_SCORE" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))
[ "$VT_SCORE" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))

if [ "$FAIL_COUNT" -ge 3 ]; then
    MAX_SCORE=10
elif [ "$FAIL_COUNT" -ge 2 ]; then
    MAX_SCORE=25
elif [ "$FAIL_COUNT" -ge 1 ]; then
    MAX_SCORE=49
else
    MAX_SCORE=$RAW_SCORE
fi
```

---

## Category Thresholds

| Range | Category | Description |
|-------|----------|-------------|
| 90-100 | RELEASE READY | Production quality |
| 70-89 | STABLE | Daily driver quality |
| 50-69 | BETA | Testing phase |
| 30-49 | BRING-UP | Initial development |
| 0-29 | NOT READY | Critical issues |

---

## Scoring Algorithm

### Step 1: Calculate Component Scores

Each component calculates its own score based on checks.

### Step 2: Sum Components

```bash
TOTAL=$((KRN_SCORE + VINTF_SCORE + VT_SCORE + DT_SCORE + BC_SCORE + BOOT_SCORE + SE_SCORE + API_SCORE))
```

### Step 3: Apply Hard-Fail

```bash
if [ "$FAIL_COUNT" -ge 1 ]; then
    # Apply cap
    TOTAL=$((TOTAL > MAX_SCORE ? MAX_SCORE : TOTAL))
fi
```

### Step 4: Assign Category

```bash
if [ "$TOTAL" -ge 90 ]; then
    CATEGORY="RELEASE READY"
elif [ "$TOTAL" -ge 70 ]; then
    CATEGORY="STABLE"
# ... etc
fi
```

---

## Example Calculations

### Example 1: Release Ready

```
Kernel Ecosystem:  16/16
VINTF:             15/15
Vendor Tree:       15/15
Device Tree:       15/15
Board Config:      14/14
Boot & Recovery:   12/12
SELinux:            8/8
API-Level:          5/5

TOTAL:            100/100
Category: RELEASE READY
```

### Example 2: Hard-Fail (1 failure)

```
Kernel Ecosystem:   0/16  ← CRITICAL FAILURE
VINTF:             15/15
Vendor Tree:       15/15
Device Tree:       15/15
Board Config:      14/14
Boot & Recovery:   12/12
SELinux:            8/8
API-Level:          5/5

RAW TOTAL:         84/100
FAIL COUNT:        1
MAX SCORE:         49
FINAL:             49/100
Category: BRING-UP
```

### Example 3: Hard-Fail (2 failures)

```
Kernel Ecosystem:   0/16  ← CRITICAL FAILURE
VINTF:              0/15  ← CRITICAL FAILURE
Vendor Tree:       15/15
Device Tree:       15/15
Board Config:      14/14
Boot & Recovery:   12/12
SELinux:            8/8
API-Level:          5/5

RAW TOTAL:         69/100
FAIL COUNT:        2
MAX SCORE:         25
FINAL:             25/100
Category: BRING-UP
```
