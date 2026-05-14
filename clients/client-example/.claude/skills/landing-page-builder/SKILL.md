---
name: landing-page-builder
description: Generate high-converting landing page HTML wireframes from brand context and offer angles. Use for building landing pages or LP wireframes.
argument-hint: "[--skip-discovery] [--from-audit]"
---

# Landing Page Builder Skill

Generate a self-contained HTML landing page wireframe with real persuasive copy, brand-matched colors, and visual placeholders — ready to open in a browser and present to a client.

Built on the **Conversion Amplifier Framework** (Offer → Hierarchy → Copy → Design → Build).

## Command Format

```
/landing-page-builder [--skip-discovery] [--from-audit]
```

**Examples:**
- `/landing-page-builder` — Full interactive mode with 7-question discovery
- `/landing-page-builder --skip-discovery` — Derive settings from existing context files
- `/landing-page-builder --from-audit` — Use prior audit/optimize data (skips "use audit data?" confirmation)

---

## Process

### Phase 0: Prerequisites Check

Check required context files:

| File | Required | If Missing |
|------|----------|------------|
| `context/brand.md` | Yes | Prompt: "Run `/ads-context [URL]` first" |
| `context/offer-angles.md` | Yes | Prompt: "Run `/offer-maker angles` first" |

**Optional files (enhance output if present):**

| File | Used For |
|------|----------|
| `context/brand-colours/palette.md` | Brand colours and fonts (from `/ads-context`). If missing, defaults are used |
| `context/business.md` | Business goals, constraints, previous test learnings |
| `context/google-ads/data/keywords.csv` | Primary keywords for message match in headline |
| `context/google-ads/data/ads.csv` | Existing ad copy for message match reference |

**If required files are missing, stop and show:**

```markdown
## Prerequisites Missing

To build a landing page wireframe, the following context is required:

| File | Status | Action |
|------|--------|--------|
| context/brand.md | Missing | Run `/ads-context-gatherer [URL]` first |
| context/offer-angles.md | Missing | Run `/offer-maker angles` first |
```

**If one exists, show which is missing and the action to take.**

---

### Phase 0.5: Prior Audit Integration

Check if prior LP audit and optimization reports exist. If they do, leverage their findings to pre-populate discovery settings and seed copy generation — avoiding redundant analysis.

**If `--from-audit` flag is provided:** Skip the "use audit data?" confirmation (Step 4) and go straight to reduced discovery (Step 5).

#### Step 1 — Detect Reports

Check for:
- `context/analysis/lp-audit.md`
- `context/analysis/lp-optimize-audit.md` (primary — full optimization guidance)
- Any other `context/analysis/lp-optimize-*.md` files (elements, speed, message-match, etc.)

**If none exist:** Skip Phase 0.5 entirely. Proceed to Phase 1 as normal.

#### Step 2 — Extract Audit Context

**From `lp-audit.md`** (if exists), extract:

| Field | Where to find it |
|-------|-----------------|
| URL audited | Header: `**URL(s) Audited:**` line |
| Vertical | Header: `**Vertical:**` line |
| Overall score + grade | Header: `**Overall Score:**` line |
| D02: Hero headline quality | Structural Results table — current H1 text + PASS/WARN/FAIL + diagnosis |
| D04: CTA quality | Structural Results table — current CTA text + classification |
| D05: Benefits quality | Structural Results table — feature vs outcome diagnosis |
| D07: Social proof quality | Structural Results table — testimonial gaps (photos, titles, results) |
| D08: Objection handling | Structural Results table — FAQ coverage + objection types addressed |
| D09: Guarantee presence | Structural Results table — present/missing + placement |
| D11: One-page-one-goal | Structural Results table — FAIL status + link counts (this is usually why a new LP is needed) |
| D12: Section hierarchy | Structural Results table — sections present vs missing, sequence correctness |
| D13: Ad-to-LP headline match | Message Match Results table — ad headline text for message matching |

**From `lp-optimize-*.md`** (if exists), extract:

| Field | Where to find it |
|-------|-----------------|
| Recommended H1 | P2 Fix Recommendations table — "Recommended" column for headline fix |
| Recommended CTAs | P2 Fix Recommendations table — "Recommended" column for CTA fix |
| Recommended guarantee text | P2 Fix Recommendations table — "Recommended" column for guarantee fix |
| Recommended benefit rewrites | P2 Fix Recommendations table — "Recommended" column for benefits fix |
| Testimonial enhancement plan | P2 Fix Recommendations table — "Recommended" column for social proof fix |
| Recommended urgency text | P2 Fix Recommendations table — "Recommended" column for urgency fix |
| Implementation copy block | "For the Marketer" section — ready-to-use copy drafts |
| Expected impact estimates | Expected Impact table — CVR and CPA projections |

