# Competitor Discovery Playbook

## Core Principle

Competitive intelligence is about the competitive set, not only the named asset. A report that only contains the user's asset is a pipeline excerpt, not competitor analysis.

## Build the Search Dictionary First

Create a structured dictionary before querying:

```yaml
project:
  asset: 9MW1911
  sponsor: Mabwell / 迈威生物
  indication: COPD / 慢性阻塞性肺疾病 / 慢阻肺
  target: ST2 / IL-33 receptor / IL1RL1
  pathway: IL-33/ST2 axis
asset_aliases:
  - 9MW1911
  - 9MW1911 injection
  - 9MW1911注射液
company_aliases:
  - Mabwell
  - Mabwell (Shanghai) Bioscience
  - 迈威生物
same_target_competitors:
  - astegolimab
same_pathway_competitors:
  - itepekimab
  - tozorakimab
indication_terms:
  - COPD
  - chronic obstructive pulmonary disease
  - 慢性阻塞性肺疾病
  - 慢阻肺
```

## Competitor Rings

Use rings to avoid missing relevant assets:

1. Ring 0: user's asset and sponsor.
2. Ring 1: same target/MoA assets.
3. Ring 2: same pathway assets.
4. Ring 3: same indication and same treatment line assets.
5. Ring 4: region-specific alternatives or standard-of-care context.
6. Ring 5: biosimilars/reference product, when the asset is a biosimilar.

The workbook should clearly label `competitive_relevance` as:

- `direct`: same target/MoA or same intended positioning.
- `adjacent`: same pathway or same line but different target.
- `background`: useful context but not a direct competitor.

## Query Axes

Do not rely on a single query. Query by:

- asset name/code
- sponsor/company/subsidiary
- target/MoA
- pathway
- indication + target
- indication + sponsor
- Chinese indication + Chinese company/drug name
- known trial IDs from company disclosures
- reference product class for biosimilars

## Minimum Evidence For Inclusion

Include a competitor when one of these is true:

- registry trial explicitly involves the asset in the same indication or pathway
- company disclosure states development in the same indication/pathway
- PubMed publication links asset to relevant trial/result
- regulatory announcement shows clinical development or approval in the relevant disease area

## Exclusion Rules

Exclude or move to background when:

- observational/non-drug study is irrelevant
- indication is only loosely related
- target/pathway is unrelated
- terminated/withdrawn trial has no current competitive implication
- data source is commercial/proprietary and not user-supplied or permitted

## Required Workbook Implications

The competitor set must appear in:

- `competitor_comparison_中文` / `_EN`: asset-level head-to-head comparison.
- `competitor_trials_中文` / `_EN`: trial-level records for competitor assets.
- `search_dictionary_中文` / `_EN`: all terms used.
- `source_log_中文` / `_EN`: all searches attempted, including no-result searches.

## Example: Anti-ST2 / IL-33 Pathway COPD

If user asks for 9MW1911 COPD:

- Target asset: 9MW1911, anti-ST2.
- Same target: astegolimab, anti-ST2.
- Same pathway: itepekimab, anti-IL-33; tozorakimab, anti-IL-33.
- Do not stop after 9MW1911 records.

## Biosimilar Special Rule

If the asset is a biosimilar, search:

- target asset code/name
- reference product generic and brand
- `generic biosimilar`
- same indication competitors
- China-specific biosimilar applicants

A biosimilar landscape without reference-product and same-class biosimilar competitors is incomplete.
