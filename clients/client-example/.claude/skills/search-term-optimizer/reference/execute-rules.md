# Execute Rules — Search Term Optimizer

Authoritative rules for generating operations from auditor findings. Every action maps to one or more of the 5 mutation primitives.

## Mutation primitives

| Primitive | Google Ads API entity | Used by |
|-----------|----------------------|---------|
| `create_keyword` | `ad_group_criterion.create` (positive) | ST-E03 |
| `create_negative` | `shared_criterion.create` (default), `campaign_criterion.create` (fallback), or `ad_group_criterion.create` (negative=true) | E01, E02, E05, E06, E07, E10 |
| `remove_negative` | `shared_criterion.remove`, `campaign_criterion.remove`, or `ad_group_criterion.remove` | E04, E05, E06 |
| `create_shared_set` | `shared_set.create` + `campaign_shared_set.create` (attach to active Search + PMax campaigns) | E02 bootstrap, E07, pre-flight auto-create |
| `brand_exclusion` | `campaign_criterion.create` (brand_list criterion) | E09 |

## Shared-list default policy

For E01, E02, E05, E06, E07, E10 — **shared list is the default destination**:

1. **Pre-flight — list exists?** Look up the target list name in `config.searchTermAnalysis.sharedNegativeLists`. Verify it exists via `negative-keywords-shared.csv`. If not, prepend a `create_shared_set` primitive + attachments to all active Search + PMax campaigns. Tag these ops with `meta.action_id='PREFLIGHT'`.
2. **Pre-flight — link coverage?** Every active Search + PMax campaign must be linked to the relevant list. Read `negative-keywords-shared-links.csv`. Missing links → prepend `campaign_shared_set.create` primitives.
3. **Campaign-level negatives only when justified.** Emit a campaign-level `campaign_criterion` create only if the finding is genuinely campaign-specific (brand carve-out, single-campaign experiment). Document the reason in `meta.rationale`.
4. **Ad-group level negatives are rare** and only used when consolidation (E05) is running *into* an ad-group (never *from* ad-group back up).

## Action detail

### ST-E01 — Negate irrelevant search terms

**Source:** `search-term-flags.json → quality.irrelevantTerms[]` confirmed by Claude (user explicitly acknowledged as irrelevant in the audit).
**Primitive:** `create_negative` on the `Negative Keywords — Irrelevant` shared list.
**Match type:** Phrase (default, from `config.searchTermAnalysis.negativeMatchType`). Exact only if the term is unambiguous and short.
**Scope:** Shared list → auto-attached to Search + PMax.
**Fallback:** Campaign-level if the irrelevance is scoped to one campaign (rare; requires rationale).

### ST-E02 — N-gram exclusion cycle

**Source:** `negative-flags.json → ngrams.nonConverting[]` and `ngrams.inefficient[]` confirmed by Claude (user did not reject them).
**Primitive:** `create_negative` on the appropriate canonical list:
- ST-D13 findings → `Negative N-grams — Non-Converting`
- ST-D14 findings → `Negative N-grams — Inefficient`
**Match type:** Phrase only. Never Exact — n-grams describe patterns, not specific queries.
**Pre-flight:** Both lists exist and are attached to all Search + PMax campaigns. If either list is missing, bootstrap via `create_shared_set`.

### ST-E03 — Promote high-performing terms

**Source:** `search-term-flags.json → promotion.candidates[]`.
**Primitive:** `create_keyword` (ad_group_criterion, positive).

**Match-type resolution (the critical rule):**

1. Find the target ad group. Read the existing keyword match-type mix in that ad group from `keywords.csv`:
   - Exact-only → promote as **Exact**
   - Exact + Phrase → promote as **Phrase**
   - Broad-heavy (≥ 50% broad) → promote as **Broad**
   - Empty ad group → default to **Exact**
2. Resolve the campaign's bidding strategy via `resolveBiddingStrategy` (reuse from `search-term-auditor/scripts/lib.js`). Portfolio attachments honored.
3. **Never auto-apply Broad-on-Smart-Bidding.** If the campaign is on TARGET_CPA / TARGET_ROAS / MAXIMIZE_CONVERSIONS / MAXIMIZE_CONVERSION_VALUE and the ad group doesn't already have broad, surface a report nudge:
   > "Consider a 50/50 split campaign experiment with broad on smart bidding for {N} candidates."
   Do **not** emit the broad-on-smart-bidding operations in this run.

### ST-E04 — Resolve negative conflicts

**Source:** `negative-flags.json → coverage.negativeConflicts[]`.
**Primitive:** `remove_negative`.
**Logic:** Remove the negative that blocks an active keyword. Never remove the positive keyword. If the conflict is at both ad-group and campaign scope, remove in the narrowest first, then re-evaluate.

### ST-E05 — Consolidate ad-group negatives → shared list

