from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Any, Callable

from .db import (
    active_app_ids,
    finish_fetch_run,
    insert_review_source,
    record_fetch_error,
    start_fetch_run,
    upsert_review,
)
from .fetcher import COUNTRIES, SORTS, fetch_review_page
from .parser import parse_reviews_feed


@dataclass
class RefreshSettings:
    delay_seconds: float = 0.75
    jitter_seconds: float = 0.5
    rate_limit_consecutive_errors: int = 3


@dataclass
class JobStats:
    status: str = "completed"
    request_count: int = 0
    review_count: int = 0
    new_review_count: int = 0
    error_count: int = 0
    run_id: int | None = None


FetchPage = Callable[[str, str, str, int], dict[str, Any]]


def _status_code(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    return int(status) if isinstance(status, int) else None


def _sleep(settings: RefreshSettings) -> None:
    if settings.delay_seconds <= 0 and settings.jitter_seconds <= 0:
        return
    jitter = random.uniform(0, settings.jitter_seconds) if settings.jitter_seconds > 0 else 0
    time.sleep(settings.delay_seconds + jitter)


def refresh_app(conn, app_id: str, *, fetch_page: FetchPage = fetch_review_page, settings: RefreshSettings | None = None, run_id: int | None = None) -> JobStats:
    settings = settings or RefreshSettings()
    own_run = run_id is None
    stats = JobStats(run_id=run_id)
    if own_run:
        stats.run_id = start_fetch_run(conn, app_count=1)
    consecutive_rate_limits = 0
    try:
        for country in COUNTRIES:
            for sort in SORTS:
                for page in range(1, 11):
                    attempts = 0
                    while True:
                        try:
                            attempts += 1
                            payload = fetch_page(app_id, country, sort, page)
                            stats.request_count += 1
                            consecutive_rate_limits = 0
                            break
                        except Exception as exc:  # noqa: BLE001 - tool records opaque fetch failures
                            code = _status_code(exc)
                            stats.error_count += 1
                            record_fetch_error(conn, stats.run_id, app_id, country, sort, page, code, str(exc))
                            if code in (403, 429):
                                consecutive_rate_limits += 1
                                if consecutive_rate_limits >= settings.rate_limit_consecutive_errors:
                                    stats.status = "rate_limited"
                                    return stats
                            if attempts >= 3:
                                if code == 400 and page > 1:
                                    payload = {"feed": {}}
                                    break
                                if code in (403, 429):
                                    stats.status = "rate_limited"
                                    return stats
                                payload = {"feed": {}}
                                break
                            _sleep(settings)
                    reviews = parse_reviews_feed(payload)
                    if not reviews:
                        continue
                    for review in reviews:
                        stats.review_count += 1
                        if upsert_review(conn, app_id, review):
                            stats.new_review_count += 1
                        insert_review_source(conn, review["review_id"], app_id, country, sort, page)
                    _sleep(settings)
        if stats.error_count and stats.status == "completed":
            stats.status = "completed_with_errors"
        return stats
    finally:
        if own_run and stats.run_id is not None:
            finish_fetch_run(
                conn,
                stats.run_id,
                stats.status,
                request_count=stats.request_count,
                review_count=stats.review_count,
                new_review_count=stats.new_review_count,
                error_count=stats.error_count,
            )


def refresh_all(conn, *, fetch_page: FetchPage = fetch_review_page, settings: RefreshSettings | None = None) -> JobStats:
    settings = settings or RefreshSettings()
    app_ids = active_app_ids(conn)
    run_id = start_fetch_run(conn, app_count=len(app_ids))
    total = JobStats(status="completed", run_id=run_id)
    try:
        for app_id in app_ids:
            stats = refresh_app(conn, app_id, fetch_page=fetch_page, settings=settings, run_id=run_id)
            total.request_count += stats.request_count
            total.review_count += stats.review_count
            total.new_review_count += stats.new_review_count
            total.error_count += stats.error_count
            if stats.status == "rate_limited":
                total.status = "rate_limited"
                break
            if stats.status == "completed_with_errors" and total.status == "completed":
                total.status = "completed_with_errors"
        return total
    finally:
        finish_fetch_run(
            conn,
            run_id,
            total.status,
            request_count=total.request_count,
            review_count=total.review_count,
            new_review_count=total.new_review_count,
            error_count=total.error_count,
        )
