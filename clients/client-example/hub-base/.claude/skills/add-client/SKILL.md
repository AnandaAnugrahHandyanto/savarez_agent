---
name: add-client
description: Create a new client workspace via `ppcos init` and configure its Google Ads context and main-config entry. Use to onboard or set up a new client account.
argument-hint: "[client-name]"
---

# Add Client

Creates a new client workspace via `ppcos init`, gathers essential details, configures `ads-context.config.json` and `main-config.json`, and routes the user to specialized skills for deeper setup.

## Command Format

```
/add-client                    # Interactive — full guided setup
/add-client <client-name>      # Skip name prompt, start with details
```

**Examples:**
- `/add-client` — Full interactive flow: name, details, config
- `/add-client client-acme` — Start directly with client-acme

## Path Resolution

**Must be run from the hub root.**

To find the hub root:
1. Check current directory for `main-config.json` or `clients/` directory
2. If not found, walk up parent directories until found
3. The hub root is where `main-config.json` lives

If the current directory is inside a client subfolder (`clients/<name>/`), resolve up to the hub root before proceeding.

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `main-config.json` | Yes | Hub config — client list to update |
| `clients/<name>/config/ads-context.config.json` | Created | Google Ads context config |
| `clients/<name>/CLAUDE.md` | Created | Client context for Claude sessions |

## Process

### Phase 0: Prerequisites

1. **Find hub root** — walk up from cwd looking for `main-config.json`.
   - If not found: "Could not find hub root (no main-config.json). Run `ppcos init` from your hub directory first."
2. **Read `main-config.json`** — load existing client list to check for duplicates.

### Phase 1: Client Details

Gather client details via AskUserQuestion. Ask one question at a time.

**1. Client folder name** (skip if provided in command):

Ask: "What should the client folder be called?"

Show naming rules:
- Lowercase letters, numbers, and hyphens only
- Must start with a letter
- 1–50 characters
- Examples: `acme-corp`, `beta-inc`, `client-delta`

Validate against `^[a-z][a-z0-9-]{0,49}$`.

If the name already exists in `main-config.json` or `clients/` directory:
- "Client `{name}` already exists. Choose a different name or use `ppcos update` to update the existing client."

**2. Display name:**

Ask: "What's the client's company name? (used in reports and context)"
- Example: "Acme Corporation"

**3. Website:**

Ask: "What's the client's website URL? (optional — used for brand context scraping)"
- Can be left empty

**4. Google Ads Customer ID:**

Ask: "What's the Google Ads Customer ID? (digits only, e.g., `1234567890`)"
- Accept any format the user provides (with or without hyphens/spaces)
- Always strip to digits only before storing — e.g., `123-456-7890` → `1234567890`
- Validate: exactly 10 digits after stripping
- If invalid, ask again: "Customer ID must be 10 digits (e.g., `1234567890`)."

**5. Manager Account ID (MCC):**

Ask: "Is this account managed under an MCC? If yes, what's the Manager Account Customer ID? (digits only, e.g., `0987654321`, or leave empty if not applicable)"
- Optional — leave empty if direct account
- Same stripping rule: always store as digits only

**6. Primary conversion actions:**

Ask: "What are the main conversion actions? These must be the **exact names** as they appear in the Google Ads account (case-sensitive). Comma-separated, e.g., `Purchase`, `Lead`, `Phone Call`."
- No default — if left empty, keep the template default `["purchase", "lead"]`
- Store each value exactly as the user provides it — do not lowercase or modify

**7. Main competitors:**

Ask: "Who are the main competitors? (comma-separated domain names, e.g., competitor1.com, competitor2.com)"
- Optional — can be filled later

**8. Location:**

Ask: "What country/region is the target market? (e.g., US, UK, NL, AU, CA)"
- Map to location code:
  - US → 2840
  - UK → 2826
  - NL → 2528
  - CA → 2124
  - AU → 2036
  - DE → 2276
  - FR → 2250
  - BE → 2056
- If not in shortlist, tell user they can find their code in `.claude/skills/competitor-scraper/references/location-codes.json` after init and update `ads-context.config.json` manually.

### Phase 2: Confirmation

Present a summary of all gathered details:

```
Client Setup Summary:

  Folder name:     {client-name}
  Display name:    {display-name}
  Website:         {website or "—"}
  Customer ID:     {customer-id}
  Manager ID:      {manager-id or "—"}
  Conversions:     {conversion-actions}
  Competitors:     {competitor-domains or "—"}
  Location:        {location-name} ({location-code})
```

