from __future__ import annotations

import csv
import io
from typing import Any, Iterable

CSV_COLUMNS = [
    "app_id",
    "app_name",
    "review_id",
    "countries",
    "rating",
    "version",
    "title",
    "body",
    "author_name",
    "review_url",
    "updated_at_apple",
    "first_seen_at",
    "last_seen_at",
    "source_sorts",
]


def reviews_to_csv(rows: Iterable[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
