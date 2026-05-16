#!/usr/bin/env python3
"""Search ICIJ Offshore Leaks for entities, officers, or by jurisdiction.

Uses the public Open Refine reconciliation endpoint plus the entity-detail
JSON pages. No auth required. Polite ~1 req/s.

Reference: https://offshoreleaks.icij.org/
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import get_json  # noqa: E402

RECONCILE_URL = "https://offshoreleaks.icij.org/reconcile"
COLUMNS = [
    "node_id",
    "name",
    "node_type",
    "country_codes",
    "countries",
    "jurisdiction",
    "incorporation_date",
    "inactivation_date",
    "source",
    "entity_url",
    "connections",
]


def _reconcile(query: str, type_filter: str | None) -> list[dict]:
    """Use ICIJ reconcile endpoint to search by name."""
    queries = {"q0": {"query": query, "limit": 50}}
    if type_filter:
        queries["q0"]["type"] = type_filter
    params = {"queries": urllib.parse.quote(str(queries).replace("'", '"'))}
    # The reconcile endpoint expects URL-encoded JSON.
    import json as _json
    url = f"{RECONCILE_URL}?queries={urllib.parse.quote(_json.dumps(queries))}"
    payload = get_json(url)
    if not isinstance(payload, dict):
        return []
    return payload.get("q0", {}).get("result", []) or []


def fetch(
    entity: str | None,
    officer: str | None,
    jurisdiction: str | None,
    out_path: str,
    limit: int = 50,
) -> int:
    rows: list[dict[str, str]] = []
    queries: list[tuple[str, str]] = []
    if entity:
        queries.append((entity, "Entity"))
    if officer:
        queries.append((officer, "Officer"))

    if jurisdiction and not queries:
        # Reconcile doesn't support pure-jurisdiction search; fall back to
        # listing recent entities filtered by name match isn't possible without
        # the bulk DB. Tell user to use bulk download.
        raise SystemExit(
            "Jurisdiction-only search requires the bulk database download. "
            "See: https://offshoreleaks.icij.org/pages/database"
        )

    seen: set[str] = set()
    for query, qtype in queries:
        try:
            results = _reconcile(query, qtype)
        except Exception as e:  # noqa: BLE001
            print(f"ICIJ reconcile error for {query!r}: {e}", file=sys.stderr)
            continue
        for r in results[:limit]:
            nid = str(r.get("id", ""))
            if not nid or nid in seen:
                continue
            seen.add(nid)
            entity_url = f"https://offshoreleaks.icij.org/nodes/{nid}"
            node_type = (r.get("type") or [{}])[0].get("name", "") if r.get("type") else ""
            description = r.get("description", "") or ""
            # Some basic metadata fields come in 'features' or 'description'
            rows.append(
                {
                    "node_id": nid,
                    "name": r.get("name", "") or "",
                    "node_type": node_type or qtype,
                    "country_codes": "",
                    "countries": "",
                    "jurisdiction": "",
                    "incorporation_date": "",
                    "inactivation_date": "",
                    "source": description,
                    "entity_url": entity_url,
                    "connections": "",
                }
            )
        time.sleep(1.0)

    if jurisdiction:
        # Post-filter by jurisdiction string match in source/description.
        jur_low = jurisdiction.lower()
        rows = [r for r in rows if jur_low in r["source"].lower()]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entity", help="Search by entity name")
    p.add_argument("--officer", help="Search by officer / individual name")
    p.add_argument("--jurisdiction", help="Filter results by jurisdiction text")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if not (a.entity or a.officer):
        p.error("must supply at least one of --entity / --officer")
    n = fetch(
        entity=a.entity,
        officer=a.officer,
        jurisdiction=a.jurisdiction,
        out_path=a.out,
        limit=a.limit,
    )
    print(f"Wrote {n} ICIJ Offshore Leaks rows to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
