---
name: connect-github-repo-to-existing-aws-static-site
description: Connect an existing GitHub repository to an already-deployed S3 + CloudFront static website using GitHub Actions, including AWS credential repair, workflow retargeting, repo secret/variable setup, and live verification.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Connect GitHub Repo to Existing AWS Static Site

Use this when:
- a website is already live on AWS via S3 + CloudFront
- the user wants GitHub pushes to deploy that live site
- there may already be a repo and/or existing workflow, but it may point at the wrong AWS resources
- AWS credentials may exist in a local plaintext file like `/home/h/aws`

## Goal

Make a GitHub repo the source of truth for an already-running AWS static website, without provisioning a new site by mistake.

## High-level strategy

1. Identify the actual live AWS site resources first.
2. Identify which GitHub repo actually matches the deployed site content.
3. Inspect any existing GitHub Actions workflow before changing it.
4. Retarget the workflow to the real bucket/distribution/region.
5. Set repo secrets and variables.
6. Trigger a deployment and verify both GitHub Actions and the public URL.

---

## 1. Load relevant skills first

Load at least:
- `cloudfront-static-site`
- `github-repo-management`
- `github-pr-workflow`
- `aws-cli-setup-from-file` if local AWS credentials are stored in a plaintext file

---

## 2. Discover the real live AWS site

If local config exists, inspect it first:

```bash
read_file /home/h/cloudfront-site/config.env
```

Typical useful values:
- `BUCKET_NAME`
- `DIST_ID`
- region
- custom domains

Then verify live AWS resources with the CLI:

```bash
aws sts get-caller-identity
aws cloudfront get-distribution --id <DIST_ID> --output json
aws s3 ls s3://<BUCKET_NAME>/
```

Useful things to capture:
- CloudFront domain name
- aliases/custom domains
- S3 origin domain
- default root object
- sample object names in the bucket

### Important
Do **not** assume the repo name matches the live site. Verify against actual S3 object names and live distribution metadata.

---

## 3. If AWS CLI is broken because credentials were pointed at the raw source file, repair it

A recurring failure mode is:

```text
aws: [ERROR]: Unable to parse config file: /home/h/aws
```

This happens when a plaintext credential source file is incorrectly used as an AWS config/credentials file.

If `/home/h/aws` contains the access key and secret on separate non-empty lines, rebuild `~/.aws/credentials` from it.

Python pattern:

```python
from pathlib import Path
import os

src = Path('/home/h/aws')
lines = [line.strip() for line in src.read_text().splitlines() if line.strip()]
access_key, secret_key = lines[:2]
aws_dir = Path.home() / '.aws'
aws_dir.mkdir(parents=True, exist_ok=True)
(aws_dir / 'credentials').write_text(
    f'[default]\naws_access_key_id = {access_key}\naws_secret_access_key = {secret_key}\n'
)
(aws_dir / 'config').write_text('[default]\nregion = us-east-1\noutput = json\n')
```

Then verify:

```bash
aws configure list
aws sts get-caller-identity
```

### Pitfall
Do not pass the plaintext source file as `AWS_SHARED_CREDENTIALS_FILE` unless it is already formatted like a real INI credentials file.

---

## 4. Identify which repo actually matches the site

List candidate repos:

```bash
gh repo list <owner> --limit 20 --json name,nameWithOwner,isPrivate,url,defaultBranchRef
```

Clone likely candidates and compare their contents to the S3 bucket listing:

```bash
gh repo clone owner/repo-a /tmp/repo-a
gh repo clone owner/repo-b /tmp/repo-b
find /tmp/repo-a -maxdepth 2 -type f | sort | head -50
find /tmp/repo-b -maxdepth 2 -type f | sort | head -50
```

Look for distinctive HTML/image/video filenames that overlap with S3 objects.

### Key lesson
The repo that should deploy the site may **not** be the repo with the most obvious name. Match by actual file inventory, not assumptions.

---

## 5. Inspect any existing workflow before replacing it

Check for workflows:

```bash
find .github -maxdepth 3 -type f | sort
read_file .github/workflows/deploy.yml
```

Common findings:
- workflow already exists
- it deploys to the wrong bucket
- wrong CloudFront distribution ID
- wrong AWS region
- hardcoded values instead of repo variables

### Important
Prefer retargeting a working deploy workflow over replacing it wholesale.

---

## 6. Recommended workflow shape for an existing live site

Use repo variables for non-secret deployment targets and secrets for credentials.

Example workflow:

```yaml
name: Deploy site to AWS

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    env:
      AWS_REGION: ${{ vars.AWS_REGION }}
      S3_BUCKET: ${{ vars.S3_BUCKET }}
      CLOUDFRONT_DISTRIBUTION_ID: ${{ vars.CLOUDFRONT_DISTRIBUTION_ID }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Deploy site to S3
        run: |
          aws s3 sync . "s3://${S3_BUCKET}" \
            --delete \
            --exclude ".git/*" \
            --exclude ".github/*" \
            --exclude "README.md" \
            --exclude "terraform/*"

      - name: Invalidate CloudFront cache
        run: |
          aws cloudfront create-invalidation \
            --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
            --paths "/*"
```

