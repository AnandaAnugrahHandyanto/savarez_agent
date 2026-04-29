---
name: clinical-trial-competitive-intel
description: Use whenever the user asks for clinical-trial competitive intelligence, competitor analysis, pipeline landscape, target/MoA landscape, CDE/ClinicalTrials.gov/ChiCTR/CTIS trial lookup, China/global trial comparison, or asks to merge registry exports into a competitive-intelligence workbook. This skill is mandatory for pharma/biotech competitor analysis tasks, especially when the user mentions assets, indications, targets, clinical phases, CDE, CTR/NCT IDs, or Excel deliverables. It prevents the common failure of returning only the target asset's own trials without true competitor data.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [clinical-trials, competitive-intelligence, pharma, pipeline, CDE, ClinicalTrials.gov, Excel, medical-affairs]
    related_skills: [ocr-and-documents]
---

# Clinical Trial Competitive Intelligence

## Purpose

Turn public clinical-trial and company-disclosure data into a source-backed competitive-intelligence deliverable for clinical strategy, statistics, medical affairs, and business teams.

The deliverable should answer:

- Who is developing what asset?
- Against which target/MoA or pathway?
- For which indication and patient population?
- In which geography?
- At what clinical stage and recruitment status?
- What changed recently?
- Why does it matter competitively?

Do not produce a raw registry dump. Do not produce a target-asset-only excerpt and call it competitive intelligence.

## Control-System Frame

Use this operating loop, matching the user's preferred engineering-control framing:

1. Objective: define the decision question and scope.
2. State observation: collect global and China trial/regulatory/public-disclosure evidence.
3. State estimation: normalize assets, companies, indications, phases, statuses, and geographies.
4. Control action: synthesize competitor ranking, gaps, risks, and milestones.
5. Feedback: verify workbook completeness, source coverage, and failure modes before final response.

## Required Skill References

Load only the reference needed for the task:

- `references/competitor-discovery.md`: how to identify true competitors beyond the target asset.
- `references/source-workflows.md`: ClinicalTrials.gov, PubMed, CDE, ChiCTR, CTIS/EUCTR, company-disclosure collection workflows.
- `references/excel-schema-and-qc.md`: workbook schema, bilingual sheet requirements, openpyxl formatting, validation gates.
- `references/cde-normal-chrome.md`: macOS normal Chrome / Apple Events workflow for CDE, and merging saved CDE exports.

## When to Use

Use this skill for requests like:

- “帮我做某资产/靶点/适应症的竞品分析。”
- “查一下这个药在 CDE / ClinicalTrials.gov 上的临床试验。”
- “整理 COPD / EGFR / GLP-1 / ADC 等方向国内外竞品格局。”
- “把 CDE 查询结果合并进竞品分析 Excel。”
- “做一个医学部能看的竞品临床试验表。”
- “追踪最近 90 天竞品临床动态。”

Do not use it for medical advice or unsupported efficacy/safety conclusions.

## Default Scope

If the user does not specify scope, default to:

```yaml
geography_scope: global_and_china
trial_phase_scope: all interventional drug/biologic trials
status_scope:
  - not_yet_recruiting
  - recruiting
  - enrolling_by_invitation
  - active_not_recruiting
  - completed
lookback_days: 90
output_format: Excel workbook plus concise markdown/terminal brief
language: Chinese first, English sheets also required
```

Ask clarification only when the ambiguity changes the data sources or output meaning. Otherwise act.

## Non-Negotiable Deliverables

For a full competitive-intelligence task, output a single `.xlsx` workbook plus a concise brief. Markdown-only is incomplete.

The workbook must contain Chinese-first and English versions of core sheets:

1. `README`
2. `asset_summary_中文`
3. `trial_records_中文`
4. `competitor_comparison_中文`
5. `competitor_trials_中文`
6. `recent_changes_中文` if monitoring or lookback requested
7. `source_log_中文`
8. `search_dictionary_中文`
9. `dedup_log_中文` if cross-source linking/deduplication was done
10. corresponding `_EN` sheets

For CDE imports, also include:

- `CDE_trials_中文`
- `CDE_trials_EN`

Place the output in:

```text
~/Desktop/<project_name>_<YYYYMMDD>/<project_name>.xlsx
```

Use `openpyxl` formatting: blue header row with white text, frozen header row, borders, wrapped text, sensible column widths, status/severity color coding, and yellow highlight for the user's own asset.

