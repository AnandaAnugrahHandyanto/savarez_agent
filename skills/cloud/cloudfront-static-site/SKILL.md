---
name: cloudfront-static-site
description: Provision an S3-backed static website served through CloudFront with Origin Access Control using AWS CLI.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# CloudFront Static Website via CLI

## When to Use
- Need to host static assets securely through CloudFront
- Want S3 origin locked behind Origin Access Control (OAC)
- Working on bare CLI (no IaC yet)

## Prerequisites
- AWS CLI v2 configured
- `openssl`, `sed`, `curl`
- Working directory under `~/cloudfront-site`

## Steps

### 1. Initialize project folder
```
mkdir -p ~/cloudfront-site
cat <<'EOF' > ~/cloudfront-site/config.env
SITE_NAME=cloudfront-demo
AWS_REGION=us-east-1
EOF
```
Export when needed:
```
set -a; source ~/cloudfront-site/config.env; set +a
```

### 2. Add sample site files
```
mkdir -p ~/cloudfront-site/site
cat <<'EOF' > ~/cloudfront-site/site/index.html
<!doctype html>
<html><body><h1>CloudFront is live!</h1></body></html>
EOF
cat <<'EOF' > ~/cloudfront-site/site/error.html
<!doctype html>
<html><body><h1>Oops!</h1></body></html>
EOF
```

### 3. Create S3 bucket (unique per run)
```
source ~/cloudfront-site/config.env
RAND=$(openssl rand -hex 4)
BUCKET_NAME="${SITE_NAME}-${RAND}"
aws s3api create-bucket --bucket "$BUCKET_NAME" --region "$AWS_REGION"
echo "BUCKET_NAME=$BUCKET_NAME" >> ~/cloudfront-site/config.env
```
Enable protections:
```
aws s3api put-bucket-versioning --bucket "$BUCKET_NAME" --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket "$BUCKET_NAME" --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```
Sync assets:
```
aws s3 sync ~/cloudfront-site/site s3://$BUCKET_NAME/ --delete
```

### 4. Create Origin Access Control
```
OAC_ID=$(aws cloudfront create-origin-access-control \
  --origin-access-control-config Name="${SITE_NAME}-oac",Description="OAC for ${BUCKET_NAME}",OriginAccessControlOriginType=s3,SigningBehavior=always,SigningProtocol=sigv4 \
  --query 'OriginAccessControl.Id' --output text)
echo "OAC_ID=$OAC_ID" >> ~/cloudfront-site/config.env
```

### 5. Bucket policy locking to distribution
Create template `~/cloudfront-site/policies/bucket-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontOACReadOnly",
      "Effect": "Allow",
      "Principal": {"Service": "cloudfront.amazonaws.com"},
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::BUCKET_NAME/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::ACCOUNT_ID:distribution/DIST_ID"
        }
      }
    }
  ]
}
```
Replace placeholders once distribution ID is known (Step 7). Without the specific Distribution ARN, CloudFront returns 403 — update policy immediately after distribution creation.

### 6. Build distribution config
```
cat <<EOF > ~/cloudfront-site/distribution-config.json
{
  "CallerReference": "$(date +%s)",
  "Comment": "CloudFront for ${SITE_NAME}",
  "Enabled": true,
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "s3-${BUCKET_NAME}",
        "DomainName": "${BUCKET_NAME}.s3.${AWS_REGION}.amazonaws.com",
        "S3OriginConfig": {"OriginAccessIdentity": ""},
        "OriginAccessControlId": "${OAC_ID}"
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-${BUCKET_NAME}",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {"Quantity": 2, "Items": ["GET","HEAD"]},
    "Compress": true,
    "ForwardedValues": {"QueryString": false, "Cookies": {"Forward": "none"}},
    "TrustedSigners": {"Enabled": false, "Quantity": 0},
    "MinTTL": 0,
    "DefaultTTL": 86400,
    "MaxTTL": 31536000
  },
  "DefaultRootObject": "index.html"
}
EOF
```

### 7. Create distribution & log output
```
DIST_ID=$(aws cloudfront create-distribution --distribution-config file://~/cloudfront-site/distribution-config.json --query 'Distribution.Id' --output text)
DIST_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)
echo "DIST_ID=$DIST_ID" >> ~/cloudfront-site/config.env
```
Update bucket policy placeholders with actual `ACCOUNT_ID`, `BUCKET_NAME`, `DIST_ID` (Step 5 template). Apply:
```
aws s3api put-bucket-policy --bucket "$BUCKET_NAME" --policy file://~/cloudfront-site/policies/bucket-policy.json
```

