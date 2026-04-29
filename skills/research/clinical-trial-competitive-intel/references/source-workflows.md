# Source Workflows

## ClinicalTrials.gov API v2

Run connectivity checks first:

```bash
env | grep -i '_proxy\|NO_PROXY' || true
curl --noproxy '*' -I -L --connect-timeout 15 --max-time 30 https://clinicaltrials.gov/
```

If proxy breaks TLS, bypass it:

```bash
curl --noproxy '*' 'https://clinicaltrials.gov/api/v2/studies?query.term=9MW1911&pageSize=20&format=json' -o /tmp/ctgov_raw.json
```

Use two-step save-then-parse. Avoid `curl | python`.

Collect:

- NCT ID
- titles
- conditions
- interventions/types
- phases
- status
- start / primary completion / completion dates
- enrollment
- sponsor and collaborators
- arms and outcomes
- countries/facilities when available
- last update
- URL

Known quirks:

- `totalCount` may be 0 even when `studies` contains records. Check `len(studies)`.
- `enrollmentInfo` can be null, dict, or list. Parse defensively.
- Stop pagination when payload is tiny, `studies` is empty, or no `nextPageToken` exists.

## PubMed / MEDLINE

Use PubMed for:

- published trial results
- PI/lead-author clues
- trial IDs not obvious in registries
- Chinese-origin trials published in English-language journals

Commands:

```bash
curl 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=DRUG+AND+INDICATION&retmax=30&retmode=json' -o /tmp/pubmed_search.json
curl 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=PMID1,PMID2&rettype=abstract&retmode=text' -o /tmp/pubmed_abstracts.txt
```

Create `pubmed_derived` trial/result records when appropriate. Link PMIDs to known NCT/CTR IDs in notes.

## CDE / China Drug Trial Registration

Use Chinese and English terms:

- drug code + 注射液/片/胶囊 as applicable
- Chinese company name
- Chinese indication
- target/MoA Chinese alias
- CTR IDs discovered elsewhere

Prefer normal Chrome workflow on macOS when automation-controlled browser fails. See `cde-normal-chrome.md`.

Collect when visible:

- CTR registration number
- drug name
- indication
- trial title
- trial status
- phase/design/details when detail page is captured
- sponsor/applicant
- institutions/sites/PI if visible
- first public/latest update date
- source URL and captured time

Do not treat CDE regulatory acceptance/review/approval as trial recruitment status. Put regulatory milestones in `regulatory_context`.

## ChiCTR

ChiCTR can contain investigator-initiated and broader China trial records. It often requires JS rendering and may block non-China IPs.

Stop if verification/CAPTCHA appears. Do not bypass. Mark `verification_required` or `geo_blocked` in source_log.

## EU CTIS / EUCTR

Use for EU-specific footprint and regional status.

Collect:

- EU trial number / CTIS identifier
- sponsor
- product/IMP
- condition
- phase
- member states
- status by country if available
- start/end dates
- protocol title
- URL

Do not assume EU status equals global status.

## Company Disclosures

Use company sites, press releases, investor decks, annual/interim reports, HKEX/SEC filings, and Chinese exchange announcements to enrich:

- asset aliases and ownership
- partnerships/licensing
- pipeline stage claimed by company
- expected readout windows
- topline/result announcements
- trial IDs not obvious from registries
- strategic positioning: first-in-class, best-in-class, pivotal, China-only, global MRCT

If company claims conflict with registries, report both and label sources.

## Source Log Requirements

Every source attempt gets a row:

- source name
- query term
- retrieval date
- status: success / no_result / blocked / unavailable / verification_required / geo_blocked / user_supplied
- records found
- notes/evidence: HTTP status, file path, screenshot path, raw JSON path, or reason

Never silently omit failed sources.
