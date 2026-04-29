# CDE Normal Chrome Workflow and Merge Procedure

## Why This Exists

`chinadrugtrials.org.cn` often returns WAF/blank pages to static HTTP, Scrapling, Playwright, or automation-controlled Chrome. The user's preference is to automate CDE as much as possible and avoid repeated manual verification.

The compliant workaround is to drive the user's ordinary Google Chrome session with Apple Events/JXA on macOS. This does not crack CAPTCHA or bypass access control; it only automates a browser session the user can normally access.

## Preferred Query Workflow on macOS

Prerequisites:

1. Use ordinary Google Chrome, not Playwright/remote-debug Chrome.
2. Chrome: `View -> Developer -> Allow JavaScript from Apple Events`.
3. Allow Terminal/iTerm/Hermes to control Google Chrome if macOS prompts for Automation permission.

Convenience command:

```bash
cde-query-normal 9MW1911
```

Expected outputs:

```text
~/Desktop/CDE_Query/<keyword>_<timestamp>/cde_result.html
~/Desktop/CDE_Query/<keyword>_<timestamp>/cde_result.txt
~/Desktop/CDE_Query/<keyword>_<timestamp>/cde_result.csv
~/Desktop/CDE_Query/<keyword>_<timestamp>/cde_result.json
```

Successful list-page extraction should include:

- URL: `https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml`
- title: `试验公示和查询`
- headers: `序号 / 登记号 / 试验状态 / 药物名称 / 适应症 / 试验通俗题目`
- rows containing CTR IDs

If verification appears, ask the user to complete it in that same ordinary Chrome window, then continue extraction.

## WAF / Verification Handling

Do not bypass verification. Detect and log:

- page title/body contains `Verification`, `验证`, `验证码`
- tiny/empty body
- WAF challenge HTML or strange meta markers
- HTTP 400/202 challenge behavior

Record in source_log as:

- `verification_required`
- `waf_challenge`
- `geo_blocked`
- `blocked`

Include evidence: HTTP status, title, screenshot path, or raw file path.

## Merging Saved CDE Results Into Workbook

Use this when user says: “文件在 ~/Desktop/CDE_Query/...，读取 cde_result.json/csv，并合并进竞品分析 Excel。”

### Steps

1. Locate CDE directory and workbook.
   - CDE: `~/Desktop/CDE_Query/<keyword>_<timestamp>/cde_result.json`
   - Workbook: `~/Desktop/<project_name>_<YYYYMMDD>/<project_name>.xlsx`
2. Read `cde_result.json` first. It preserves URL, title, captured_at, table rows, links, and WAF evidence.
3. Use CSV as provenance and secondary table source.
4. Create timestamped workbook backup before editing:
   - `<workbook>_backup_before_CDE_merge_<YYYYMMDD_HHMMSS>.xlsx`
5. Normalize CDE rows into:
   - `CDE_trials_中文`
   - `CDE_trials_EN`
6. Merge the same rows into:
   - `trial_records_中文`
   - `trial_records_EN`
7. Make merge idempotent: remove/replace previous CDE rows before appending new rows.
8. Update source log. If old CDE row says unavailable/blocked, replace with success and record count.
9. Add/update dedup/crosswalk sheets:
   - `dedup_log_中文`
   - `dedup_log_EN`
10. Reorder sheets Chinese first.
11. Verify workbook with openpyxl.

## CDE List-Page Field Mapping

CDE list page normally has:

- `登记号` -> source_trial_id / CTR ID
- `试验状态` -> status_raw
- `药物名称` -> asset_raw
- `适应症` -> indication_raw
- `试验通俗题目` -> trial_title

List page usually does not include:

- full phase
- enrollment
- endpoints
- PI
- sites
- dates
- detailed design

If detail page was not captured, write:

- `未抓取 / Not captured` for fields that could exist but were not captured
- `未报告 / Not reported` for fields not reported in the captured source

## CTR-to-NCT Crosswalk

Crosswalk only when supported by evidence:

- same drug name
- same sponsor/applicant
- same indication
- similar title
- matching phase/status if available
- overlapping dates if available

Confidence:

- High: explicit cross-registry ID or obvious same trial from title + details.
- Medium: list-page-only match with same asset/indication/title but no dates/details.
- Low: plausible but weak match; do not merge, only note.

Keep both source records unless there is a strong reason to collapse them. CDE and CT.gov serve different regional/source roles.

## Verification Expectations

After CDE merge, verify:

- `CDE_trials_中文` and `CDE_trials_EN` have imported rows.
- `trial_records_中文` and `trial_records_EN` include CDE rows, not only side sheets.
- `source_log` CDE status is success with correct record count.
- `dedup_log` includes crosswalk decisions and confidence.
- core sheets have data beyond column A.

## Example Interpretation

For 9MW1911 CDE list results:

- CTR20252324: COPD, recruiting; likely Phase II based on matched CT.gov NCT07292714 if title/indication align.
- CTR20230380: COPD, recruitment complete; likely Phase I/II based on matched CT.gov NCT06175351 if title/indication align.
- CTR20213300 / CTR20212590: healthy-volunteer early trials; matching to CT.gov Phase I records may be medium confidence if only list-page data is available.

State these as inferred crosswalks, not as CDE-provided full details.