### 8. Wait for deployment and test
```
aws cloudfront wait distribution-deployed --id "$DIST_ID"
curl -I "https://${DIST_DOMAIN}/"
```
Expect HTTP/2 200. If 403 persists, ensure bucket policy references the specific distribution ARN (not wildcard).

### 9. Updates & invalidations
- Sync site updates using `aws s3 sync ...`
- For an existing site, first inspect the bucket layout with `aws s3 ls s3://$BUCKET_NAME/` and run a dry-run sync before changing anything:
```
aws s3 sync /path/to/local/site s3://$BUCKET_NAME/ --delete --dryrun
```
- Be careful to sync the real site root, not its parent directory. Syncing the parent can create an unwanted nested prefix (for example `ingneeringwebsite/` inside the bucket) and leave stale duplicate files behind.
- After confirming the path is correct, run the real sync with `--delete` to clean old nested copies:
```
aws s3 sync /path/to/local/site s3://$BUCKET_NAME/ --delete
```
- Invalidate cache when needed:
```
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
```
- For custom domains, verify the actual public URL too, not just the CloudFront domain:
```
curl -I https://your-domain.example/
```

### 10. Custom domain follow-up
Document or automate ACM cert request (us-east-1), update distribution `Aliases` + `ViewerCertificate`, then configure DNS alias.

## Pitfalls
- CloudFront rejects configs missing `S3OriginConfig.OriginAccessIdentity` even when using OAC — set it to empty string.
- Bucket policy must include specific `arn:aws:cloudfront::<acct>:distribution/<id>`; wildcard `distribution/*` can cause 403.
- Remember CloudFront propagation may take several minutes.
- When updating an existing static site from a local folder, verify asset references before syncing. HTML exported from Windows often contains broken absolute paths like `c:\Users\...\image.webp` or references to missing files such as `images/example2.jpg`; these upload fine as HTML but the browser cannot load the assets in production.
- After an invalidation, browser sessions may still show cached HTML/images. Verify with `curl` or load the page with a cache-busting query string such as `?v=2` before assuming the deployment failed.
- If you manually delete stale prefixes from S3, confirm the deploy repository no longer contains those paths before rerunning CI; otherwise a successful `aws s3 sync` workflow can re-upload them.

## Updating an existing deployed site

For GitHub Actions-based S3/CloudFront deployments, see `references/static-site-github-actions-ci.md` for the CI/CD verification and stale-secret recovery flow.

For professional portfolio/site refreshes where the source repo deploys to S3/CloudFront, see `references/static-site-portfolio-refresh.md` for the edit → local visual QA → push → CI → production verification workflow.

For static dark/light mode additions, see `references/static-site-theme-toggle.md` for the CSS-variable theme pattern, accessible toggle behavior, and local/live verification checklist.

1. Load deployment values from `~/cloudfront-site/config.env`:
   ```bash
   source ~/cloudfront-site/config.env
   ```
2. Preview changes first:
   ```bash
   aws s3 sync /path/to/site s3://$BUCKET_NAME/ --delete --dryrun
   ```
3. If the site came from a designer export or Windows machine, scan HTML for broken asset references before upload. Look especially for:
   - `c:\Users\...`
   - `images/example...` pointing to files that do not exist
   - placeholder references like `photos/project1.jpg`
4. Sync the site:
   ```bash
   aws s3 sync /path/to/site s3://$BUCKET_NAME/ --delete
   ```
5. Invalidate CloudFront:
   ```bash
   aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths '/*'
   ```
6. Verify both origin content and CDN delivery:
   ```bash
   curl -s https://your-domain/page.html | sed -n '1,40p'
   curl -I https://your-domain/
   ```
7. If a page still appears broken in-browser but `curl` shows the fixed HTML, test with a cache-busting URL like `https://your-domain/page.html?v=2`.

## Verification
- `aws cloudfront wait distribution-deployed`
- `curl -I` returns HTTP/2 200 with index page
- `aws s3 ls s3://$BUCKET_NAME` shows files

## Cleanup
- `aws cloudfront delete-distribution` (after disabling)
- `aws s3 rb s3://$BUCKET_NAME --force`

Ready for reuse.