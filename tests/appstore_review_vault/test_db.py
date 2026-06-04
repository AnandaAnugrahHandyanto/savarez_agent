import sqlite3

from appstore_review_vault.db import (
    archive_app,
    get_review_count,
    init_db,
    insert_review_source,
    list_apps,
    restore_app,
    search_reviews,
    upsert_app,
    upsert_review,
)


def make_conn(tmp_path):
    db_path = tmp_path / "reviews.sqlite"
    init_db(db_path)
    return sqlite3.connect(db_path)


def review(review_id="r1", title="Buggy app", body="Crashes on launch"):
    return {
        "review_id": review_id,
        "rating": 1,
        "version": "1.0",
        "title": title,
        "body": body,
        "author_name": "User",
        "author_url": None,
        "review_url": None,
        "updated_at_apple": "2026-06-01T00:00:00Z",
        "vote_sum": None,
        "vote_count": None,
    }


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "reviews.sqlite"
    init_db(db_path)
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')")}

    assert "apps" in tables
    assert "reviews" in tables
    assert "review_sources" in tables
    assert "fetch_runs" in tables
    assert "fetch_errors" in tables
    assert "reviews_fts" in tables


def test_upsert_review_dedupes_and_tracks_first_seen(tmp_path):
    conn = make_conn(tmp_path)
    upsert_app(conn, "1477376905", "GitHub")

    assert upsert_review(conn, "1477376905", review()) is True
    first_seen = conn.execute("SELECT first_seen_at FROM reviews WHERE review_id='r1'").fetchone()[0]
    assert upsert_review(conn, "1477376905", review(title="Updated title")) is False

    row = conn.execute("SELECT title, first_seen_at FROM reviews WHERE review_id='r1'").fetchone()
    assert row == ("Updated title", first_seen)
    assert get_review_count(conn) == 1


def test_review_sources_dedupe_by_review_country_sort_page(tmp_path):
    conn = make_conn(tmp_path)
    upsert_app(conn, "1477376905", "GitHub")
    upsert_review(conn, "1477376905", review())

    insert_review_source(conn, "r1", "1477376905", "us", "mostrecent", 1)
    insert_review_source(conn, "r1", "1477376905", "us", "mostrecent", 1)
    insert_review_source(conn, "r1", "1477376905", "gb", "mosthelpful", 2)

    count = conn.execute("SELECT COUNT(*) FROM review_sources").fetchone()[0]
    assert count == 2


def test_search_reviews_uses_fts_and_filters_sources(tmp_path):
    conn = make_conn(tmp_path)
    upsert_app(conn, "1477376905", "GitHub")
    upsert_review(conn, "1477376905", review())
    insert_review_source(conn, "r1", "1477376905", "us", "mostrecent", 1)

    rows = search_reviews(conn, q="crashes", country="us", rating=1)

    assert len(rows) == 1
    assert rows[0]["review_id"] == "r1"
    assert rows[0]["countries"] == "us"


def test_archive_hides_app_by_default_and_restore_reactivates(tmp_path):
    conn = make_conn(tmp_path)
    upsert_app(conn, "1477376905", "GitHub")
    archive_app(conn, "1477376905")

    assert list_apps(conn) == []
    assert list_apps(conn, include_archived=True)[0]["archived_at"] is not None

    restore_app(conn, "1477376905")
    assert list_apps(conn)[0]["app_id"] == "1477376905"
