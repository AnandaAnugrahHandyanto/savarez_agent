from __future__ import annotations

from typing import Any


def _label(obj: dict[str, Any] | None) -> str | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get("label")
    if value is None:
        return None
    return str(value)


def _nested_label(obj: dict[str, Any], *keys: str) -> str | None:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return _label(cur)


def _int_or_none(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_reviews_feed(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Apple's iTunes customerreviews JSON feed into review dictionaries."""
    feed = payload.get("feed") if isinstance(payload, dict) else None
    if not isinstance(feed, dict):
        return []
    entries = feed.get("entry")
    if not entries:
        return []
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []

    reviews: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        review_id = _nested_label(entry, "id")
        if not review_id:
            continue
        review_url = None
        link = entry.get("link")
        if isinstance(link, list):
            link = link[0] if link else None
        if isinstance(link, dict):
            attributes = link.get("attributes")
            if isinstance(attributes, dict):
                href = attributes.get("href")
                review_url = str(href) if href else None
        reviews.append(
            {
                "review_id": review_id,
                "rating": _int_or_none(_nested_label(entry, "im:rating")),
                "version": _nested_label(entry, "im:version"),
                "title": _nested_label(entry, "title"),
                "body": _nested_label(entry, "content"),
                "author_name": _nested_label(entry, "author", "name"),
                "author_url": _nested_label(entry, "author", "uri"),
                "review_url": review_url,
                "updated_at_apple": _nested_label(entry, "updated"),
                "vote_sum": _int_or_none(_nested_label(entry, "im:voteSum")),
                "vote_count": _int_or_none(_nested_label(entry, "im:voteCount")),
            }
        )
    return reviews