If multiple `lp-optimize-*.md` files exist, prefer `lp-optimize-audit.md` as the primary source (it's the most comprehensive). Read others for additional specific fixes.

#### Step 3 — Staleness Check

Parse the `**Date:**` field from the audit report header. If the audit is older than 14 days:

> "Audit report is {N} days old ({date}). Recommendations may be outdated. Consider re-running `/lp-auditor` first."

Still allow the user to proceed.

#### Step 4 — Present Summary and Ask

Show what was found:

```markdown
## Prior Audit Data Detected

I found existing audit and optimization reports for this page:

| Report | Date | Key Info |
|--------|------|----------|
| LP Audit | {date} | {score}% ({grade}) — {url} |
| LP Optimize — {action} | {date} | {P2 fix count} strategic fixes with copy recommendations |

### Key findings that will inform this build:
- **Vertical:** {vertical}
- **Current H1:** "{current_h1}" → **Recommended:** "{recommended_h1}"
- **Current CTAs:** "{current_ctas}" → **Recommended:** "{recommended_ctas}"
- **Missing sections:** {e.g., Urgency/Scarcity, Guarantee badge}
- **Weak sections:** {e.g., Benefits (feature-focused), Social Proof (no photos/titles)}
- **Strong sections to preserve:** {e.g., FAQ (12+ questions), Trust (1M+ installs)}

Would you like to use this audit data to inform the new landing page?
```

AskUserQuestion with options:
- **Yes, use audit data (Recommended)** — Pre-populate settings from audit. You'll confirm just 2 questions instead of 7
- **No, start fresh** — Ignore audit data and run full discovery

If user selects "No, start fresh": proceed to Phase 1 as normal.

#### Step 5 — Reduced Discovery

If user selects "Yes, use audit data" (or `--from-audit` flag was provided): replace Phase 1's 7 questions with this reduced flow.

**Auto-derived settings (no questions needed):**

| Setting | Derived From | Value |
|---------|-------------|-------|
| Vertical | Audit header `Vertical:` field | {e.g., SaaS} |
| Page length | Auto-recommended from awareness level (same logic as Phase 1 Q4) | {e.g., Full-length} |
| Offer details | `context/offer-angles.md` + audit D01 offer completeness | Auto-populated |
| Urgency | Audit D12 (if missing → include) + optimizer recommendation (if specific text exists) | {e.g., Yes — "Join 1M+ professionals"} |
| Objections | Audit D08 FAQ items that scored PASS — adapt rather than reinvent | Auto-populated from audit |

Present auto-derived settings in a confirmation table, then ask only these 2 questions:

**Question A: Awareness Level**

"The audit data suggests this page serves **{inferred awareness level}** traffic. Is this correct?"

Inference logic:
- If audit D13 mentions branded ad headlines → Most Aware
- If audit D13 mentions competitor ad headlines → Product Aware
- If audit mentions product/service search keywords → Solution Aware
- If unclear, default to Solution Aware (most common for paid traffic)

Options: Brand Search (Most Aware) | Competitor Search (Product Aware) | Product/Service Search (Solution Aware) | Problem Search (Problem Aware)

**Question B: Conversion Action**

"The current page converts via **{inferred action from D04}**. Should the new LP use the same conversion action?"

Inference logic: Parse D04 CTA details — "Sign up with Google" = free trial signup, "Get a demo" = demo request, "Contact us" = form submission, etc.

Options: (vertical-specific options from Phase 1 Q3, with inferred one marked as Recommended)

#### Step 6 — Build Context Objects

After reduced discovery, produce two context blocks that downstream phases consume:

**`AUDIT_ARCHITECTURE_CONTEXT`** (consumed by Phase 3):
```
Sections present: {from D12}
Sections missing: {from D12 — e.g., Urgency/Scarcity}
Section quality:
  - Hero: {WARN/FAIL} — needs full rewrite
  - Benefits: {WARN} — feature-focused, needs outcome rewrite
  - Trust/Authority: {PASS} — strong, preserve approach
  - Social Proof: {WARN} — incomplete, needs enrichment
  - Objection Handling: {PASS} — thorough, adapt items
  - Urgency: {missing} — add per optimizer
  - Guarantee: {WARN} — missing near CTAs, add badge
Emphasis overrides:
  - Where audit WARN/FAIL → increase emphasis one level above standard
  - Where audit PASS → maintain standard awareness-based level
```

**`AUDIT_COPY_SEEDS`** (consumed by Phase 4):
```
hero_h1: "{recommended H1 from optimizer}" (source: lp-optimize P2 Fix #N)
hero_subhead: "{recommended sub-headline}" (source: optimizer Implementation Notes)
hero_cta: "{recommended CTA}" (source: lp-optimize P2 Fix #N)
guarantee_text: "{recommended badge text}" (source: lp-optimize P2 Fix #N)
benefit_rewrites: ["{outcome-focused H2}", ...] (source: lp-optimize P2 Fix #N)
urgency_text: "{recommended urgency}" (source: lp-optimize P2 Fix #N)
testimonial_gaps: "{what's missing — photos, titles, companies, results}" (source: audit D07)
faq_items: ["{existing FAQ items that scored PASS}"] (source: audit D08)
trust_signals: ["{strong signals to preserve}"] (source: audit D06)
expected_impact: "{CVR and CPA projections}" (source: optimizer Expected Impact table)
```

---

### Phase 0.6: Peer Context Pull (Mode 2 — Enrichment, Informational)

**Purpose:** Before generating the LP, read fresh peer audit reports across the account and extract LP-relevant findings into a `PEER_CONTEXT` buffer. This is **purely informational** — no gates, no aborts, no hard-blocks. Peer findings are used to **bias** the generated output (section ordering, H1 wording, hero offer, differentiation), not to gate it.

This sub-phase runs after Phase 0.5 regardless of whether prior LP audit data exists. It is in addition to (not instead of) the LP audit-back signal flow. If a peer report is missing or stale, simply skip that signal — never abort.

#### Step 1 — Walk the 10-peer freshness table

For each peer report listed below, check if the file exists, parse the canonical `**Date:**` field from the report header, and classify as **fresh** (within window), **stale** (exists but older than window), or **missing** (no file).

| Peer skill | Report file | Fresh window | Highest-leverage signal for LP |
|------------|-------------|--------------|--------------------------------|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | LPE / AR informs hero design + copy alignment |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days | Top n-grams shape H1 / hero copy |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days | Per-AG themes for keyword-matched LP copy |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days | Budget context |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days | Posture context |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Differentiation positioning |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Offer angles for hero/CTA |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | Informational warning if dirty |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days | Break-even / posture for CVR target framing |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days | Account-level structure |

**Freshness rule:** the header `**Date:**` line is canonical. If the report header date contradicts the file mtime, surface the contradiction in the freshness summary (do NOT auto-pick — flag both for the user). Never override the header date silently.

#### Step 2 — Extract LP-relevant findings into `PEER_CONTEXT`

For each fresh peer report, extract only the highest-leverage signal (per the table above). Skip stale/missing reports — note them but do not extract. Build a `PEER_CONTEXT` buffer as follows:

```
PEER_CONTEXT:
  freshness_summary:
    - {peer}: {fresh|stale ({N} days old)|missing}
    - ... (one row per peer)
  contradictions:
    - {peer}: header date {X} vs file mtime {Y} — flagged, not auto-resolved
  signals:
    quality_score:
      lpe_findings: "{summary of LPE component issues — e.g., 'LPE below average on 4 ad groups, message match weak'}"
      ar_findings: "{summary of Ad Relevance issues — e.g., 'AR below average on branded ad groups'}"
      target_ad_groups: ["{ad group names where LPE/AR is the limiting component}"]
    search_terms:
      top_converting_ngrams: ["{n-gram 1}", "{n-gram 2}", ...]   # actual user search language
      top_volume_ngrams: ["{n-gram 1}", "{n-gram 2}", ...]
    keywords:
      themes_per_ad_group: { "{AG name}": "{theme phrase}", ... }
      primary_match_keywords: ["{kw 1}", "{kw 2}", ...]
    competitive:
      competitor_positioning: ["{angle competitors lead with}"]
      differentiation_gaps: ["{angle no competitor owns}"]
      our_position: "{summary of where we stand vs the field}"
    offer:
      recommended_angles: ["{angle 1}", "{angle 2}"]   # offer-audit's prioritized hero/CTA angles
      weakest_offer_dimensions: ["{value|urgency|trust|positioning}"]
      guarantee_recommendation: "{offer-audit guarantee guidance, if any}"
    budget:
      budget_limited_campaigns: ["{campaign 1}"]
      pacing_state: "{on-pace|under-pacing|over-pacing}"
    bidding:
      strategy_posture: "{tCPA|tROAS|MaxConv|MaxClicks}"
      learning_state: "{learning|learned|limited}"
    strategy:
      break_even_cvr: "{X%}"   # if available
      cpa_target: "{$X}"       # only if surfaced by strategy-specialist, never assumed
      roas_target: "{X}"       # only if surfaced
      posture: "{aggressive|balanced|efficient}"
    tracking:
      status: "{clean|dirty}"
      dirty_findings: ["{finding 1}", ...]   # informational warning only
    account:
      structure_notes: "{account-level structure findings relevant to LP routing}"
```

**Strict rules:**
- This is **read + extract only**. No prompts, no gates, no aborts.
- If a report is missing or stale → leave the corresponding `signals.{key}` empty and note it in `freshness_summary`. Do not attempt to fill from inference.
- Never assume CPA, ROAS, or CVR targets — only carry through values that strategy-specialist or business.md explicitly surfaces.

#### Step 3 — Surface informational notes (no gate)

Display a concise `PEER_CONTEXT` summary to the user before Phase 1, formatted as:

```markdown
## Peer Context (informational — no gate)

**Fresh peer signals applied:**
| Peer | Status | Will inform |
|------|--------|-------------|
| /offer-auditor | Fresh ({N}d) | Hero/CTA angles |
| /search-term-auditor | Fresh ({N}d) | H1 + hero copy language |
| /competitive-analyst | Fresh ({N}d) | Differentiation positioning |
| /quality-score-auditor | Fresh ({N}d) | Hero message-match emphasis |
| /keyword-auditor | Fresh ({N}d) | Per-theme copy |
| ... | ... | ... |

**Stale or missing (skipped):**
- /tracking-specialist: missing — proceeding without tracking context
- /strategy-specialist: stale (45d old) — break-even/posture context not applied

**Informational warnings:**
- Tracking audit is missing — the LP will be built, but conversion tracking should be validated separately before launch. (M-bucket dirty)
- Strategy audit is stale — break-even and CVR targets in the Summary phase are not peer-validated. (B-bucket dirty)

**Header-date contradictions:**
- {peer}: header date contradicts file mtime — flagged, you may want to re-run.
```

Proceed to Phase 1 regardless of which signals are fresh, stale, or missing. The `PEER_CONTEXT` buffer is now available for Phases 3, 4, 5, and 7.

---

### Phase 1: Discovery Questionnaire

**If Phase 0.5 completed with "Yes, use audit data":** Skip Phase 1 entirely. The audit-derived settings and reduced discovery answers replace all 7 questions. Proceed to Phase 2.

**If `--from-audit` flag was provided and Phase 0.5 completed:** Skip Phase 1. Proceed to Phase 2.

**If `--skip-discovery` flag is provided:** Skip to auto-derivation (see below).

Ask 7 questions using the AskUserQuestion tool. Ask questions in batches where possible to reduce back-and-forth.

#### Question 1: Traffic Type / Awareness Level

**Question:** "What type of traffic will this landing page serve?"

| Option | Description |
|--------|-------------|
| Brand Search (Most Aware) | People searching for your brand name — they know you and want the deal |
| Competitor Search (Product Aware) | People searching for competitor names — comparing alternatives |
| Product/Service Search (Solution Aware) | People searching for what you sell — evaluating solutions |
| Problem Search (Problem Aware) | People searching for their problem — not yet aware of solutions |

Use AskUserQuestion with these 4 options. multiSelect: false.

**If the user selects "Other"** (for Display/YouTube or Remarketing), ask them to specify the awareness level.

#### Question 2: Vertical

**Question:** "What type of business is this landing page for?"

| Option | Description |
|--------|-------------|
| Lead Gen | Services, consulting, agencies — conversion is a form fill, call, or booking |
| SaaS | Software products — conversion is a trial signup, demo request, or account creation |
| Ecommerce | Physical or digital products — conversion is a purchase or add-to-cart |

Use AskUserQuestion with these 3 options. multiSelect: false.

#### Question 3: Primary Conversion Action

**Question:** Dynamic based on vertical selected in Q2.

**Lead Gen options:**
| Option | Description |
|--------|-------------|
| Form submission | Contact form, quote request, lead magnet download |
| Phone call | Click-to-call or phone number display |
| Consultation booking | Calendar booking for a strategy call or demo |

**SaaS options:**
| Option | Description |
|--------|-------------|
| Free trial signup | Self-service trial with or without credit card |
| Demo request | Scheduled product demo or walkthrough |
| Account creation | Direct account signup |

**Ecommerce options:**
| Option | Description |
|--------|-------------|
| Purchase | Direct buy/add-to-cart |
| Pre-order | Reserve before launch |
| Free sample / trial | Try before you buy |

Use AskUserQuestion with 3 options based on the selected vertical. multiSelect: false.

#### Question 4: Page Length

Based on the awareness level from Q1, recommend a page length. Let the user override.

**Auto-recommendation logic:**
- Most Aware → Short-form (Recommended)
- Product Aware → Medium
- Solution Aware → Full-length (Recommended)
- Problem Aware → Long-form

**Question:** "How long should the landing page be?"

| Option | Description |
|--------|-------------|
| Short-form (Recommended for {awareness}) | Hero + light proof + CTA. Best for ready-to-buy visitors |
| Medium | All 7 sections at moderate depth. Good balance of persuasion and brevity |
| Full-length | All 7 sections at heavy depth. Maximum persuasion for evaluating visitors |
| Long-form | All 7 sections, extra education and proof. For visitors who need convincing |

Adjust the "(Recommended for {awareness})" label to match the recommended option.
Use AskUserQuestion with these 4 options. multiSelect: false.

#### Question 5: Specific Offer Details

**Question:** "Describe the specific offer for this landing page. What exactly will visitors get? Include pricing, deliverables, or any special terms."

This is a free-text question. Use AskUserQuestion with options like:
| Option | Description |
|--------|-------------|
| Use offer from context | Pull offer details from offer-angles.md and brand.md automatically |

If the user selects "Other", they provide free-text offer details.

#### Question 6: Urgency/Scarcity

**Question:** "Is there any urgency or scarcity element available for this offer?"

| Option | Description |
|--------|-------------|
| Time-limited | Offer expires on a specific date or within a timeframe |
| Limited quantity | Limited spots, inventory, or capacity |
| Progressive pricing | Price increases over time (early bird, regular, late) |
| None | No urgency element — Section 6 will be skipped |

Use AskUserQuestion with these 4 options. multiSelect: false.

#### Question 7: Top 3 Objections

**Question:** "What are the top 3 objections or concerns your visitors are likely to have? (These will be addressed in the FAQ section)"

This is a free-text question. Show vertical-specific examples to guide the user:

- **Lead Gen examples:** "Is this worth the cost?" "How long until I see results?" "What if it doesn't work?"
- **SaaS examples:** "Is it hard to set up?" "Does it integrate with my tools?" "What if my team doesn't adopt it?"
- **Ecommerce examples:** "Is the quality good enough?" "What if it doesn't fit/work?" "How fast is shipping?"

Use AskUserQuestion with options like:
| Option | Description |
|--------|-------------|
| Use common objections for {vertical} | Auto-generate typical objections for this vertical |

If the user selects "Other", they provide free-text objections.

#### Auto-Derivation (`--skip-discovery`)

When `--skip-discovery` is provided, derive settings from existing context:

1. **Awareness level:** Check `context/offer-angles.md` for traffic classification or awareness mentions. Default to Solution Aware if not found.
2. **Vertical:** Check `context/brand.md` for business type, industry. Infer Lead Gen / SaaS / Ecommerce.
3. **Conversion action:** Check `context/brand.md` for primary CTA. Infer conversion type.
4. **Page length:** Auto-recommend based on derived awareness level.
5. **Offer details:** Pull from `context/offer-angles.md` Value Proposition + Value Boosters sections.
6. **Urgency:** Default to None unless `context/offer-angles.md` mentions time limits or scarcity.
7. **Objections:** Use vertical defaults from `reference/section-patterns.md`.

Present derived settings to user for confirmation before proceeding.

---

### Phase 2: Brand Color Resolution

Resolve brand colors for the landing page CSS variables. Uses a priority chain: palette file → fallback defaults.

#### 2.1 Check for Palette File

Check if `context/brand-colours/palette.md` exists (generated by `/ads-context`).

**If palette file exists:** Read it and extract:
- **Primary** — from the "Suggested Colour Roles" table, role = Primary
- **Accent** — from the "Suggested Colour Roles" table, role = Accent
- **Background** — from the "Suggested Colour Roles" table, role = Background
- **Text** — from the "Suggested Colour Roles" table, role = Text
- **Heading Font** — from the Typography table, role = Headings
- **Body Font** — from the Typography table, role = Body

**If palette file does not exist:** Log that no palette was found, use defaults, and inform the user they can run `/ads-context` to extract brand colours.

#### 2.2 Map to CSS Variables

Map resolved values to the CSS variable system:

| Source (from palette) | Maps To | Fallback |
|-----------------------|---------|----------|
| Primary hex | `--color-primary` | `#1a1a2e` |
| Darker shade of primary | `--color-secondary` | `#16213e` |
| Accent hex | `--color-accent` | `#e94560` |
| Darken accent by ~10% | `--color-accent-hover` | Computed |
| Background hex | `--color-bg` | `#ffffff` |
| Slightly off-white | `--color-bg-alt` | `#f8f9fa` |
| Text hex | `--color-text` | `#333333` |
| Lighter shade of text | `--color-text-light` | `#666666` |
| White (or contrast color on accent) | `--color-text-on-accent` | `#ffffff` |
| Heading font | `--font-heading` | `system-ui, sans-serif` |
| Body font | `--font-body` | `system-ui, sans-serif` |

#### 2.3 Present Palette for Confirmation

Show the resolved colors to the user:

```markdown
## Brand Colors

| Variable | Value | Source |
|----------|-------|--------|
| Primary | {hex} | palette.md / default |
| Accent (CTA) | {hex} | palette.md / default |
| Background | {hex} | palette.md / default |
| Text | {hex} | palette.md / default |
| Heading Font | {font-family} | palette.md / default |
| Body Font | {font-family} | palette.md / default |

Does this look correct?
```

Use AskUserQuestion:
| Option | Description |
|--------|-------------|
| Yes, use these colors | Proceed with this palette |
| No, I'll provide colors | Enter hex codes manually |

#### 2.4 Fallback

If `context/brand-colours/palette.md` is missing or incomplete:
1. Check `context/brand.md` for any color or font mentions
2. If still no colors, use sensible defaults from `reference/html-template.md`
3. Inform the user: "No brand palette found. Run `/ads-context [URL]` to extract brand colours automatically. Using defaults — you can customize the `:root` CSS variables in the output file."

---

### Phase 3: Page Architecture

#### 3.1 Read Reference

Read `reference/awareness-and-hierarchy.md` to look up section emphasis levels.

#### 3.2 Select Section Emphasis

**If `AUDIT_ARCHITECTURE_CONTEXT` exists from Phase 0.5:** Use the audit's section quality data to adjust the standard emphasis table. Where the audit identifies a section as WARN or FAIL, increase emphasis by one level above the standard awareness-based level (e.g., Moderate → Heavy). Where the audit identifies a section as PASS, maintain the standard level. Ensure sections the audit flagged as missing (e.g., Urgency/Scarcity, Guarantee) are included regardless of awareness defaults.

**Apply `PEER_CONTEXT` bias from Phase 0.6 (informational, not gating):**

| Peer signal | Architecture bias |
|-------------|-------------------|
| `quality_score.lpe_findings` shows AR/LPE below average | Lead with **strong message-match hero** (full emphasis on hero + sub-headline keyword echo). Bump Hero emphasis to Full. |
| `competitive.competitor_positioning` shows competitors all lead with the same angle | Differentiate: choose a **different hero angle** from `offer.recommended_angles` than the competitor consensus. Note the chosen contrast in the architecture justification. |
| `offer.weakest_offer_dimensions` includes "trust" | Bump Trust/Authority + Social Proof one level higher than awareness default. |
| `offer.weakest_offer_dimensions` includes "urgency" | Force-include Urgency/Scarcity section even if Q6 said None — mark as "[Replace with real deadline/quantity]" placeholder. |
| `offer.weakest_offer_dimensions` includes "value" | Bump Benefits emphasis one level higher; include guarantee badge near every CTA. |
| `offer.guarantee_recommendation` is present | Include guarantee badge near hero CTA AND final CTA. |
| `bidding.strategy_posture` is tCPA/tROAS + `bidding.learning_state` is "learning" | Note in justification: page should be stable / not A/B tested for first 2 weeks (informational only — does not affect emphasis). |
| `tracking.status` is "dirty" | Note in justification only — recommend tracking validation before launch. Does not affect emphasis. |

When multiple peer signals conflict (e.g., audit says Trust=PASS but offer-audit says trust dimension is weak), prefer the **more specific** signal: offer-audit findings outrank generic awareness defaults; lp-audit findings outrank both for sections it explicitly scored.

Based on the awareness level from Phase 1 (or Phase 0.5 reduced discovery), determine emphasis for each section:

| Section | Emphasis Level |
|---------|---------------|
| 1. Hero | {Full/Full-problem/Full-offer based on awareness} |
| 2. Benefits | {Heavy/Moderate/Light based on awareness} |
| 3. Trust/Authority | {Heavy/Moderate/Light based on awareness} |
| 4. Social Proof | {Heavy/Moderate/Light based on awareness} |
| 5. Objection Handling | {Heavy/Moderate/Light/Minimal based on awareness} |
| 6. Urgency/Scarcity | {Strong/Moderate/Light/Skip based on Q6 answer} |
| 7. Call to Action | Repeated throughout |

**For Short-form pages:** Include Hero, light Social Proof, and CTA only.
**For Medium pages:** All 7 sections at moderate depth.
**For Full-length/Long-form:** All 7 sections at heavy depth.

#### 3.3 Select Copywriting Framework

Based on awareness level + vertical, select from:

| Awareness | Framework | Structure |
|-----------|-----------|-----------|
| Unaware | AIDA | Attention → Interest → Desire → Action |
| Problem Aware | PAS | Problem → Agitation → Solution |
| Solution Aware | AIDA or BAB | Before → After → Bridge |
| Product Aware | Hook-Story-Offer | Hook → Story → Offer |
| Most Aware | Direct Offer | Offer → Proof → CTA |

#### 3.4 Select Headline and CTA Types

Read `reference/headline-patterns.md` and `reference/cta-patterns.md`:

**Headline type by awareness:**
- Unaware → Question or Problem-agitation
- Problem Aware → Problem-agitation
- Solution Aware → How-to or Outcome
- Product Aware → Proof/statistic or Outcome
- Most Aware → Direct offer

**CTA type by awareness:**
- Unaware / Problem Aware → Low-commitment
- Solution Aware → Value-first
- Product Aware → Action-driven or Value-first
- Most Aware → Urgency-based or Action-driven

#### 3.5 Present Page Outline for Approval

Present the architecture to the user:

```markdown
## Page Architecture

**Awareness Level:** {level}
**Vertical:** {vertical}
**Page Length:** {length}
**Copywriting Framework:** {framework}
**Headline Type:** {type} — {formula}
**CTA Type:** {type} — {formula}

### Section Outline

| # | Section | Emphasis | Key Content |
|---|---------|----------|-------------|
| 1 | Hero | Full | {Headline type}, {CTA type}, {visual approach} |
| 2 | Benefits | {emphasis} | {benefit angle approach} |
| 3 | Trust/Authority | {emphasis} | {trust type for vertical} |
| 4 | Social Proof | {emphasis} | {proof types to include} |
| 5 | Objection Handling | {emphasis} | FAQ addressing {top 3 objections} |
| 6 | Urgency/Scarcity | {emphasis or Skip} | {urgency type from Q6} |
| 7 | Final CTA | Full | Value recap + strongest CTA |

**If audit-informed build:** Add an "Audit Justification" column to the table showing why each emphasis level was chosen. Example: "D02 WARN: H1 feature-focused → full rewrite" or "D06 PASS: trust signals strong → preserve".

**If `PEER_CONTEXT` applied any bias:** Add a "Peer Bias" column to the table showing which peer signal shifted emphasis. Example: "offer-audit: trust dimension weak → +1 emphasis" or "competitive-audit: 4/5 competitors lead with speed → differentiate via authority angle".

Shall I proceed with this structure?
```

Use AskUserQuestion:
| Option | Description |
|--------|-------------|
| Yes, proceed | Generate copy with this architecture |
| Adjust sections | Make changes to emphasis or section order |

---

### Phase 4: Copy Generation

#### 4.1 Read References

Read:
- `reference/headline-patterns.md`
- `reference/cta-patterns.md`
- `reference/section-patterns.md`
- `context/offer-angles.md`
- `context/brand.md`

#### 4.2 Write Copy Section by Section

**Apply `PEER_CONTEXT` bias from Phase 0.6 to copy generation (informational, not gating):**

The peer-context buffer biases copy choices in priority order. When peer signals conflict with `AUDIT_COPY_SEEDS` (LP audit-back signal), the LP audit wins — it scored the actual page. When peer signals conflict with each other, the more specific signal wins (offer-audit > generic awareness defaults; search-term-audit > generic vertical patterns).

| Peer signal | Copy element biased | How |
|-------------|---------------------|-----|
| `search_terms.top_converting_ngrams` | **H1, hero sub-headline, body copy** | Use the actual user search language verbatim where natural. Top converting n-grams beat top volume n-grams. If the n-gram is a literal phrase (e.g., "marketing automation for agencies"), echo it in H1. |
| `offer.recommended_angles` | **Hero offer, CTA microcopy, final CTA** | Lead the hero with the #1 recommended angle. Use the #2 angle as sub-headline support or final CTA value recap. |
| `offer.guarantee_recommendation` | **Guarantee statement, hero microcopy, near-CTA badge** | Use offer-audit's recommended guarantee text verbatim near every CTA. |
| `keywords.themes_per_ad_group` | **H1 (when LP serves a specific AG)** | If the LP is dedicated to one ad group, mirror that AG's keyword theme in H1 (message match). If the LP serves multiple AGs, choose the dominant theme. |
| `keywords.primary_match_keywords` | **Hero sub-headline, benefits H2s** | Naturally weave 2-3 of the primary keywords into sub-headline + benefit titles. Don't keyword-stuff. |
| `competitive.competitor_positioning` | **Hero angle selection, differentiation copy** | If competitors all lead with one angle (e.g., speed), do NOT lead with the same. Choose a contrasting angle from `offer.recommended_angles`. Add a "differentiation" line in benefits/objections section that names what we do differently (without naming competitors). |
| `competitive.differentiation_gaps` | **Hero sub-headline, benefits, FAQ** | If there's an angle no competitor owns and our offer supports it, claim it explicitly in sub-headline or as a top benefit. |
| `quality_score.lpe_findings` + `quality_score.target_ad_groups` | **H1 + sub-headline** | If LPE is the limiting QS component on the target AG, force tight ad-text-to-H1 message match. Pull the best-performing ad headline from `context/google-ads/data/ads.csv` for that AG and mirror its structure in H1. |
| `quality_score.ar_findings` | **H1 specificity** | If AR is below average, the H1 must be highly specific to the search intent — avoid generic "the best [category]" headlines. |
| `strategy.break_even_cvr` | **CVR framing in Summary phase only** | Surface the break-even CVR in the Summary as context for the wireframe's CVR target. Do NOT bake target CPA/ROAS numbers into the LP copy itself (the LP is target-agnostic). |
| `strategy.posture` | **CTA aggressiveness** | aggressive → action-driven CTA ("Get my audit now"); efficient → value-first CTA ("See your savings"); balanced → as awareness default. |
| `tracking.status = dirty` | **Summary phase warning only** | Add a "verify tracking before launch" note in the handoff. Does NOT change copy. |

**If `AUDIT_COPY_SEEDS` exists from Phase 0.5:** Use the optimizer's recommended copy as starting points instead of generating from scratch:
- **Hero headline:** Present the optimizer's recommended H1 as the primary option. Generate 1-2 alternatives in the same style. Present all for user selection.
- **Hero CTA:** Use the optimizer's recommended CTA text as default. Generate 1 alternative.
- **Benefits:** Seed with the optimizer's outcome-focused rewrites. Apply the three-angles methodology on top.
- **Guarantee:** Use the optimizer's recommended badge text verbatim.
- **Urgency:** Use the optimizer's recommended urgency text as starting point.
- **Social Proof:** Mark placeholders with the specific gaps from audit D07 (e.g., "[Replace with real testimonial: Full name, PHOTO REQUIRED, job title + company REQUIRED, specific result with number REQUIRED]").
- **FAQ/Objections:** Adapt items that scored PASS in audit D08 rather than generating from scratch.
- **Trust signals:** Preserve strong signals identified in audit D06 (e.g., "1M+ installs", "800+ reviews").
- Annotate copy with source: *(from optimize report P2 Fix #N)* where applicable.

Using the selected headline formula, CTA formula, section patterns, and offer angles, write copy for each included section:

**Section 1: Hero**
- Primary headline using selected headline type formula
- Sub-headline adding specificity (mechanism or proof)
- CTA button text using selected CTA type formula
- Microcopy (risk removal, social proof, or speed/ease)
- Visual placeholder description based on vertical

**Section 2: Benefits**
- Section headline
- 3-6 benefits using the three angles (functional, business, personal)
- Use phrases from offer-angles.md USP and Value Proposition sections
- Display as benefit cards (icon placeholder + headline + description)

**Section 3: Trust/Authority**
- Section headline
- Trust elements appropriate for the vertical
- Pull from offer-angles.md Social Proof section for credentials
- Placeholder badges where real assets needed

**Section 4: Social Proof**
- Section headline
- 2-3 testimonials using the testimonial formula (specific result + before + after)
- Mark all testimonials as placeholders: "[Replace with real testimonial: Full name, photo, company, specific result]"
- Pull language from offer-angles.md Social Proof section

**Section 5: Objection Handling**
- Section headline ("Frequently Asked Questions" or similar)
- FAQ items addressing the top 3 objections from Phase 1
- Guarantee statement using offer-angles.md Risk Removal section
- CTA after guarantee

**Section 6: Urgency/Scarcity (if not skipped)**
- Based on urgency type from Q6
- Placeholder for specific deadline/quantity: "[Replace with real deadline]"
- Explanation of why the limitation exists
- CTA

**Section 7: Final CTA**
- Value recap headline
- 3-5 bullet summary of key value points
- Strongest CTA version (same text, largest styling)
- Final microcopy

#### 4.3 Copy Guidelines

- Use exact phrases from `context/offer-angles.md` where they fit naturally
- Match the brand voice and tone from `context/brand.md`
- Active voice throughout, no hedging
- Visitor-first language (their reality, not your company)
- Specific numbers and results where available
- First-person CTA text ("Get my..." not "Get your...")
- Mark anything that needs real content with `[Replace with...]`

#### 4.4 Present Copy for Approval

Present the full copy draft organized by section:

```markdown
## Copy Draft

### Hero
**Headline:** {headline}
**Sub-headline:** {sub-headline}
**CTA:** {button text}
**Microcopy:** {microcopy}
**Visual:** [{placeholder description}]

### Benefits
**Section headline:** {headline}
1. **{Benefit 1 title}** — {description}
2. **{Benefit 2 title}** — {description}
3. **{Benefit 3 title}** — {description}

### Trust/Authority
{trust content}

### Social Proof
{testimonial placeholders}

### Objection Handling
{FAQ items + guarantee}

### Urgency (if applicable)
{urgency copy}

### Final CTA
{value recap + CTA}

---
Ready to generate the HTML?
```

Use AskUserQuestion:
| Option | Description |
|--------|-------------|
| Yes, generate HTML | Proceed to HTML generation |
| Revise copy | Make changes before generating |

---

### Phase 5: HTML Generation

#### 5.1 Read HTML Template

Read `reference/html-template.md` for the base HTML structure, CSS variables, and section snippets.

#### 5.2 Build HTML

1. Start with the base HTML structure from the template
2. Populate `:root` CSS variables with colors from Phase 2
3. Generate each section using the approved copy from Phase 4 and the section snippets from the template
4. Apply section emphasis: skip sections marked as "Skip", use lighter content for "Light" emphasis
5. Use the `.placeholder` class for all image/badge placeholders
6. Ensure CTA buttons appear in at least 5 locations (hero, after benefits, after social proof, after objections, final section)
7. Alternate section backgrounds via the `section:nth-child(even)` CSS rule

**Apply `PEER_CONTEXT` bias to trust signal / proof placements:**

| Peer signal | HTML element bias |
|-------------|-------------------|
| `offer.weakest_offer_dimensions` includes "trust" | Add a trust-strip row directly under the hero (logos, badges, ratings placeholders) — not just in the dedicated Trust section. |
| `offer.guarantee_recommendation` is present | Render a guarantee badge component inline next to every CTA button, not just in the dedicated guarantee section. |
| `competitive.differentiation_gaps` is non-empty | Add a "What makes us different" sub-block within Benefits — render as a callout box (border-left accent) rather than a benefit card. |
| `quality_score.lpe_findings` shows LPE issues on target AGs | Above-the-fold layout must include H1 + sub-headline + CTA + microcopy + trust-strip — all visible without scrolling on a 1024×768 viewport. Document this constraint as a comment in the HTML head. |

#### 5.3 Output Rules

- Self-contained: all CSS in `<style>`, no external dependencies
- No navigation bar, no footer links (one-page-one-goal)
- No JavaScript (smooth scroll handled by CSS `scroll-behavior: smooth`)
- Responsive: single breakpoint at 768px, grids collapse, CTAs go full-width
- All placeholder images/content use dashed-border boxes with descriptive text
- CTA button text is consistent across all placements

#### 5.4 Save File

Create output directory if needed:

```bash
mkdir -p created/landing-pages
```

Save the HTML file:
- **Filename:** `{YYYYMMDD}_{company}_{offer-type}.html`
- **Company:** From `context/brand.md`, sanitized (lowercase, hyphens, no special chars)
- **Offer type:** From the conversion action or offer description (e.g., "free-audit", "free-trial", "product-page")

---

### Phase 6: Quality Validation

#### 6.1 Read Checklist

Read `reference/quality-checklist.md`.

#### 6.2 Validate Against All 12 Categories

Check the generated HTML file against every item in the checklist. For each category, count passing and failing items.

**Wireframe adaptations:**
- Skip "Page loads in under 3 seconds" (not applicable to wireframe)
- Skip "Conversion tracking fires correctly" (not applicable to wireframe)
- Skip "Form submits correctly" (no real form in wireframe)
- Check layout, section order, copy quality, CTA placement, brand colors, responsiveness

#### 6.3 Present Results

```markdown
## Quality Validation Results

| Category | Pass | Fail | Score |
|----------|------|------|-------|
| Offer Completeness | X/6 | Y/6 | Z% |
| Hero Section | X/8 | Y/8 | Z% |
| Benefits | X/4 | Y/4 | Z% |
| Trust/Authority | X/4 | Y/4 | Z% |
| Social Proof | X/4 | Y/4 | Z% |
| Objection Handling | X/4 | Y/4 | Z% |
| Urgency/Scarcity | X/4 | Y/4 | Z% |
| Call to Action | X/5 | Y/5 | Z% |
| Copy Quality | X/5 | Y/5 | Z% |
| One-Page-One-Goal | X/5 | Y/5 | Z% |
| Visual & Layout | X/9 | Y/9 | Z% |
| Brand & Message Match | X/5 | Y/5 | Z% |
| **Total** | **X/N** | **Y/N** | **Z%** |

### Action Items
1. {failing item} → {how to fix}
2. ...
```

If any items fail, fix them in the HTML file before proceeding.

---

### Phase 7: Summary & Handoff

Present the final summary:

```markdown
## Landing Page Wireframe Complete

### Output
- **File:** `created/landing-pages/{filename}.html`
- **Open in browser to preview**

### Page Structure
| Section | Emphasis | Status |
|---------|----------|--------|
| Hero | {level} | Complete |
| Benefits | {level} | Complete |
| Trust/Authority | {level} | Complete |
| Social Proof | {level} | Complete (placeholders) |
| Objection Handling | {level} | Complete |
| Urgency/Scarcity | {level or Skipped} | Complete |
| Final CTA | Full | Complete |

### Brand Match
- **Colors:** {primary}, {accent}, {background}
- **Fonts:** {heading font}, {body font}
- **Source:** {palette.md / manual / defaults}

### Quality Score: {X}%

### Placeholders to Replace
- [ ] {list of all [Replace with...] items in the file}

### Audit Integration (if applicable)
- **Informed by:** {lp-audit.md ({date}, {score}%) | lp-optimize-{action}.md ({date}) | N/A}
- **Original page:** {URL from audit | N/A}
- **Compare after live:** Run `/lp-audit` on the new LP and compare against the original score ({original_score}%)

### Cross-skill context applied (Mode 2 — informational)

List every peer signal that shaped the output. Skip rows where the corresponding peer report was missing/stale.

| Peer signal | Status | Shaped which output |
|-------------|--------|--------------------|
| /offer-auditor | Fresh ({N}d) | Hero angle: "{chosen angle}" — used #1 recommended angle. Guarantee badge: "{text}" — verbatim from offer-audit. |
| /search-term-auditor | Fresh ({N}d) | H1: incorporated n-gram "{n-gram}". Sub-headline: incorporated n-gram "{n-gram}". |
| /competitive-analyst | Fresh ({N}d) | Differentiation: avoided "{competitor consensus angle}" — chose contrasting "{our angle}". Added differentiation callout in Benefits. |
| /quality-score-auditor | Fresh ({N}d) | Hero emphasis bumped to Full (LPE on AGs: {AG list}). Above-fold layout enforced. |
| /keyword-auditor | Fresh ({N}d) | H1 mirrors theme of "{AG name}". Primary keywords woven into sub-headline + benefits. |
| /strategy-specialist | Fresh ({N}d) | CTA aggressiveness: {chosen} (posture: {posture}). Break-even CVR context: {X%}. |
| /bidding-auditor | Fresh ({N}d) | Stability note: {posture/learning state} — page should not be A/B tested for first 2 weeks. |
| /budget-auditor | Fresh ({N}d) | Context only — no copy/layout changes. |
| /tracking-specialist | {Fresh/Dirty} | Informational warning surfaced in handoff. No copy changes. |
| /account-auditor | Fresh ({N}d) | Context only — no copy/layout changes. |

**Stale or missing peers (not applied):**
- {peer}: {reason} — peer signal not used.

**Header-date contradictions flagged:**
- {peer}: {description} — flagged for user, not auto-resolved.

**Informational warnings carried forward:**
- {e.g., "Tracking audit missing — verify conversion tracking before launch (M-bucket dirty)"}
- {e.g., "Strategy audit stale (45d) — break-even CVR not peer-validated (B-bucket dirty)"}

### Client Handoff Notes
1. **Review wireframe** in browser (desktop + mobile views)
2. **Replace placeholders** with real testimonials, images, badges
3. **Verify message match** with the ads that will drive traffic
4. **Implement** in your landing page builder (Unbounce, Instapage, WordPress, etc.)
5. **After live:** Run `/quality-score-auditor components` to validate Landing Page Experience in Google Ads

### Suggested Next Steps
1. Review wireframe with client → gather feedback
2. Collect real assets (testimonials, product images, trust badges)
3. Implement in landing page builder
4. Set up conversion tracking
5. Launch and monitor for 48 hours
6. Run `/lp-audit` to score the live page across all 6 modules
7. Run `/lp-optimize` for targeted fix guidance on any issues found
```

---

## Error Handling

| Error | Message |
|-------|---------|
| Missing `context/brand.md` | "Run `/ads-context [URL]` first to gather brand context" |
| Missing `context/offer-angles.md` | "Run `/offer-maker angles` first to extract offer message angles" |
| `context/brand-colours/palette.md` missing | "No brand palette found. Run `/ads-context [URL]` to extract brand colours. Using defaults — customize `:root` CSS variables in the output file" |
| Palette file incomplete (missing roles) | "Palette file found but some colour roles are missing. Using defaults for missing values" |

---

## Integration Points

### Uses (reads from):
- `context/brand.md` — Brand voice, tone, homepage URL, company name
- `context/offer-angles.md` — 6 message angles with headline-ready phrases
- `context/brand-colours/palette.md` (optional) — Brand colours and fonts extracted by `/ads-context`
- `context/business.md` (optional) — Business goals, constraints
- `context/google-ads/data/keywords.csv` (optional) — Primary keywords for message match
- `context/google-ads/data/ads.csv` (optional) — Existing ad copy for message match
- `context/analysis/lp-audit.md` (optional) — Prior audit findings for audit-informed builds (Phase 0.5)
- `context/analysis/lp-optimize-*.md` (optional) — Prior optimization recommendations with specific copy rewrites (Phase 0.5)
- `context/analysis/quality-score-audit.md` (optional, ≤7d) — LPE/AR findings → hero design + copy alignment (Phase 0.6)
- `context/analysis/search-term-audit.md` (optional, ≤7d) — Top n-grams → H1/hero copy (Phase 0.6)
- `context/analysis/keyword-audit.md` (optional, ≤7d) — Per-AG themes → keyword-matched copy (Phase 0.6)
- `context/analysis/budget-audit.md` (optional, ≤7d) — Budget context (Phase 0.6, informational)
- `context/analysis/bidding-audit.md` (optional, ≤7d) — Bid posture → CTA aggressiveness (Phase 0.6)
- `context/analysis/competitive-audit.md` (optional, ≤14d) — Differentiation positioning (Phase 0.6)
- `context/analysis/offer-audit.md` (optional, ≤30d) — Offer angles → hero/CTA (Phase 0.6, highest leverage)
- `context/analysis/tracking-audit.md` (optional, ≤30d) — Informational warning if dirty (Phase 0.6)
- `context/analysis/strategy-audit.md` (optional, ≤30d) — Break-even/posture context for CVR framing (Phase 0.6)
- `context/analysis/account-audit.md` (optional, ≤30d) — Account-level structure context (Phase 0.6)
- `reference/awareness-and-hierarchy.md` — Awareness stages, section hierarchy, emphasis tables
- `reference/section-patterns.md` — Content patterns per section per vertical
- `reference/headline-patterns.md` — 6 headline types with formulas
- `reference/cta-patterns.md` — 5 CTA types with formulas
- `reference/quality-checklist.md` — 12-category validation checklist
- `reference/html-template.md` — CSS variables, section snippets, responsive rules

### Produces (writes to):
- `created/landing-pages/{YYYYMMDD}_{company}_{offer-type}.html` — Self-contained HTML wireframe

### Downstream:
- Client review and feedback
- Implementation in landing page builder
- `/quality-score-auditor components` validation on the live version (LP Experience module)

---

## Output Location

All files are created relative to the **current working directory**:
- Output directory: `created/landing-pages/`
- Creates directory if it doesn't exist
- Each run creates a new date-stamped file (never overwrites)
