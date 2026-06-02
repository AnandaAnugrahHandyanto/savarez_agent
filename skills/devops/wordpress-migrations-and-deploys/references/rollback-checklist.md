# WordPress Rollback Checklist

Use this checklist before any risky WordPress release or migration.

## Before Deploy

- Record the code version being deployed.
- Record the current live code version.
- Confirm where the latest database backup lives.
- Confirm where uploads/media backup or sync checkpoint lives.
- Confirm who can trigger rollback.
- Confirm whether the release mutates data, schema, URLs, or cache behavior.

## Rollback Inputs

Have these ready:
- last known-good code revision/tag
- restore command or host control panel path
- database backup filename and timestamp
- uploads sync/restore plan if media changed
- cache flush steps after restore

## Trigger Conditions

Rollback is usually preferred when:
- admin is inaccessible
- checkout/orders/payments are broken
- media or assets fail widely
- fatal errors persist after a fast, low-risk forward fix attempt
- a data mutation behaves incorrectly and recovery is time-sensitive

## After Rollback

- Restore code.
- Restore database if needed.
- Restore uploads if needed.
- Flush relevant caches.
- Verify homepage, admin, one key content path, and one business-critical flow.
- Document what failed before reattempting deployment.
