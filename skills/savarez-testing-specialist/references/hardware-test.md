# Hardware Component Test Reference

## Purpose

Validate hardware component functionality.

## Inputs

- Hardware test results
- Component list
- Device specs

## Component Categories

| Category | Tests | Priority |
|----------|-------|----------|
| Camera | Preview, capture, video | HIGH |
| Audio | Playback, recording, routing | HIGH |
| Display | Brightness, resolution, touch | HIGH |
| Connectivity | WiFi, Bluetooth, NFC | HIGH |
| Sensors | Accelerometer, gyroscope, proximity | MEDIUM |
| Biometrics | Fingerprint, face unlock | MEDIUM |
| Storage | Read/write speeds | MEDIUM |
| Battery | Charging, drain | LOW |

## Detection Logic

### Camera Test

```bash
grep -i "camera" hardware_results.xml | head -5
```

### Audio Test

```bash
grep -i "audio" hardware_results.xml | head -5
```

### Display Test

```bash
grep -i "display\|screen" hardware_results.xml | head -5
```

### Connectivity Test

```bash
grep -i "wifi\|bluetooth\|nfc" hardware_results.xml | head -5
```

### Sensor Test

```bash
grep -i "sensor\|accel\|gyro" hardware_results.xml | head -5
```

### Biometrics Test

```bash
grep -i "fingerprint\|face" hardware_results.xml | head -5
```

### Storage Test

```bash
grep -i "storage\|read\|write" hardware_results.xml | head -5
```

### Battery Test

```bash
grep -i "battery\|charging" hardware_results.xml | head -5
```

## Output Format

- Total tests
- Pass/Fail counts
- Component coverage
- Failed components list

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Pass rate | 100% | PASS |
| Pass rate | ≥ 95% | WARNING |
| Pass rate | < 95% | FAIL |

## Scoring

| Pass Rate | Score |
|-----------|-------|
| 100% | 100 |
| 95-99% | 80 |
| 90-94% | 60 |
| < 90% | 40 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Missing hardware | Check device specs |
| Driver issues | Check driver status |
| Permission issues | Check test permissions |
