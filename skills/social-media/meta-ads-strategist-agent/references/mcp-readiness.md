# MCP Readiness — Meta Ads Strategist Agent

This document defines how the Meta Ads Strategist Agent should behave once a Meta MCP server, Meta Ads CLI wrapper, or Marketing API bridge is connected.

## Goal

The agent should be able to move from:

```text
strategy-only → account read/audit → paused draft creation → approved live changes
```

without changing the core persona or playbooks.

## Tool Discovery Pattern

Hermes native MCP registers tools as:

```text
mcp_<server_name>_<tool_name>
```

For a future server named `meta_ads`, expected names might look like:

- `mcp_meta_ads_list_ad_accounts`
- `mcp_meta_ads_list_campaigns`
- `mcp_meta_ads_get_insights`
- `mcp_meta_ads_create_campaign`
- `mcp_meta_ads_create_ad_set`
- `mcp_meta_ads_create_ad_creative`
- `mcp_meta_ads_create_ad`
- `mcp_meta_ads_update_campaign`
- `mcp_meta_ads_update_ad_set`
- `mcp_meta_ads_update_ad`

Actual names may differ. The agent should inspect available tools and map capabilities conceptually.

## Minimum Capability Set

### Read-only MVP

The safest first integration only needs:

- list ad accounts
- get current ad account
- list campaigns
- list ad sets
- list ads
- list creatives
- get insights with date range and level
- list pages
- list pixels/datasets

This enables weekly audits and recommendations without write risk.

### Draft-builder V2

Add write actions that create paused resources:

- create campaign with `status=PAUSED`
- create ad set with `status=PAUSED`
- create creative
- create ad with `status=PAUSED`

### Live-operator V3

Only after governance is agreed:

- activate campaign/ad set/ad
- pause campaigns/ad sets/ads
- update budgets
- update bids/bid strategy
- update targeting
- archive/delete resources

These require explicit user approval per action.

## Suggested MCP Server Config Shape

Example only; do not commit real secrets.

```yaml
mcp_servers:
  meta_ads:
    command: "uvx"
    args: ["company-meta-ads-mcp"]
    env:
      META_ACCESS_TOKEN: "${META_ACCESS_TOKEN}"
      META_AD_ACCOUNT_ID: "${META_AD_ACCOUNT_ID}"
      META_BUSINESS_ID: "${META_BUSINESS_ID}"
    timeout: 180
    connect_timeout: 60
    sampling:
      enabled: false
```

If using HTTP transport:

```yaml
mcp_servers:
  meta_ads:
    url: "https://mcp.example.com/meta-ads"
    headers:
      Authorization: "Bearer ${META_MCP_TOKEN}"
    timeout: 180
    connect_timeout: 60
    sampling:
      enabled: false
```

## Secret Safety

Never print or summarize:

- Meta system user access tokens
- app secrets
- page tokens
- business tokens
- cookies
- `.env` files
- MCP headers

To verify auth, use status/list calls that do not expose tokens.

## Approval Boundaries

The agent may do without approval:

- read account structure
- read insights
- summarize performance
- generate recommendations
- create local draft plans/files

The agent needs explicit approval before:

- creating objects in a real ad account, even paused, unless the user explicitly requested draft creation
- activating any object
- increasing/decreasing budget
- pausing currently active campaigns/ad sets/ads
- deleting/archiving anything
- changing tracking, pixel, catalog, or page settings

## Dry-Run Contract

Every write-capable flow should support a dry-run response:

```markdown
## Proposed Meta Action Plan — Dry Run

No account changes have been made.

### Would create
- Campaign: ...
- Ad set: ...
- Ad: ...

### Required approvals
1. Create paused drafts? yes/no
2. Activate after QA? yes/no, separate later approval
```

## Verification After Writes

After any approved write, return:

- object type
- object ID
- name
- status
- parent object ID
- created/updated timestamp if available
- any warnings/errors from the API
- link to Ads Manager if available

## Failure Handling

If an MCP/API call fails:

1. Report the action attempted.
2. Report sanitized error text.
3. Do not retry destructive writes automatically.
4. For transient read failures, retry once.
5. Suggest the next diagnostic: auth, permission scope, account ID, business manager access, rate limit, or object validation.

## Meta Ads CLI Compatibility

If MCP is not available but the official Meta Ads CLI is installed, follow the same governance:

- use JSON output for reads
- create resources paused by default
- verify IDs/status after create
- do not pass tokens in commands
- do not use verbose modes that print credentials

Related skill: `meta-ads-cli`.