Ask via AskUserQuestion: "Does this look correct?"
- Options: "Yes, create the workspace" / "No, let me fix something"
- If "No" → ask which field to change, update it, re-display summary

### Phase 3: Initialize Workspace

Run the CLI command:

```bash
ppcos init {client-name}
```

This creates the workspace at `clients/{client-name}/` with all base skills, config files, and directory structure.

**If the command fails:**
- Show the error message
- Do not proceed to Phase 4
- Suggest: "Check `ppcos login` if authentication expired, or remove `clients/{client-name}/` if a partial install remains."

**If successful:** proceed to Phase 4.

### Phase 4: Credentials

Copy API credentials from an existing client so the user doesn't have to set up `.env` from scratch.

1. **Scan for existing `.env` files** — check `clients/*/config/.env` for all sibling clients.

2. **If existing `.env` files found:**
   - List the clients that have credentials configured:
     ```
     Found existing credentials in:
       1. client-acme
       2. client-beta
     ```
   - Ask via AskUserQuestion: "Copy credentials from an existing client?"
     - Options: list each client name, plus "No, I'll set it up manually"
   - If user picks a client → copy `clients/{source}/config/.env` to `clients/{client-name}/config/.env`
   - Delete `clients/{client-name}/config/.env.example` — no longer needed

3. **If no existing `.env` files found:**
   - Tell the user: "No existing credentials found. Set up `clients/{client-name}/config/.env` using the `.env.example` template before running data pulls."
   - Keep `.env.example` in place as reference

### Phase 5: Configure Files

#### 5a. Update `main-config.json`

Read the current `main-config.json`. Find the client entry that `ppcos init` just added (it only adds `name` and `enabled`). Update it with the gathered details:

```json
{
  "name": "{client-name}",
  "displayName": "{display-name}",
  "website": "{website}",
  "googleAdsCustomerId": "{customer-id}",
  "enabled": true
}
```

Write the updated `main-config.json`.

#### 5b. Update `ads-context.config.json`

Read `clients/{client-name}/config/ads-context.config.json`. Update these fields with gathered values:

- `googleAds.customerId` → customer ID (already digits-only from Phase 1)
- `googleAds.loginCustomerId` → manager ID (already digits-only from Phase 1) or leave as-is if empty
- `googleAds.clientName` → display name
- `googleAds.conversionActions` → parsed conversion actions array
- `competitors.domains` → parsed competitor domains array
- `competitors.location_code` → mapped location code

Write the updated file. Leave all other fields (`dateRange`, `searchTermAnalysis`, `ngramAnalysis`) at their template defaults.

#### 5c. Update `CLAUDE.md`

Read `clients/{client-name}/CLAUDE.md`. The template file does not have placeholder fields to fill — it's a complete system prompt. No changes needed unless the user specifically asked to customize it.

### Phase 6: Summary & Next Steps

Display completion message:

```
Client "{display-name}" ({client-name}) created successfully!

  Workspace:  clients/{client-name}/
  Config:     clients/{client-name}/config/ads-context.config.json
  Context:    clients/{client-name}/context/business.md

Next steps:
  1. cd clients/{client-name}
  2. Run /ads-context-gatherer {website} — scrape brand context from their website
  3. Run /business-context — set up business goals, KPIs, and strategy
  4. Run /gads-context — pull Google Ads account data
  5. Fine-tune config/ads-context.config.json thresholds as you learn the account
```

If no website was provided, skip step 2 in the next steps.

## Error Handling

| Error | Message |
|-------|---------|
| Hub root not found | "Could not find hub root (no main-config.json). Run `ppcos init` from your hub directory first." |
| Client name invalid | "Invalid name. Use lowercase letters, numbers, and hyphens only. Must start with a letter." |
| Client already exists | "Client `{name}` already exists. Use `ppcos update` to update, or choose a different name." |
| `ppcos init` fails | Show error output. Suggest checking auth with `ppcos login`. |
| Invalid customer ID format | "Customer ID must be 10 digits (e.g., `1234567890`)." |
| Config file write fails | "Could not write to {file}. Check file permissions." |

## Integration Points

### Reads From
- `main-config.json` — existing client list

### Produces
- `clients/{name}/` — full client workspace (via `ppcos init`)
- `main-config.json` — updated with client details
- `clients/{name}/config/ads-context.config.json` — updated with Google Ads config
- `clients/{name}/config/.env` — copied from existing client (if available)

### Downstream Skills (suggested next steps)
- `/ads-context-gatherer` → scrape website for brand context
- `/business-context` → interactive business context interview
- `/gads-context` → pull Google Ads account data
- `/account-changelog` → fetch recent account changes