## First 10 Minutes Protocol

1. Parse the user's stated asset, target/MoA, indication, sponsor, geography, and expected output.
2. Create a search dictionary before querying:
   - asset names/codes/generic/brand names
   - sponsor and subsidiaries
   - target/MoA and pathway terms
   - indication aliases in English and Chinese
   - known competitor assets and companies
3. Run pre-flight checks before ClinicalTrials.gov calls:
   - inspect proxy variables
   - test direct `curl --noproxy '*' https://clinicaltrials.gov/`
4. Query the target asset, but immediately query competitors too.
5. Save raw source outputs before normalization.
6. Build workbook incrementally, not at the end only.
7. Update `source_log` for every source attempted, including blocked/unavailable sources.
8. Verify the workbook before final response.

## Competitor Coverage Rule

A competitive-intelligence workbook is failed if it only contains the user's target asset.

After collecting the target asset, always collect at least one of the following competitor sets unless demonstrably none exist:

- same target/MoA assets
- same pathway assets
- same indication + same treatment line assets
- reference product and biosimilars, for biosimilar tasks
- company-disclosed direct competitors
- region-specific competitors in China, US, EU, or Japan as relevant

For example, for anti-ST2 COPD work, do not stop at 9MW1911. Also query astegolimab and IL-33 pathway competitors such as itepekimab and tozorakimab.

Document the competitor search terms in `search_dictionary` and `source_log`.

See `references/competitor-discovery.md` for the detailed competitor-discovery playbook.

## Source Priority

Use structured sources first:

1. ClinicalTrials.gov API v2 for global registry records.
2. PubMed / MEDLINE for published results, trial IDs, lead authors, PI clues.
3. China public sources: CDE / China drug clinical trial registration platform, ChiCTR, NMPA/CDE announcements.
4. EU CTIS / EUCTR for EU records.
5. Company press releases, investor decks, annual/interim reports, exchange filings.
6. User-provided exports from permitted commercial tools.
7. Dynamic scraping only when allowed and necessary.

Do not bypass paywalls, login, CAPTCHA, verification, or access controls. For CDE, prefer compliant normal Chrome workflow when automation-controlled browsers are blocked.

## Collection Requirements

For each trial-level record, capture where available:

- source and source URL
- retrieval date
- source trial ID: NCT / CTR / ChiCTR / EUCT / CTIS ID
- company/sponsor/applicant and role
- asset raw and canonical name
- target/MoA and modality
- indication and patient population
- phase raw and normalized phase
- status raw and normalized status
- title and official title
- arms/interventions
- primary and secondary endpoints
- enrollment
- dates: start, primary completion, completion, last update
- country/region and China flag
- PI names and affiliations if available
- notes and confidence

Keep raw and normalized fields. Do not overwrite raw registry language.

## Normalization Rules

Normalize but do not erase uncertainty.

- Company: parent, subsidiary, Chinese name, English name, historical name, license partner.
- Asset: generic, brand, code, Chinese transliteration, combination components.
- Indication: canonical English term plus Chinese alias; preserve line of therapy and biomarker subgroup.
- Phase: map Early Phase 1 / Phase 1 / Phase 1-2 / Phase 2 / Phase 2-3 / Phase 3 into standard labels.
- Status: map to `not_yet_recruiting`, `recruiting`, `enrolling_by_invitation`, `active_not_recruiting`, `completed`, `suspended`, `terminated`, `withdrawn`, or `unknown`.

If inference is needed, label confidence as high/medium/low and put the reason in notes or `dedup_log`.

## Deduplication and Cross-Registry Linking

Never blindly delete China records as duplicates of global records.

Use this hierarchy:

1. exact source ID match
2. explicit cross-registry ID reference
3. same sponsor + asset + indication + very similar title + overlapping dates
4. global MRCT evidence
5. company-disclosure linkage

Keep both records when they represent different source systems. Link them in `dedup_log` and mark a primary record only when justified.

For CDE list-page-only records, treat CTR-to-NCT crosswalks as medium confidence unless the title/phase/status/indication mapping is obvious.

## CDE-Specific Policy

CDE is important for this user. Do not give up after a static curl or automation-controlled browser fails.

Preferred order:

