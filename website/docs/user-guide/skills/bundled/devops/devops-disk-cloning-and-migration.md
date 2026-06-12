---
title: "Disk Cloning And Migration"
sidebar_label: "Disk Cloning And Migration"
description: "Safely prepare and run SSD/HDD disk cloning or system migration on Linux, with source/target identification, health checks, ddrescue safeguards, and post-clo..."
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Disk Cloning And Migration

Safely prepare and run SSD/HDD disk cloning or system migration on Linux, with source/target identification, health checks, ddrescue safeguards, and post-clone expansion.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/devops/disk-cloning-and-migration` |
| Version | `1.0.0` |
| Author | Mizuki |
| License | MIT |
| Tags | `linux`, `disk-cloning`, `migration`, `ddrescue`, `storage`, `backup` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Disk Cloning and Migration

Use this skill when the user wants to clone an SSD/HDD, migrate a Linux system disk, prepare a target drive, verify drive health before cloning, create a guarded clone workflow, or verify/restore a system backup after an OS format/reinstall.

## Core safety rule

Disk cloning is destructive to the target. Never start a clone until all of these are true:

1. Source disk and target disk are identified by model, serial, size, and mountpoints.
2. The target is explicitly confirmed by the user.
3. The target is not mounted.
4. The target is at least as large as the source.
5. The command uses whole disks, not partitions, unless the user explicitly wants partition-only cloning.
6. The user understands the target will be erased.

Good whole-disk example:

```bash
sudo ddrescue -f -n /dev/sda /dev/sdb rescue.log
```

Bad accidental partition example for full system clone:

```bash
sudo ddrescue -f -n /dev/sda2 /dev/sdb2 rescue.log
```

## Preferred workflow

### 1. Inventory disks

Always inspect real block devices first:

```bash
lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,TRAN
ls -l /dev/disk/by-id/ | grep -E 'ata-|usb-|nvme-' || true
findmnt -no SOURCE,FSTYPE,SIZE,USED,AVAIL /
```

Look for:

- current root disk
- removable target disk
- target auto-mounted partitions
- disk sizes
- serial/model identifiers

### 2. Check target health when possible

For SATA/NVMe direct devices:

```bash
sudo smartctl -a /dev/sdX
```

For many USB-SATA bridges, try SAT mode if direct mode fails:

```bash
sudo smartctl -d sat -a /dev/sdX
```

Do not trust a failing or suspicious target for an important clone.

### 3. Install tools if missing

On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y gddrescue pv partclone smartmontools gdisk cloud-guest-utils
```

Use the `sudo-from-secrets-file` skill when local sudo credentials are available. If the secrets file has non-shell-safe lines, parse only `SUDO_PASSWORD`; do not source the whole file.

### 4. Prefer live USB for system disk cloning

Best practice is cloning from a live USB so the source root filesystem is not changing while copied. Cloning a running root disk can work, but it may produce an inconsistent clone if files change during the run.

Tell the user plainly:

> Best clone quality: boot a live Ubuntu USB, then clone. Running-system clone is more convenient but less clean.

### 5. Unmount target partitions

If the target auto-mounted:

```bash
sudo umount /dev/sdX1
sudo umount /dev/sdX2
```

Never unmount the source root partition while running from it.

### 6. Clone with ddrescue in two passes

Use a log file so interrupted clones can resume:

```bash
sudo ddrescue -f -n /dev/SOURCE /dev/TARGET clone.log
sudo ddrescue -f -d -r3 /dev/SOURCE /dev/TARGET clone.log
sync
sudo partprobe /dev/TARGET || true
```

Meaning:

- `-f`: allow writing directly to a block device
- `-n`: first pass, copy good areas without retrying bad sectors
- `-d`: direct disk access for retry pass
- `-r3`: retry bad areas three times
- `clone.log`: persistent rescue map/log

### 7. Verify target layout

After cloning:

```bash
lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,TRAN /dev/TARGET
sudo sgdisk -v /dev/TARGET || true
```

If the target disk is bigger, expansion can be done later after boot or after inspection:

```bash
sudo growpart /dev/sdX 2
sudo resize2fs /dev/sdX2
```

Only run expansion after verifying partition numbering and filesystem type.

## Guarded helper script pattern

For user PCs, create a helper that refuses unsafe execution:

- requires `sudo`
- requires exactly `/dev/SOURCE /dev/TARGET`
- checks both are block devices
- checks target is larger/equal
- refuses mounted targets
- prints source and target layouts
- requires typing an exact confirmation phrase like `CLONE /dev/sda TO /dev/sdb`
- uses `ddrescue` two-pass workflow

Prefer stable `/dev/disk/by-id/...` paths for final launchers once the source and target are identified. `/dev/sdX` names can change after replug/reboot, while by-id paths include model/serial and reduce wrong-disk risk.

See `references/guarded-ddrescue-clone-toolkit.md` for a compact toolkit pattern.
See `references/hermes-agent-block-device-clone-handoff.md` for the Hermes-safe handoff pattern when raw block-device writes are blocked by the agent runtime: prepare, verify, stop avoidable writers, unmount the target, create a locked by-id launcher, and have the user run the final destructive command locally.
See `references/s3-home-backup-restore-verification.md` for a non-destructive S3 backup/restore audit pattern after an OS format: enumerate buckets, read restore manifests, compare S3 prefixes to local folders with `aws s3 sync --dryrun`, and avoid overwriting live `~/.hermes`.

## Pitfalls

- USB HDDs often auto-mount; mounted targets must be unmounted first.
- Device names can change after reboot/replug. Re-identify disks every time using model/serial/size, then prefer stable `/dev/disk/by-id/...` paths in any final launcher or handoff command.
- Host may have unrelated listeners or disks; do not infer from `/dev/sdb` alone.
- Do not clone to a disk with important files unless the user explicitly accepts erasing it.
- Do not start destructive clone commands during preparation. Prepare tools/scripts/checklists first, then wait for explicit target confirmation.
- If the agent runtime blocks raw block-device writes, do not stop at a refusal. Finish all safe prep: stop avoidable writers, unmount target partitions, verify target state, create a guarded by-id launcher, and give the exact local command plus confirmation phrase.
- A target disk can show `SMART PASSED` while still having concerning history such as ATA errors, command timeouts, reallocated sectors, or prior temperature failures. Report that nuance: acceptable for emergency/temporary recovery if needed, not a trusted long-term replacement.
- Avoid `dd` for first choice. `ddrescue` is safer because it resumes and handles bad sectors better.

## Good final output

Before cloning: report source candidate, target candidate, size check, mount status, tool readiness, and exact next command.

After cloning: report ddrescue completion, log path, target layout, and next boot/expansion steps.
