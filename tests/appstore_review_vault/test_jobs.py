from appstore_review_vault.db import get_connection, init_db, upsert_app
from appstore_review_vault.jobs import RefreshSettings, refresh_app


def payload(review_id):
    return {
        "feed": {
            "entry": [
                {
                    "author": {"name": {"label": "A User"}},
                    "updated": {"label": "2026-06-01T12:00:00Z"},
                    "im:rating": {"label": "4"},
                    "im:version": {"label": "1.0"},
                    "id": {"label": review_id},
                    "title": {"label": "Nice"},
                    "content": {"label": "Useful"},
                }
            ]
        }
    }


def test_refresh_app_fetches_all_country_sort_page_combinations(tmp_path):
    db_path = tmp_path / "reviews.sqlite"
    init_db(db_path)
    conn = get_connection(db_path)
    upsert_app(conn, "1477376905", "GitHub")
    calls = []

    def fetch_page(app_id, country, sort, page):
        calls.append((app_id, country, sort, page))
        return payload(f"{country}-{sort}-{page}")

    stats = refresh_app(
        conn,
        "1477376905",
        fetch_page=fetch_page,
        settings=RefreshSettings(delay_seconds=0, jitter_seconds=0),
    )

    assert stats.request_count == 80
    assert stats.review_count == 80
    assert stats.new_review_count == 80
    assert stats.status == "completed"
    assert len(calls) == 80


def test_refresh_app_is_idempotent_for_existing_reviews(tmp_path):
    db_path = tmp_path / "reviews.sqlite"
    init_db(db_path)
    conn = get_connection(db_path)
    upsert_app(conn, "1477376905", "GitHub")

    def fetch_page(app_id, country, sort, page):
        return payload("same-review")

    refresh_app(conn, "1477376905", fetch_page=fetch_page, settings=RefreshSettings(delay_seconds=0, jitter_seconds=0))
    stats = refresh_app(conn, "1477376905", fetch_page=fetch_page, settings=RefreshSettings(delay_seconds=0, jitter_seconds=0))

    assert stats.new_review_count == 0


def test_refresh_app_stops_on_repeated_rate_limits(tmp_path):
    db_path = tmp_path / "reviews.sqlite"
    init_db(db_path)
    conn = get_connection(db_path)
    upsert_app(conn, "1477376905", "GitHub")

    class RateLimit(Exception):
        status_code = 429

    def fetch_page(app_id, country, sort, page):
        raise RateLimit("too many requests")

    stats = refresh_app(conn, "1477376905", fetch_page=fetch_page, settings=RefreshSettings(delay_seconds=0, jitter_seconds=0))

    assert stats.status == "rate_limited"
    assert stats.error_count == 3
