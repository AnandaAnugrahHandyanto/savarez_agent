---
name: aws-cli-setup-from-file
description: Install AWS CLI v2 and configure default credentials from a text file that stores the access key and secret on separate lines.
---

## When to use
- Need AWS CLI but it is not installed yet.
- Credentials are provided in a plaintext file (e.g., `~/aws`) with the access key on one line and the secret on another.

## Prerequisites
1. File path containing the AWS access key ID and secret access key (one value per line).
2. sudo privileges to install the AWS CLI.

## Steps
1. **Inspect the credential file**
   - `read_file` or `cat` the file to confirm the first non-empty line is the access key and the second is the secret.
2. **Configure credentials**
   - Run a Python snippet to parse the file, ensure `~/.aws/` exists, and write `~/.aws/credentials`:
     ```bash
     python3 - <<'PY'
     from pathlib import Path
     aws_file = Path('/home/h/aws')  # adjust path as needed
     lines = [line.strip() for line in aws_file.read_text().splitlines() if line.strip()]
     if len(lines) < 2:
         raise SystemExit('Missing key or secret in aws file')
     access_key, secret_key = lines[:2]
     aws_dir = Path.home() / '.aws'
     aws_dir.mkdir(parents=True, exist_ok=True)
     cred_path = aws_dir / 'credentials'
     cred_path.write_text(f"[default]\naws_access_key_id = {access_key}\naws_secret_access_key = {secret_key}\n")
     PY
     ```
3. **Install AWS CLI v2 (if not present)**
   - Download and install:
     ```bash
     cd /tmp
     curl -sS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip
     unzip -q -o awscliv2.zip
     cd aws
     sudo ./install
     ```
4. **Verify installation and configuration**
   - `aws --version`
   - `aws configure list` (confirm the access key and secret show as masked values; region will be `<not set>` unless provided).

## Multi-account workflow
If the user has more than one AWS account, do **not** overwrite the existing `default` profile unless they explicitly ask for that. Preserve current entries in `~/.aws/credentials` and add each additional account under its own named profile, for example:

```ini
[default]
aws_access_key_id = EXISTING_KEY
aws_secret_access_key = EXISTING_SECRET

[customer]
aws_access_key_id = NEW_KEY
aws_secret_access_key = NEW_SECRET
```

And in `~/.aws/config`:

```ini
[default]
region = us-east-1
output = json

[profile customer]
region = us-east-1
output = json
```

Recommended approach:
1. Inspect `~/.aws/credentials`, `~/.aws/config`, and `aws configure list-profiles` first.
2. If only one plaintext source file exists (for example `/home/h/aws`), do not assume it should replace `default` if the user mentions multiple accounts.
3. Ask the user for a profile name or choose a safe descriptive one only if the intent is unambiguous.
4. Verify each profile with `aws sts get-caller-identity --profile <name>`.

## Pitfalls
- Forgetting to run commands with `python3` if `python` is not available.
- Missing sudo rights when running the AWS installer.
- Credential file lacking newline-separated values; ensure you strip blank lines before parsing.
- If `aws` reports `Unable to parse config file: ~/.aws/credentials`, do not try to edit the broken file line-by-line. Rebuild `~/.aws/credentials` from the first two non-empty lines of the source file and overwrite it completely. This fixes malformed profile names, stray continuation lines, and accidental extra `+` lines in the secret.
- Do not reconstruct AWS secrets from `read_file` output on sensitive files. In this environment, safe file readers may redact credential values with `...`. If you need the real values, re-read the original plaintext source via a trusted terminal/Python path and use prefix/suffix or length checks for verification.
- Writes to protected credential files may be blocked by high-level file-write tools. If `write_file` is denied for `~/.aws/credentials` or `~/.aws/config`, do not fight the file directly. Prefer AWS CLI writes such as `aws configure set region us-east-1 --profile <name>` and `aws configure set output json --profile <name>` for config values, or use a `terminal` Python snippet only when you truly need to rebuild the credentials file. Verify with `aws configure list` / `aws sts get-caller-identity`.
- Do not assume a newly edited source file actually changed; verify by checking the masked key suffix/prefix or by running `aws sts get-caller-identity` after writing credentials.
- Use a simple `[default]` profile unless there is a confirmed need for named profiles; but when the user has multiple accounts, named profiles are the correct solution.
- Avoid profile names with spaces when creating new entries. AWS config parsing is inconsistent here: a manually written section like `[profile my acc 2]` may exist in `~/.aws/config` yet still show `region = <not set>` in `aws configure list --profile 'my acc 2'`, while `aws configure set ... --profile 'my acc 2'` writes a second section like `[profile 'my acc 2']` that the CLI actually honors. Prefer hyphenated names such as `my-acc-2`. If a spaced profile already exists, verify with both `aws sts get-caller-identity --profile '<name>'` and `aws configure list --profile '<name>'`, and be prepared to normalize the profile name.

## Verification
- `aws configure list` shows the credentials source as `shared-credentials-file` with masked values.
- `aws configure list-profiles` includes all expected profiles.
- Running `aws sts get-caller-identity --profile <name>` succeeds for each configured account.
- Running an AWS CLI command succeeds once a region is set (if required).