**Source:** `negative-flags.json → coverage.repeatedAdGroupNegatives[]` (≥ 3 ad groups in same campaign).
**Primitives:** `create_negative` (shared list) + `remove_negative` (ad-group level).
**Rule:** Create at shared list first, then remove at ad group — never the reverse. Match type preserved (Phrase → Phrase, Exact → Exact).
**Fallback:** Campaign-level if the repeat is within a single campaign and a shared list would affect too many other campaigns.

### ST-E06 — Consolidate campaign negatives → shared list

**Source:** `negative-flags.json → coverage.repeatedCampaignNegatives[]` (≥ 3 campaigns).
**Primitives:** `create_negative` (shared list) + `remove_negative` (campaign level).
**Rule:** Create before remove. Match type preserved.

### ST-E07 — Catalog-validated negative proposal

**Source:** Claude-generated from the Negative Keyword Catalog SOP + vertical context in business.md.
**Primitives:** `create_shared_set` (if missing) + `create_negative`.
**Propose-only workflow:**
1. Pull 365d search-terms.csv via `pull-all.js --pull-catalog --catalog-period=365`.
2. For each catalog candidate (e.g. `free`, `diy`, competitor names, informational patterns):
   - Check `search-terms-catalog.csv` for actual performance in the last 365d.
   - Reject the candidate if any query containing it:
     - Converted at or above the resolved target, or
     - Generated meaningful conversion value, or
     - Is explicitly in `config.searchTermAnalysis.protectedTerms.neverExclude`.
3. Present survivors to the user. User reviews and approves per candidate.
4. Only approved candidates become operations.
**Match type:** Phrase by default. Exact for unambiguous competitor names.

### ST-E09 — PMax brand defense

**Source:** `search-term-flags.json → pmaxAnalysis.brandQueryPct` (≥ threshold) or explicit user request.
**Primitive:** `brand_exclusion` via `campaign_criterion.create` with a brand list criterion.
**Pre-flight:** Check if the PMax campaign already has a brand list attached. Do not duplicate.

### ST-E10 — Negate foreign language queries

**Source:** ST-D04 findings confirmed by Claude.
**Primitive:** `create_negative` on `Negative Keywords — Foreign Language` shared list.
**Match type:** Exact — foreign queries are specific. Do not use Phrase (avoid over-exclusion of cognate English words).

## Cross-op resource references (temp negative IDs)

`mutate.js` sends all ops in a single `mutateResources` call — no response chaining, no string-placeholder substitution. Whenever an op must reference a resource *created in the same batch* (e.g. attaching a new shared set, or adding criteria to it), use Google Ads' **temporary negative-ID** convention:

- `shared_set` create gets `fields.resource_name = "customers/{customerId}/sharedSets/-1"`.
- Every dependent op in the same batch references that exact temp string.
- Use distinct negatives (`-1`, `-2`, …) when creating multiple new entities.

Apply this to E02 bootstrap (new n-gram lists), E07 (catalog list bootstrap), and E10 (foreign-language list bootstrap) whenever the target list is not yet in `negative-keywords-shared.csv`. Existing lists always use their real resource name from that CSV.

**Never emit string placeholders** like `{{NEW_LIST_RN}}` — the API rejects them as malformed resource names and the dry-run validation will fail before any ops run.

## Safety constraints

- `--max-ops=100` default cap. Abort if exceeded unless the user explicitly raises.
- `validate_only=true` on every dry-run.
- Never emit a negative for a term in `config.searchTermAnalysis.protectedTerms.neverExclude`.
- Never emit a positive keyword for a term that's already in an ad-group keyword set (`already_keyword=true` in the source record).
- Status changes only allowed for removed negatives — never PAUSED (negatives are removed, not paused).
- Portfolio bid strategies are handled upstream by the auditor's `resolveBiddingStrategy`; the optimizer only reads the resolved `target_source` for E03 match-type heuristics. No portfolio mutation capability here (that belongs to `/strategy-specialist`).

## Operation meta schema

Every operation object must include:

```json
{
  "type": "create" | "remove",
  "resource": "shared_set" | "shared_criterion" | "campaign_criterion" | "ad_group_criterion" | "campaign_shared_set",
  "fields": { ... },                    // For creates
  "resource_name": "customers/.../...",  // For removes
  "meta": {
    "action_id": "ST-E01" | "ST-E02" | ... | "PREFLIGHT",
    "category": "negate" | "ngram" | "promote" | "conflict" | "consolidate" | "catalog" | "brand" | "foreign",
    "target": "<search term | keyword | campaign name>",
    "term": "<text>",
    "match_type": "EXACT" | "PHRASE" | "BROAD",
    "scope": "shared_list:<name>" | "campaign:<name>" | "ad_group:<name>",
    "campaign": "<name>",
    "ad_group": "<name>",       // if scoped to an ad group
    "rationale": "<one-sentence reason>",
    "source_diagnostic": "ST-D02" | "ST-D13" | ...
  }
}
```

The `meta.action_id` determines the sort order and the dry-run table grouping.
