# S3 home-backup restore verification pattern

Use when the user formatted/reinstalled a Linux PC and says important files were backed up to S3, or after they say they restored the backup and ask what is still missing.

## Goal

Distinguish three states clearly:

1. **Backup exists in S3** — bucket/prefix has objects, manifest, restore notes, sane privacy/encryption/versioning.
2. **Local restore is complete** — S3 source and local destination match for the intended folders.
3. **Runtime environment is usable** — tools like Node/Docker/AWS profiles are installed/configured after OS reinstall.

Do not conflate these. A project folder can be restored while its toolchain is still missing.

## Discovery commands

Confirm profile/account and buckets without printing secrets:

```bash
aws configure list-profiles
for p in $(aws configure list-profiles); do
  aws sts get-caller-identity --profile "$p" --output json
 done
aws s3api list-buckets --query 'Buckets[].Name' --output text
```

For a candidate backup bucket:

```bash
bucket=hevar-pc-backup-ACCOUNT-DATE
aws s3api get-bucket-location --bucket "$bucket"
aws s3api get-bucket-versioning --bucket "$bucket"
aws s3api get-bucket-encryption --bucket "$bucket"
aws s3api get-public-access-block --bucket "$bucket"
aws s3 ls "s3://$bucket/" --recursive --summarize --human-readable | tail -n 50
```

If the backup has restore helper files, read only operational text, not secrets:

```bash
prefix='host/home-user/timestamp'
aws s3 cp "s3://$bucket/$prefix/RESTORE-FROM-S3.txt" -
aws s3 cp "s3://$bucket/$prefix/backup-manifest.txt" - | sed -n '1,160p'
```

## Non-destructive local restore comparison

Use `aws s3 sync --dryrun` from each S3 backup folder to the expected local destination. This reports what would still download without changing the machine.

Example mapping for a home backup:

```bash
checks=(
  'Desktop:/home/h/Desktop'
  'Documents:/home/h/Documents'
  'Downloads:/home/h/Downloads'
  'Pictures:/home/h/Pictures'
  'Videos:/home/h/Videos'
  'Music:/home/h/Music'
  'code:/home/h/code'
  'cv_output:/home/h/cv_output'
  'cloudfront-site:/home/h/cloudfront-site'
  'dotfiles:/home/h/.restore-dotfiles'
  'config:/home/h/.restore-config'
  'local:/home/h/.restore-local'
  'hermes:/home/h/.hermes'
)
mkdir -p /tmp/s3-restore-check
printf '%-18s %-10s %-12s %-12s %s\n' 'SOURCE' 'LOCAL?' 'LOCAL_SIZE' 'MISSING_CT' 'SAMPLE_MISSING_OR_DIFF'
for item in "${checks[@]}"; do
  src=${item%%:*}; dst=${item#*:}
  outfile="/tmp/s3-restore-check/${src//\//_}.dryrun"
  aws s3 sync "s3://$bucket/$prefix/$src" "$dst" --dryrun > "$outfile" 2>&1 || true
  miss=$(grep -E 'download: ' "$outfile" 2>/dev/null | wc -l | tr -d ' ' || true)
  if [ -d "$dst" ]; then exists=yes; size=$(du -sh "$dst" 2>/dev/null | cut -f1); else exists=no; size='-'; fi
  sample=$(grep -E 'download: ' "$outfile" 2>/dev/null | sed -n '1,3p' | cut -c1-180 | tr '\n' '|' || true)
  [ -n "$sample" ] || sample='-'
  printf '%-18s %-10s %-12s %-12s %s\n' "$src" "$exists" "$size" "$miss" "$sample"
done
```

Keep full dry-run logs in `/tmp/s3-restore-check/` and summarize by category for the user.

## Hermes-specific caution

If Hermes is currently running, do **not** blindly sync old `hermes/` over live `~/.hermes`. Restore it to an inspection directory first, then selectively compare/copy useful files.

Safer pattern:

```bash
aws s3 sync "s3://$bucket/$prefix/hermes" "$HOME/old-hermes-backup" --dryrun
# If user wants it, sync to old-hermes-backup, not ~/.hermes.
```

## Reporting

Use a simple table: source folder, local exists, local size, missing/different count. Then list only important samples. Say explicitly when you verified only S3/object presence versus a full source-vs-restore comparison.