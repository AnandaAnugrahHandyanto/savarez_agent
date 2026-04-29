# Excel Schema and Quality Control

## Required Workbook Sheets

For Chinese-speaking users, sheet order should be Chinese first:

1. `README`
2. `asset_summary_中文`
3. `trial_records_中文`
4. `competitor_comparison_中文`
5. `competitor_trials_中文`
6. `recent_changes_中文` when applicable
7. `CDE_trials_中文` when CDE data is used/imported
8. `dedup_log_中文` when dedup/crosswalk is done
9. `source_log_中文`
10. `search_dictionary_中文`
11. corresponding `_EN` sheets

## `trial_records` Core Columns

Use bilingual equivalents for Chinese/English sheets.

- source
- source_trial_id
- source_url
- retrieved_at
- last_updated_source
- company_canonical
- sponsor_raw
- sponsor_role
- partner_companies
- asset_canonical
- asset_raw
- asset_aliases
- brand_name
- modality
- target_or_moa
- combination_components
- indication_canonical
- indication_raw
- line_of_therapy
- biomarker_population
- trial_title
- official_title
- study_type
- phase_raw
- phase_std
- status_raw
- status_std
- randomized
- blinded
- control_type
- arms
- primary_endpoints
- secondary_endpoints
- enrollment_planned
- enrollment_actual
- start_date
- primary_completion_date
- completion_date
- countries
- has_china
- has_us
- has_eu
- is_global_mrct
- china_sites
- pi_names
- pi_affiliations
- regulatory_context
- notes
- confidence

If the workbook uses a smaller practical column set, do not omit source, trial ID, sponsor, asset, indication, phase/status raw+normalized, endpoints, dates, geography, PI fields, notes, URL.

## `asset_summary`

One row per asset:

- company_canonical
- asset_canonical
- aliases
- target_or_moa
- modality
- indications
- highest_global_phase
- highest_china_phase
- active_global_trials
- active_china_trials
- completed_trials
- key_trial_ids
- next_expected_milestone
- competitive_relevance
- medical_affairs_note

## `competitor_comparison`

Head-to-head asset table:

- company
- asset
- target/pathway
- modality
- indication / population
- highest global phase
- highest China phase
- key active trial(s)
- route/dosing if available
- primary endpoint/readout timing
- geography
- competitive relevance
- evidence/source
- strategic note

## `competitor_trials`

Trial-level records for competitor assets. It can reuse the `trial_records` schema or a compact version, but must include enough metadata to support the comparison.

## `source_log`

Rows for every attempted source:

- source
- query
- retrieval date
- status
- records found
- notes/evidence/path

If an earlier source row says blocked/unavailable and later data is successfully imported, update the stale status.

## `search_dictionary`

Rows for:

- indication terms
- target/MoA terms
- pathway terms
- asset aliases
- company aliases
- competitor assets
- Chinese aliases
- excluded/no-result terms when useful

## `dedup_log`

Required when linking CDE/ChiCTR/EU/CT.gov/company records:

- duplicate_or_link_group_id
- records_in_group
- primary_record if any
- reason
- confidence
- action: kept both / merged / excluded / linked only

## Formatting

Use `openpyxl`:

- blue header fill (`1F4E78`) with white bold text
- frozen top row
- thin borders
- wrapped text
- sensible widths
- filters if practical
- yellow fill (`FFF2CC`) for user's own asset
- green/blue fills for successful imported source rows when useful
- severity/status color coding

## Verification Script Pattern

After saving, run an actual validation:

```python
import openpyxl
p = '/absolute/path/to/workbook.xlsx'
wb = openpyxl.load_workbook(p, data_only=True)
required = ['README','asset_summary_中文','trial_records_中文','competitor_comparison_中文','competitor_trials_中文','source_log_中文','search_dictionary_中文','asset_summary_EN','trial_records_EN','source_log_EN','search_dictionary_EN']
missing = [s for s in required if s not in wb.sheetnames]
if missing:
    raise SystemExit(f'missing sheets: {missing}')
for s in required:
    ws = wb[s]
    rows_with_data_beyond_a = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if any(v not in (None, '') for v in row[1:]):
            rows_with_data_beyond_a += 1
    print(s, ws.max_row, ws.max_column, rows_with_data_beyond_a)
    if ws.max_row < 2 or rows_with_data_beyond_a == 0:
        raise SystemExit(f'empty or one-column-only sheet: {s}')
```

## Failure Conditions

Treat the deliverable as incomplete if:

- no Excel workbook was created
- workbook cannot be opened
- only target asset is present in a CI task
- competitor sheets are missing or empty
- Chinese/English split is absent
- source_log is missing failures or blocked sources
- CDE side sheet is present but main `trial_records` was not updated
- data exists only in column A
- phase/status were inferred without notes/confidence
