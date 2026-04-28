# Hermes Auto-Update PR

## Summary

- **Feature**: Auto-update system for Hermes Gateway with fork-safe detection
- **Modes**: `notify` (notify on updates) and `apply` (auto-apply after grace period)
- **Safety**: Skips auto-apply for forks, validates home channel before notifications

## Changes

### New Files

| File | Description |
|------|-------------|
| `hermes_cli/auto_update.py` | `AutoUpdater` class with `parse_check_interval()` helper |
| `tests/hermes_cli/test_auto_update.py` | Unit tests for AutoUpdater |

### Modified Files

| File | Changes |
|------|---------|
| `hermes_cli/banner.py` | Added `check_for_updates_uncached()` - bypasses cache for real-time checks |
| `hermes_cli/config.py` | Added `auto_update` section to `DEFAULT_CONFIG` |
| `gateway/run.py` | Added home channel tracking and `_check_post_update_notification()` async loop |

### Internal Files (runtime)

- `~/.hermes/.update_manifest.json` - Created before execv, deleted after notification
- `~/.hermes/.home_channel.json` - Persisted home channel for notifications

## Configuration

```yaml
auto_update:
  enabled: false
  mode: notify            # notify | apply
  check_interval: 24h    # 1h, 6h, 12h, 24h, 48h, 72h
  grace_period_seconds: 300  # only for mode=apply
```

## Safety

1. **Fork Detection**: Uses `is_fork()` from `hermes_cli/main.py` - skips auto-apply for forks
2. **Home Channel Validation**: First valid user message (non-empty text) captures target
3. **Manifest Lifecycle**: 5-minute timestamp window prevents stale notifications

## Test Plan

- [x] `test_check_for_updates_uncached_bypasses_cache` - verifies cache bypass
- [x] `test_parse_check_interval_shortcuts` - verifies interval parsing
- [x] `test_auto_updater_init` - verifies config initialization
- [x] `test_auto_updater_should_apply_skips_when_disabled` - verifies disabled check
- [x] `test_auto_updater_should_apply_skips_notify_mode` - verifies notify mode skip
- [x] `test_home_channel_persistence` - verifies home channel save/load
- [x] `test_is_fork_detection` - verifies fork detection