from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS apps (
              app_id TEXT PRIMARY KEY,
              name TEXT,
              bundle_id TEXT,
              seller_name TEXT,
              archived_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
              review_id TEXT PRIMARY KEY,
              app_id TEXT NOT NULL,
              rating INTEGER,
              version TEXT,
              title TEXT,
              body TEXT,
              author_name TEXT,
              author_url TEXT,
              review_url TEXT,
              updated_at_apple TEXT,
              vote_sum INTEGER,
              vote_count INTEGER,
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              FOREIGN KEY(app_id) REFERENCES apps(app_id)
            );

            CREATE TABLE IF NOT EXISTS review_sources (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              review_id TEXT NOT NULL,
              app_id TEXT NOT NULL,
              country TEXT NOT NULL,
              sort TEXT NOT NULL,
              page INTEGER NOT NULL,
              fetched_at TEXT NOT NULL,
              UNIQUE(review_id, country, sort, page),
              FOREIGN KEY(review_id) REFERENCES reviews(review_id),
              FOREIGN KEY(app_id) REFERENCES apps(app_id)
            );

            CREATE TABLE IF NOT EXISTS fetch_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              status TEXT NOT NULL,
              app_count INTEGER DEFAULT 0,
              request_count INTEGER DEFAULT 0,
              review_count INTEGER DEFAULT 0,
              new_review_count INTEGER DEFAULT 0,
              error_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS fetch_errors (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id INTEGER,
              app_id TEXT,
              country TEXT,
              sort TEXT,
              page INTEGER,
              status_code INTEGER,
              error TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES fetch_runs(id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS reviews_fts USING fts5(
              title,
              body,
              content='reviews',
              content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS reviews_ai AFTER INSERT ON reviews BEGIN
              INSERT INTO reviews_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
            END;
            CREATE TRIGGER IF NOT EXISTS reviews_ad AFTER DELETE ON reviews BEGIN
              INSERT INTO reviews_fts(reviews_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
            END;
            CREATE TRIGGER IF NOT EXISTS reviews_au AFTER UPDATE ON reviews BEGIN
              INSERT INTO reviews_fts(reviews_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
              INSERT INTO reviews_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
            END;

            CREATE INDEX IF NOT EXISTS idx_reviews_app_id ON reviews(app_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating);
            CREATE INDEX IF NOT EXISTS idx_reviews_updated_at_apple ON reviews(updated_at_apple);
            CREATE INDEX IF NOT EXISTS idx_review_sources_app_country ON review_sources(app_id, country);
            CREATE INDEX IF NOT EXISTS idx_review_sources_sort ON review_sources(sort);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columns = [desc[0] for desc in cursor.description or []]
    rows: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        if isinstance(row, sqlite3.Row):
            rows.append(dict(row))
        else:
            rows.append(dict(zip(columns, row)))
    return rows


def upsert_app(conn: sqlite3.Connection, app_id: str, name: str | None = None) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO apps(app_id, name, created_at, updated_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(app_id) DO UPDATE SET
          name = COALESCE(excluded.name, apps.name),
          updated_at = excluded.updated_at
        """,
        (str(app_id), name, now, now),
    )
    conn.commit()


def archive_app(conn: sqlite3.Connection, app_id: str) -> None:
    now = utc_now()
    conn.execute("UPDATE apps SET archived_at = ?, updated_at = ? WHERE app_id = ?", (now, now, str(app_id)))
    conn.commit()


def restore_app(conn: sqlite3.Connection, app_id: str) -> None:
    now = utc_now()
    conn.execute("UPDATE apps SET archived_at = NULL, updated_at = ? WHERE app_id = ?", (now, str(app_id)))
    conn.commit()


def list_apps(conn: sqlite3.Connection, *, include_archived: bool = False) -> list[dict[str, Any]]:
    where = "" if include_archived else "WHERE a.archived_at IS NULL"
    return _rows(
        conn.execute(
            f"""
            SELECT a.*, COUNT(DISTINCT r.review_id) AS review_count, MAX(r.updated_at_apple) AS latest_review_at
            FROM apps a
            LEFT JOIN reviews r ON r.app_id = a.app_id
            {where}
            GROUP BY a.app_id
            ORDER BY a.name IS NULL, COALESCE(a.name, a.app_id)
            """
        )
    )


def active_app_ids(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute("SELECT app_id FROM apps WHERE archived_at IS NULL ORDER BY app_id")]


def upsert_review(conn: sqlite3.Connection, app_id: str, review: dict[str, Any]) -> bool:
    now = utc_now()
    exists = conn.execute("SELECT 1 FROM reviews WHERE review_id = ?", (review["review_id"],)).fetchone() is not None
    conn.execute(
        """
        INSERT INTO reviews(
          review_id, app_id, rating, version, title, body, author_name, author_url, review_url,
          updated_at_apple, vote_sum, vote_count, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(review_id) DO UPDATE SET
          app_id = excluded.app_id,
          rating = excluded.rating,
          version = excluded.version,
          title = excluded.title,
          body = excluded.body,
          author_name = excluded.author_name,
          author_url = excluded.author_url,
          review_url = excluded.review_url,
          updated_at_apple = excluded.updated_at_apple,
          vote_sum = excluded.vote_sum,
          vote_count = excluded.vote_count,
          last_seen_at = excluded.last_seen_at
        """,
        (
            review["review_id"], str(app_id), review.get("rating"), review.get("version"), review.get("title"),
            review.get("body"), review.get("author_name"), review.get("author_url"), review.get("review_url"),
            review.get("updated_at_apple"), review.get("vote_sum"), review.get("vote_count"), now, now,
        ),
    )
    conn.commit()
    return not exists


def insert_review_source(conn: sqlite3.Connection, review_id: str, app_id: str, country: str, sort: str, page: int) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO review_sources(review_id, app_id, country, sort, page, fetched_at)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (review_id, str(app_id), country, sort, page, utc_now()),
    )
    conn.commit()


def start_fetch_run(conn: sqlite3.Connection, *, app_count: int) -> int:
    cur = conn.execute(
        "INSERT INTO fetch_runs(started_at, status, app_count) VALUES(?, 'running', ?)",
        (utc_now(), app_count),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_fetch_run(conn: sqlite3.Connection, run_id: int, status: str, *, request_count: int, review_count: int, new_review_count: int, error_count: int) -> None:
    conn.execute(
        """
        UPDATE fetch_runs
        SET finished_at = ?, status = ?, request_count = ?, review_count = ?, new_review_count = ?, error_count = ?
        WHERE id = ?
        """,
        (utc_now(), status, request_count, review_count, new_review_count, error_count, run_id),
    )
    conn.commit()


def record_fetch_error(conn: sqlite3.Connection, run_id: int | None, app_id: str, country: str | None, sort: str | None, page: int | None, status_code: int | None, error: str) -> None:
    conn.execute(
        """
        INSERT INTO fetch_errors(run_id, app_id, country, sort, page, status_code, error, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, str(app_id), country, sort, page, status_code, error, utc_now()),
    )
    conn.commit()


def get_review_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0])


def dashboard_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    last_run = conn.execute("SELECT * FROM fetch_runs ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "app_count": conn.execute("SELECT COUNT(*) FROM apps WHERE archived_at IS NULL").fetchone()[0],
        "archived_app_count": conn.execute("SELECT COUNT(*) FROM apps WHERE archived_at IS NOT NULL").fetchone()[0],
        "review_count": get_review_count(conn),
        "last_run": dict(last_run) if last_run else None,
        "recent_errors": _rows(conn.execute("SELECT * FROM fetch_errors ORDER BY id DESC LIMIT 10")),
    }


def list_runs(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    return _rows(conn.execute("SELECT * FROM fetch_runs ORDER BY id DESC LIMIT ?", (limit,)))


def list_errors(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    return _rows(conn.execute("SELECT * FROM fetch_errors ORDER BY id DESC LIMIT ?", (limit,)))


def search_reviews(
    conn: sqlite3.Connection,
    *,
    app_id: str | None = None,
    country: str | None = None,
    rating: int | None = None,
    version: str | None = None,
    q: str | None = None,
    sort_source: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    joins = ["JOIN apps a ON a.app_id = r.app_id", "LEFT JOIN review_sources rs ON rs.review_id = r.review_id"]
    wheres = []
    if q:
        joins.append("JOIN reviews_fts fts ON fts.rowid = r.rowid")
        wheres.append("reviews_fts MATCH ?")
        params.append(q)
    if not include_archived:
        wheres.append("a.archived_at IS NULL")
    if app_id:
        wheres.append("r.app_id = ?")
        params.append(app_id)
    if country:
        wheres.append("rs.country = ?")
        params.append(country)
    if rating is not None:
        wheres.append("r.rating = ?")
        params.append(rating)
    if version:
        wheres.append("r.version = ?")
        params.append(version)
    if sort_source:
        wheres.append("rs.sort = ?")
        params.append(sort_source)
    where_sql = "WHERE " + " AND ".join(wheres) if wheres else ""
    params.extend([limit, offset])
    return _rows(
        conn.execute(
            f"""
            SELECT r.*, a.name AS app_name,
                   GROUP_CONCAT(DISTINCT rs.country) AS countries,
                   GROUP_CONCAT(DISTINCT rs.sort) AS source_sorts
            FROM reviews r
            {' '.join(joins)}
            {where_sql}
            GROUP BY r.review_id
            ORDER BY COALESCE(r.updated_at_apple, r.last_seen_at) DESC
            LIMIT ? OFFSET ?
            """,
            params,
        )
    )