1. Use existing saved CDE export if present under `~/Desktop/CDE_Query/<keyword>_<timestamp>/`.
2. Use normal Google Chrome + Apple Events/JXA workflow (`cde-query-normal`) on macOS.
3. If verification appears, ask the user to complete legitimate verification in that same ordinary Chrome session, then continue extraction.
4. If still blocked, record `verification_required`, `waf_challenge`, or `geo_blocked` with evidence in `source_log`.
5. Accept user-provided CSV/PDF/export and label it as user-supplied.

CDE list-page fields are limited. If details pages are not captured, do not invent phase, enrollment, endpoints, PI, sites, or dates. Write `未抓取 / Not captured` or `未报告 / Not reported`.

See `references/cde-normal-chrome.md` for exact commands and merge procedure.

## Workbook Quality Gates

Before final response, run an actual verification script with `openpyxl`.

Minimum checks:

- workbook opens without error
- required sheets exist
- Chinese sheets precede English sheets
- `trial_records` has rows beyond header
- `competitor_comparison` and `competitor_trials` are populated for CI tasks
- rows have source and retrieval date or source file
- data exists beyond column A in every core sheet
- `source_log` includes all attempted sources, even failures
- CDE status is not stale if CDE data was later merged successfully
- output path is absolute

A workbook with only IDs in column A is failed even if row counts are nonzero.

## Recent Changes / Monitoring

When the task is monitoring or has a lookback window, compare the new normalized table with the prior snapshot if available.

Track:

- new trial records
- status changes
- phase changes
- enrollment changes
- primary completion date shifts >90 days
- new countries/sites, especially China
- new endpoints or arms
- company-disclosed milestones
- termination/suspension

Classify severity:

- High: new Phase III/pivotal trial, China IND/trial start, termination, topline results.
- Medium: Phase II start, recruitment status change, major enrollment/date shift, new combination arm.
- Low: metadata cleanup, contacts/sites, minor date or typo changes.

If no prior snapshot exists, label findings as first-pass discovery rather than changes.

## Final Response Pattern

Keep final response concise and evidence-based:

1. Scope and sources checked.
2. Output workbook path.
3. Top 3-5 takeaways.
4. Direct competitor table or short list.
5. China-specific notes if applicable.
6. Caveats and next recommended expansion.

Do not overclaim. Public registries can lag company disclosures.

## Common Failure Modes to Avoid

- Only querying the target asset and missing true competitors.
- Producing markdown but no workbook.
- Producing English-only output for a Chinese-speaking user.
- Failing to log blocked sources.
- Treating CDE regulatory status as trial recruitment status.
- Treating ClinicalTrials.gov as globally exhaustive.
- Ignoring Chinese aliases and company subsidiaries.
- Guessing CDE detail fields from a list page.
- Forgetting PI fields when PubMed or registry pages can provide them.
- Not verifying workbook contents after saving.
- Re-running blocked CDE/ChiCTR dynamic fetches repeatedly instead of switching strategy.

## Evaluation and Maintenance

This skill has a skill-creator-compatible eval set at `evals/evals.json`.
Use it when changing this skill instead of relying only on intuition.

The eval set covers three failure-prone workflows:

1. Full 9MW1911 COPD competitive-intelligence workbook.
   - Expected: 9MW1911 plus same-target/pathway competitors such as astegolimab, itepekimab, and tozorakimab or justified alternatives.
   - Expected: bilingual workbook, source log, search dictionary, and workbook verification.
2. Saved CDE export merge into an existing workbook.
   - Expected: read `cde_result.json/csv`, back up the workbook, add bilingual CDE sheets, merge CDE rows into main trial records, update source log, and create dedup/crosswalk notes.
3. GLP-1/GIP obesity 90-day monitoring workbook.
   - Expected: competitor discovery, China/global source attempts, recent-change severity classification, and clear first-pass-vs-diff labeling.

Before committing changes to this skill, run:

```bash
python scripts/validate_skill.py
```

For larger rewrites, follow the `skill-creator` loop:

1. Snapshot the previous skill version.
2. Run each eval with the changed skill and with the previous version as baseline.
3. Grade expectations from `evals/evals.json`.
4. Generate a review artifact with `eval-viewer/generate_review.py` or a static report.
5. Revise based on failed expectations and user feedback.

## Reference Loading Guide

- For any full CI task: read `references/competitor-discovery.md` and `references/excel-schema-and-qc.md`.
- For any data pull: read `references/source-workflows.md`.
- For any CDE query/merge: read `references/cde-normal-chrome.md`.
