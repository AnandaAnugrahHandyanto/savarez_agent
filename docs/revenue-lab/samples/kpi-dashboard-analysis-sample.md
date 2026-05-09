# Sample 3 — KPI / Dashboard Analysis Sample

Buyer-facing title: Local Service Business KPI Snapshot  
Sample niche: Residential HVAC / plumbing / mechanical contractor  
Prepared: 2026-05-09  
Data status: Synthetic/anonymized sample data; no Life Church or client data

Companion spreadsheet-style file: `kpi-dashboard-sample-data.csv`

## Executive summary

This sample shows how Ryan can turn a small business owner's rough monthly numbers into a decision dashboard. The important shift is from "we got leads" to "which channel produced profitable booked jobs, and where are we leaking response time or conversion?"

Using the sample three-month dataset:

- Total leads: 382
- Total booked jobs: 168
- Overall booking rate: 44.0%
- Total revenue: $365,400
- Total tracked marketing spend: $9,100
- Revenue per booked job: $2,175
- Paid-search ROAS: 11.9x revenue/spend
- Referral/repeat produced the highest booking rate at 70.4%
- Social/local posts produced the lowest booking rate at 26.7% and slowest response times

## Dashboard view

| Channel | Leads | Booked jobs | Booking rate | Revenue | Spend | Revenue / lead | Revenue / booked job | Avg response |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Organic search | 144 | 61 | 42.4% | $133,700 | $0 | $928 | $2,192 | 58 min |
| Paid search | 112 | 38 | 33.9% | $97,500 | $8,200 | $871 | $2,566 | 50 min |
| Referral/repeat | 81 | 57 | 70.4% | $112,200 | $0 | $1,386 | $1,968 | 31 min |
| Social/local posts | 45 | 12 | 26.7% | $22,000 | $900 | $489 | $1,833 | 107 min |
| Total | 382 | 168 | 44.0% | $365,400 | $9,100 | $957 | $2,175 | 61 min |

## Formula examples

Use these in Google Sheets or Excel:

- Booking rate: `=booked_jobs / leads`
- Revenue per lead: `=revenue / leads`
- Revenue per booked job: `=revenue / booked_jobs`
- ROAS: `=revenue / marketing_spend`
- Response-time flag: `=IF(avg_response_minutes>60,"At risk","OK")`
- Channel priority score: `(Revenue per lead * Booking rate) - Spend per lead`, normalized by owner capacity

## What the buyer should notice

1. Referral/repeat leads convert far better than cold channels. A simple maintenance-plan or review-referral campaign may be more profitable than buying more ads.
2. Paid search is not automatically bad. The sample paid-search rows show strong revenue per booked job, but the booking rate trails organic and referral channels.
3. Social/local posts are not worthless, but they need a different goal: trust-building, seasonal education, recruiting, and retargeting rather than immediate booked jobs.
4. Response time matters. Channels with slower follow-up often look worse than they are because the operational handoff leaks value.
5. The dashboard is small enough for an owner to use weekly.

## Recommended next actions

| Priority | Action | Why |
|---|---|---|
| 1 | Add source/channel to every call form and intake note | Attribution before more spend |
| 2 | Call back all web leads in under 15 minutes during business hours | Improve conversion without increasing traffic |
| 3 | Build a referral/repeat campaign around maintenance and seasonal checkups | Highest sample booking rate |
| 4 | Split paid search by repair vs replacement intent | Find the high-ticket campaigns |
| 5 | Review social content goals | Stop judging awareness content only by booked jobs |

## Buyer deliverable

A Google Sheet or Excel workbook with:

- Raw data tab.
- Monthly KPI summary tab.
- Channel comparison tab.
- Red/yellow/green flags.
- 5-10 action recommendations.
- Optional Loom walkthrough script.

## Timeline

1-2 business days using exported sample/CSV data. 3-5 business days if Ryan has to clean messy CRM exports, call logs, ad exports, or QuickBooks categories.

## Price option

- Spreadsheet KPI snapshot: $400 fixed.
- KPI snapshot + executive memo: $650 fixed.
- KPI dashboard + market/competitor/website audit bundle: $1,500-$2,000.

## Source notes

This specific file uses synthetic/anonymized data only. It is meant to demonstrate structure, formulas, and buyer value. For a paid buyer, Ryan can plug in exports from public ad dashboards, call tracking, CRM, or manually supplied owner data after confirming permission.
