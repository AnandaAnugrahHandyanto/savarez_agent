---
name: preview-deployment
description: Use when deploying an MVP or generated website to a private preview URL before production, especially via Docker, Traefik, Tailscale, or a configurable preview domain.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [preview, deployment, docker, traefik, tailscale, smoke-tests]
    related_skills: [self-hosted-service-operations, browser-automation-operations]
---

# Preview Deployment

## Overview

Preview deployment creates a private or limited-access URL for testing before production. It should be configurable and reversible: build an image or static artifact, deploy under a preview hostname, run smoke/E2E checks, collect feedback, then either promote or tear down.

Do not hardcode a single preview server or domain in reusable instructions. Treat Batumi preview infrastructure as one backend, configured by environment or YAML.

## When to Use

- A newly built MVP needs a testable URL before production.
- The user wants a Tailscale/private preview under a known preview domain.
- A production launch should be blocked until preview smoke/E2E checks pass.

## Configuration

Example:

```yaml
# ~/.hermes/mvp-launcher.yaml
preview:
  domain: preview.batumi.org
  ssh_target: root@preview-host
  docker_network: traefik-public
  access: tailscale
```

Environment override names:

- `MVP_LAUNCHER_PREVIEW_DOMAIN`
- `MVP_LAUNCHER_PREVIEW_SSH`
- `MVP_LAUNCHER_PREVIEW_NETWORK`
- `MVP_LAUNCHER_PREVIEW_ACCESS`

## Deployment Pattern

1. Build or package the app.
2. Transfer artifact/image to the preview host.
3. Start a uniquely named preview service/container.
4. Attach routing labels/Ingress for `project.preview-domain`.
5. Verify DNS/routing/HTTPS.
6. Run smoke checks and, when needed, browser-based tests.
7. Save preview URL, commit SHA/build ID, and test report.

## Quality Gate

Preview checks should include at minimum:

- homepage HTTP 200
- HTTPS or intentionally private HTTP documented
- primary pages/routes
- no obvious server errors in logs
- no placeholder/fake production data
- forms either tested or explicitly marked manual

For real browser claims, use Playwright/Hermes browser automation. Plain `urllib`/`curl` checks are HTTP smoke tests, not browser E2E.

## Verification Checklist

- [ ] Preview target and domain came from config, not hardcoded code.
- [ ] Preview URL is reachable from the expected network.
- [ ] Smoke/browser results are saved.
- [ ] Production remains untouched until preview passes and user approves promotion.
- [ ] Rollback/cleanup command is known before deploy.
