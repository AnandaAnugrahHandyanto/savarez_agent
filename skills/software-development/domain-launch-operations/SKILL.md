---
name: domain-launch-operations
description: Use when researching domains, registering domains, configuring DNS/SSL, or handing a domain from Porkbun to Cloudflare as part of a gated launch workflow.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [domains, dns, cloudflare, porkbun, launch, safety]
    related_skills: [self-hosted-service-operations, security-review-operations]
---

# Domain Launch Operations

## Overview

This skill covers the domain and DNS half of an MVP launch: naming research, registrar availability checks, domain registration, Cloudflare zone setup, nameserver handoff, SSL mode, and DNS records.

It is intentionally **gated**. Domain purchases, nameserver changes, domain deletion, DNS cutovers, and public production exposure are external side effects. Do safe discovery first, show exact facts, and require explicit user approval before changing anything.

## When to Use

- A user wants domain ideas or availability checks for a project.
- A workflow needs Porkbun registration plus Cloudflare DNS/SSL.
- You are preparing a production launch after a preview site passes checks.

Do not use this for general web hosting unrelated to a domain launch; use `self-hosted-service-operations` instead.

## Safe Workflow

1. **Read the PRD/project brief** and extract product name, audience, geography, and brand constraints.
2. **Generate candidates** from the brand name, short verb prefixes, and relevant TLDs.
3. **Check availability/prices only**. This is safe if API credentials are already configured.
4. **Report exact choices**: domain, registrar, yearly price, premium status, min term, and any renewal caveats.
5. **Ask for explicit approval** before purchase. The approval text should include the exact domain and immediate charge.
6. After purchase, configure nameservers/DNS/SSL in small verifiable steps.
7. Verify with registrar API, Cloudflare API, `dig NS`, `dig A/CNAME`, and `curl -I https://domain` where applicable.

## Safety Gates

Require user confirmation before:

- Registering a domain or accepting any charge.
- Changing nameservers.
- Creating public DNS records for production.
- Deleting/canceling a domain or disabling auto-renew.
- Exposing a private preview publicly.

For deletion/cancellation, require exact-domain approval, e.g. `delete example.com`.

## Configuration

Prefer non-secret config in a YAML file and secrets in the runtime secret manager/env:

```yaml
# ~/.hermes/mvp-launcher.yaml
registrar:
  provider: porkbun
dns:
  provider: cloudflare
launch:
  default_tlds: [com, app, io]
  max_domain_budget_usd: 50
```

Expected secret names, if using Porkbun/Cloudflare scripts:

- `PORKBUN_API_KEY`
- `PORKBUN_SECRET_KEY`
- `CF_API_TOKEN`

Never print these values.

## Verification Checklist

- [ ] Candidate domains and prices are current and sourced from the registrar/API.
- [ ] No purchase/change was made before explicit user approval.
- [ ] Nameserver handoff is verified at registrar and with DNS lookup.
- [ ] Cloudflare zone/SSL state is verified via API or dashboard output.
- [ ] Final public endpoint responds over HTTPS before declaring launch complete.