### Why variables matter
This avoids hardcoding environment-specific values in the workflow file and makes later migration/retargeting much safer.

---

## 7. Set GitHub repo secrets and variables

Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Variables:
- `AWS_REGION`
- `S3_BUCKET`
- `CLOUDFRONT_DISTRIBUTION_ID`

Important:
- The repo may already have AWS secrets from an older deployment target. Overwrite them with the current working credentials rather than assuming they are still correct.
- It is normal to find old secrets present but no repo variables yet.

Example:

```bash
gh secret set AWS_ACCESS_KEY_ID -R owner/repo --body "$AWS_ACCESS_KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY -R owner/repo --body "$AWS_SECRET_ACCESS_KEY"

gh variable set AWS_REGION -R owner/repo --body us-east-1
gh variable set S3_BUCKET -R owner/repo --body <bucket-name>
gh variable set CLOUDFRONT_DISTRIBUTION_ID -R owner/repo --body <distribution-id>
```

Verify:

```bash
gh secret list -R owner/repo
gh variable list -R owner/repo
```

---

## 8. Commit, push, trigger, verify

Before editing content, sync the local checkout to the current remote so you do not patch an old copy:

```bash
git fetch origin
git status -sb
git pull --ff-only
```

For small static-site behavior changes, patch the source file, then verify locally before pushing. Browser-based checks are useful for JavaScript/UI state such as theme toggles:

```js
// Fresh visitor/default-state probe after loading the local file or live URL
localStorage.removeItem('theme');
location.reload();
({
  theme: document.documentElement.getAttribute('data-theme'),
  button: document.getElementById('theme-toggle')?.textContent.trim(),
  meta: document.querySelector('meta[name="theme-color"]')?.content,
  stored: localStorage.getItem('theme')
})
```

If the site has a light/dark toggle and the requirement is “new visitors should see light mode,” do not initialize from `prefers-color-scheme`. Use saved user choice if present, otherwise force `light`:

```js
const savedTheme = localStorage.getItem('theme');
setTheme(savedTheme || 'light');
```

This preserves manual dark-mode choice while making fresh visits deterministic.

Commit and push the workflow/content change:

```bash
git add .github/workflows/deploy.yml index.html
git commit -m "ci: deploy website to current AWS CloudFront stack"  # adjust message for content-only changes
git push origin main
```

Optionally trigger manually too:

```bash
gh workflow run deploy.yml -R owner/repo
```

Check recent runs and wait for deployment when a push triggers CI:

```bash
gh run list -R owner/repo --workflow deploy.yml --limit 3
gh run watch <RUN_ID> -R owner/repo --exit-status
```

Verify public delivery with a cache-busting query string after CloudFront invalidation:

```bash
curl -I -L 'https://your-domain.example/?v=<commit-sha>'
curl -I -L 'https://<cloudfront-domain>/?v=<commit-sha>'
```

For UI/JS changes, also inspect the live DOM state in a browser against the cache-busted URL.

Expected result:
- GitHub Actions run succeeds
- public custom domain returns `HTTP 200`
- CloudFront domain returns `HTTP 200`
- relevant live DOM/state matches the requested behavior

---

## 9. Common pitfalls

### 1. Wrong repo
The live site may map to a different repo than expected. Compare bucket object names to repo contents.

### 2. Existing workflow points at dead infrastructure
Very common. Inspect before assuming it is usable.

### 3. Wrong AWS region
A static site may be live in `us-east-1` while an old workflow still points to another region such as `eu-north-1`.

### 4. AWS CLI parse error from raw credential source file
If `/home/h/aws` is just two lines, it is a credential source file, not a real AWS INI credentials file.

### 5. Over-syncing junk files
A root-level `aws s3 sync . ... --delete` will upload everything not excluded. Add excludes for `.git/*`, `.github/*`, docs, infra folders, and any non-site artifacts.

### 6. Node.js deprecation warnings in Actions
GitHub may warn that some actions still run on deprecated Node versions. This is not necessarily a deployment failure, but should be tracked for future action version bumps.

---

## 10. Reusable decision rule

If the user says “connect GitHub to my AWS website,” interpret it as:
- find the existing live AWS stack first
- find the correct content repo second
- connect deployment third

Do **not** start by provisioning new infrastructure unless the user explicitly asked for a new site.

## 11. Optional: give a teammate direct push access

If the user wants a friend to update the site from their own PC, add them as a collaborator with write access on the connected repo:

```bash
gh api -X PUT repos/<owner>/<repo>/collaborators/<github-username> -f permission=push
```

Expected result:
- GitHub returns an invitation object if the user was newly invited
- or confirms the collaborator permission if they already had access

Important:
- write access is enough for cloning, committing, and pushing
- if the workflow deploys on push to `main`, then collaborator pushes to `main` update the live site immediately
- tell the user to have the collaborator accept the GitHub invitation before trying to clone/push

## Verification checklist

Before finishing, verify all of these:
- AWS identity works with `aws sts get-caller-identity`
- live `DIST_ID` and `BUCKET_NAME` confirmed
- chosen GitHub repo content matches S3 object inventory
- workflow file points to correct region, bucket, distribution
- repo secrets and variables are set
- workflow run succeeds
- public domain and CloudFront domain both return `HTTP 200`
