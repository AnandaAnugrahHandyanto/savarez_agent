#!/usr/bin/env python3
"""Fetch FEC individual contributions via the OpenFEC API.

Defaults to DEMO_KEY (30 req/hour). Set FEC_API_KEY for 1000 req/hour.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import get_json  # noqa: E402

BASE = "https://api.open.fec.gov/v1/schedules/schedule_a/"
COLUMNS = [
    "contributor_name",
    "contributor_employer",
    "contributor_occupation",
    "contributor_city",
    "contributor_state",
    "contributor_zip",
    "recipient_name",
    "recipient_committee_id",
    "amount",
    "date",
    "cycle",
    "transaction_id",
]


def fetch(
    api_key: str,
    candidate: str | None,
    committee: str | None,
    employer: str | None,
    cycle: int,
    out_path: str,
    page_size: int = 100,
    max_pages: int = 50,
) -> int:
    params: dict[str, str | int] = {
        "api_key": api_key,
        "per_page": page_size,
        "two_year_transaction_period": cycle,
        "sort": "-contribution_receipt_date",
    }
    if candidate:
        params["contributor_name"] = candidate
    if employer:
        params["contributor_employer"] = employer
    if committee:
        params["committee_id"] = committee

    rows: list[dict[str, str]] = []
    last_index = None
    pages = 0
    while pages < max_pages:
        if last_index is not None:
            params["last_index"] = last_index
        try:
            payload = get_json(BASE, params=params)
        except Exception as e:  # noqa: BLE001
            print(f"FEC error on page {pages + 1}: {e}", file=sys.stderr)
            break
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not results:
            break
        for r in results:
            rows.append(
                {
                    "contributor_name": r.get("contributor_name", "") or "",
                    "contributor_employer": r.get("contributor_employer", "") or "",
                    "contributor_occupation": r.get("contributor_occupation", "") or "",
                    "contributor_city": r.get("contributor_city", "") or "",
                    "contributor_state": r.get("contributor_state", "") or "",
                    "contributor_zip": r.get("contributor_zip", "") or "",
                    "recipient_name": r.get("committee", {}).get("name", "") if r.get("committee") else "",
                    "recipient_committee_id": r.get("committee_id", "") or "",
                    "amount": str(r.get("contribution_receipt_amount", "") or ""),
                    "date": r.get("contribution_receipt_date", "")[:10] if r.get("contribution_receipt_date") else "",
                    "cycle": str(r.get("two_year_transaction_period", cycle)),
                    "transaction_id": r.get("transaction_id", "") or "",
                }
            )
        pagination = payload.get("pagination", {}) if isinstance(payload, dict) else {}
        last_index = pagination.get("last_indexes", {}).get("last_index") if pagination else None
        if not last_index:
            break
        pages += 1
        time.sleep(1.0)  # polite

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", help="Candidate / contributor name filter")
    p.add_argument("--committee", help="FEC committee ID (e.g. C00580100)")
    p.add_argument("--employer", help="Filter by contributor employer")
    p.add_argument("--cycle", type=int, default=2024)
    p.add_argument("--out", required=True)
    p.add_argument("--api-key", default=os.environ.get("FEC_API_KEY", "DEMO_KEY"))
    p.add_argument("--max-pages", type=int, default=50)
    a = p.parse_args()
    if not (a.candidate or a.committee or a.employer):
        p.error("must supply at least one of --candidate / --committee / --employer")
    n = fetch(
        api_key=a.api_key,
        candidate=a.candidate,
        committee=a.committee,
        employer=a.employer,
        cycle=a.cycle,
        out_path=a.out,
        max_pages=a.max_pages,
    )
    print(f"Wrote {n} FEC contribution rows to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
