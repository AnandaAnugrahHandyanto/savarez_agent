from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

COUNTRIES = ("us", "gb", "ca", "au")
SORTS = ("mostrecent", "mosthelpful")
MAX_PAGE = 10
DEFAULT_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class FetchHTTPError(Exception):
    status_code: int
    message: str

    def __str__(self) -> str:
        return self.message


def validate_fetch_params(app_id: str, country: str, sort: str, page: int) -> None:
    if not str(app_id).isdigit():
        raise ValueError("app_id must be numeric")
    if country not in COUNTRIES:
        raise ValueError(f"country must be one of {', '.join(COUNTRIES)}")
    if sort not in SORTS:
        raise ValueError(f"sort must be one of {', '.join(SORTS)}")
    if page < 1 or page > MAX_PAGE:
        raise ValueError(f"page must be between 1 and {MAX_PAGE}")


def build_review_url(app_id: str, country: str, sort: str, page: int) -> str:
    validate_fetch_params(app_id, country, sort, page)
    return f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby={sort}/json"


def fetch_review_page(app_id: str, country: str, sort: str, page: int, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    url = build_review_url(app_id, country, sort, page)
    headers = {"User-Agent": "appstore-review-vault/0.1", "Accept": "application/json"}
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise FetchHTTPError(0, str(exc)) from exc
    if response.status_code >= 400:
        raise FetchHTTPError(response.status_code, f"Apple RSS request failed with HTTP {response.status_code}")
    return response.json()
