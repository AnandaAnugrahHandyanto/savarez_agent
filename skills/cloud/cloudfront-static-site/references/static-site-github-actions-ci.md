# Static site GitHub Actions CI/CD checks

Use this when a static S3 + CloudFront site has a GitHub Actions deploy workflow and the user asks to test whether CI/CD works.

## Fast verification flow

1. Identify the deploy repo and inspect the workflow:
   ```bash
   gh workflow list --repo OWNER/REPO
   gh run list --repo OWNER/REPO --limit 10
   gh run view RUN_ID --repo OWNER/REPO --json status,conclusion,jobs
   ```

2. If the latest deploy failed before upload, inspect the failed step:
   ```bash
   gh run view RUN_ID --repo OWNER/REPO --json jobs \
     --jq '{status,conclusion,jobs:[.jobs[]|{name,conclusion,steps:[.steps[]|{name,conclusion,status}]}]}'
   ```

3. Common static-site deploy failure: `Configure AWS Credentials` failed because repository secrets are stale or wrong. Refresh the GitHub Actions secrets from the intended AWS profile, without printing the values:
   ```bash
   ACCESS_KEY=$(aws configure get aws_access_key_id --profile PROFILE)
   SECRET_KEY=$(aws configure get aws_secret_access_key --profile PROFILE)
   [ -n "$ACCESS_KEY" ] && [ -n "$SECRET_KEY" ]
   printf '%s' "$ACCESS_KEY" | gh secret set AWS_ACCESS_KEY_ID --repo OWNER/REPO >/dev/null
   printf '%s' "$SECRET_KEY" | gh secret set AWS_SECRET_ACCESS_KEY --repo OWNER/REPO >/dev/null
   ```

4. Rerun and watch the deploy:
   ```bash
   gh run rerun RUN_ID --repo OWNER/REPO --failed
   gh run watch RUN_ID --repo OWNER/REPO --exit-status
   ```

5. Verify what actually deployed:
   ```bash
   aws s3 ls s3://BUCKET/ --recursive --human-readable --summarize --profile PROFILE
   curl -I -L https://DOMAIN/
   ```

## Pitfalls

- If you manually delete objects from S3, a later successful CI run may re-upload them if they still exist in the repository. Check the latest commit or clone the repo before declaring cleanup durable.
- `gh secret list` confirms secret names and update times only; it cannot validate the secret values. A rerun is the real test.
- Avoid reading secrets from ad-hoc local files unless you have verified they contain both access key and secret. Prefer `aws configure get ... --profile PROFILE` for an already-working AWS CLI profile.
- For CloudFront-backed private S3 origins, a missing object often appears as `403` rather than `404`; combine URL checks with `aws s3 ls` for certainty.
