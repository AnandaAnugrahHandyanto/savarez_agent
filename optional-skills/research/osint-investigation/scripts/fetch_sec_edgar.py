#!/usr/bin/env python3
"""Fetch SEC EDGAR filings index for a given CIK or company name.

SEC requires a User-Agent header with contact info. Set SEC_USER_AGENT,
e.g. SEC_USER_AGENT="Research example@example.com".

Filings JSON is published at:
    https://data.sec.gov/submissions/CIK<10-digit-padded>.json

Company lookup uses:
    https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=<name>&output=atom
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import get, get_json  # noqa: E402

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COLUMNS = [
    "cik",
    "company_name",
    "form_type",
    "filing_date",
    "accession_number",
    "primary_document",
    "filing_url",
    "reporting_period",
]


def _ua() -> str:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        raise SystemExit(
            "SEC requires a User-Agent with contact info. "
            "Set SEC_USER_AGENT='Your Name your@email'."
        )
    return ua


def _resolve_cik(company: str) -> str:
    """Resolve a company name to a CIK via EDGAR's atom feed."""
    url = "https://www.sec.gov/cgi-bin/browse-edgar"
    params = {"action": "getcompany", "company": company, "output": "atom", "owner": "include"}
    body = get(url, params=params, user_agent=_ua()).decode("utf-8", errors="replace")
    m = re.search(r"CIK=(\d{10})", body)
    if not m:
        raise SystemExit(f"Could not resolve CIK for company={company!r}")
    return m.group(1)


def fetch(
    cik: str | None,
    company: str | None,
    types: list[str],
    since: str | None,
    out_path: str,
) -> int:
    if not cik and company:
        cik = _resolve_cik(company)
    if not cik:
        raise SystemExit("must supply --cik or --company")
    cik = cik.zfill(10)
    url = SUBMISSIONS_URL.format(cik=cik)
    payload = get_json(url, user_agent=_ua())
    if not isinstance(payload, dict):
        raise SystemExit(f"Unexpected EDGAR response shape for CIK {cik}")
    name = payload.get("name", "")
    recent = (payload.get("filings", {}) or {}).get("recent", {}) or {}
    form = recent.get("form", [])
    date = recent.get("filingDate", [])
    accession = recent.get("accessionNumber", [])
    primary_doc = recent.get("primaryDocument", [])
    period = recent.get("reportDate", [])

    type_set = {t.strip().upper() for t in types} if types else None
    rows: list[dict[str, str]] = []
    for i, ftype in enumerate(form):
        if type_set and ftype.upper() not in type_set:
            continue
        fdate = date[i] if i < len(date) else ""
        if since and fdate and fdate < since:
            continue
        acc = accession[i] if i < len(accession) else ""
        pdoc = primary_doc[i] if i < len(primary_doc) else ""
        acc_nodash = acc.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{pdoc}"
            if acc and pdoc
            else ""
        )
        rows.append(
            {
                "cik": cik,
                "company_name": name,
                "form_type": ftype,
                "filing_date": fdate,
                "accession_number": acc,
                "primary_document": pdoc,
                "filing_url": filing_url,
                "reporting_period": period[i] if i < len(period) else "",
            }
        )

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cik", help="Central Index Key (will be 10-digit zero-padded)")
    p.add_argument("--company", help="Resolve to CIK by company name")
    p.add_argument("--types", default="", help="Comma-separated form types (e.g. 10-K,10-Q,8-K)")
    p.add_argument("--since", help="Skip filings before YYYY-MM-DD")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    types = [t for t in (a.types or "").split(",") if t.strip()]
    n = fetch(cik=a.cik, company=a.company, types=types, since=a.since, out_path=a.out)
    print(f"Wrote {n} EDGAR filing rows to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
