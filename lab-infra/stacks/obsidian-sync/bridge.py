#!/usr/bin/env python3
"""
Obsidian LiveSync Bridge
Watches /lab/obsidian_vault and syncs .md files to CouchDB
in the format expected by the Obsidian Self-hosted LiveSync plugin.
"""

import os
import time
import json
import hashlib
import base64
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Config from env
COUCHDB_URL  = os.environ["COUCHDB_URL"]
COUCHDB_USER = os.environ["COUCHDB_USER"]
COUCHDB_PASS = os.environ["COUCHDB_PASSWORD"]
COUCHDB_DB   = os.environ.get("COUCHDB_DB", "obsidian")
VAULT_PATH   = Path(os.environ.get("VAULT_PATH", "/vault"))
INTERVAL     = int(os.environ.get("SYNC_INTERVAL", "5"))

AUTH = (COUCHDB_USER, COUCHDB_PASS)
DB_URL = f"{COUCHDB_URL}/{COUCHDB_DB}"


def configure_cors():
    """Enable CORS on CouchDB for Obsidian LiveSync plugin."""
    cfg_url = f"{COUCHDB_URL}/_node/_local/_config"
    cors_settings = {
        "httpd/enable_cors": "true",
        "cors/origins": "app://obsidian.md,capacitor://localhost,http://localhost",
        "cors/credentials": "true",
        "cors/methods": "GET, PUT, POST, HEAD, DELETE",
        "cors/headers": "accept, authorization, content-type, origin, referer",
    }
    for key, value in cors_settings.items():
        section, name = key.split("/")
        r = requests.put(
            f"{cfg_url}/{section}/{name}",
            json=value,
            auth=AUTH,
            timeout=10,
        )
        if r.status_code in (200, 201):
            log.info(f"CORS config set: {key} = {value}")
        else:
            log.warning(f"Failed to set {key}: {r.status_code} {r.text}")


def ensure_db():
    """Create the database if it doesn't exist."""
    r = requests.get(DB_URL, auth=AUTH, timeout=10)
    if r.status_code == 404:
        r = requests.put(DB_URL, auth=AUTH, timeout=10)
        r.raise_for_status()
        log.info(f"Created CouchDB database: {COUCHDB_DB}")
    elif r.status_code == 200:
        log.info(f"Database {COUCHDB_DB} already exists")
    else:
        r.raise_for_status()


def file_to_doc_id(path: Path) -> str:
    """Convert a vault-relative path to a LiveSync-compatible doc ID."""
    rel = path.relative_to(VAULT_PATH)
    # LiveSync uses the path with forward slashes, prefixed with "/"
    return str(rel).replace("\\", "/")


def content_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def get_existing_doc(doc_id: str):
    """Fetch existing doc from CouchDB (returns None if not found)."""
    r = requests.get(f"{DB_URL}/{requests.utils.quote(doc_id, safe='')}", auth=AUTH, timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def upsert_doc(doc_id: str, content: str, mtime: float):
    """Insert or update a note in CouchDB."""
    existing = get_existing_doc(doc_id)

    # LiveSync document format
    doc = {
        "_id": doc_id,
        "type": "plain",
        "content": content,
        "ctime": int(mtime * 1000),
        "mtime": int(mtime * 1000),
        "size": len(content),
        "deleted": False,
    }

    if existing:
        # Skip if content hasn't changed
        if existing.get("content") == content:
            return False
        doc["_rev"] = existing["_rev"]
        log.info(f"Updating: {doc_id}")
    else:
        log.info(f"Creating: {doc_id}")

    encoded_id = requests.utils.quote(doc_id, safe="")
    r = requests.put(f"{DB_URL}/{encoded_id}", json=doc, auth=AUTH, timeout=10)
    r.raise_for_status()
    return True


def delete_doc(doc_id: str):
    """Mark a doc as deleted in CouchDB."""
    existing = get_existing_doc(doc_id)
    if not existing or existing.get("deleted"):
        return
    existing["deleted"] = True
    existing["mtime"] = int(time.time() * 1000)
    encoded_id = requests.utils.quote(doc_id, safe="")
    r = requests.put(f"{DB_URL}/{encoded_id}", json=existing, auth=AUTH, timeout=10)
    r.raise_for_status()
    log.info(f"Deleted: {doc_id}")


def scan_vault() -> dict:
    """Return {doc_id: (content, mtime)} for all .md files in vault."""
    result = {}
    for path in VAULT_PATH.rglob("*.md"):
        if any(part.startswith(".") for part in path.parts):
            continue  # skip hidden dirs (.obsidian, .trash, etc.)
        try:
            content = path.read_text(encoding="utf-8")
            mtime = path.stat().st_mtime
            doc_id = file_to_doc_id(path)
            result[doc_id] = (content, mtime)
        except Exception as e:
            log.warning(f"Could not read {path}: {e}")
    return result


def sync_all(previous_ids: set) -> set:
    """Full sync pass — upsert all vault files, delete removed ones."""
    vault_files = scan_vault()
    current_ids = set(vault_files.keys())

    synced = 0
    for doc_id, (content, mtime) in vault_files.items():
        try:
            changed = upsert_doc(doc_id, content, mtime)
            if changed:
                synced += 1
        except Exception as e:
            log.error(f"Failed to sync {doc_id}: {e}")

    # Handle deletions
    for doc_id in previous_ids - current_ids:
        try:
            delete_doc(doc_id)
        except Exception as e:
            log.error(f"Failed to delete {doc_id}: {e}")

    if synced:
        log.info(f"Synced {synced} changed file(s). Total tracked: {len(current_ids)}")

    return current_ids


def wait_for_couchdb(retries=30, delay=2):
    """Wait until CouchDB is reachable."""
    log.info("Waiting for CouchDB to be ready...")
    for i in range(retries):
        try:
            r = requests.get(COUCHDB_URL, auth=AUTH, timeout=5)
            if r.status_code == 200:
                log.info("CouchDB is ready!")
                return
        except Exception:
            pass
        log.info(f"Not ready yet, retrying in {delay}s... ({i+1}/{retries})")
        time.sleep(delay)
    raise RuntimeError("CouchDB did not become ready in time")


if __name__ == "__main__":
    log.info(f"Obsidian LiveSync Bridge starting")
    log.info(f"  Vault:    {VAULT_PATH}")
    log.info(f"  CouchDB:  {DB_URL}")
    log.info(f"  Interval: {INTERVAL}s")

    wait_for_couchdb()
    configure_cors()
    ensure_db()

    known_ids: set = set()

    # Initial full sync
    log.info("Running initial full sync...")
    known_ids = sync_all(known_ids)
    log.info("Initial sync complete. Watching for changes...")

    while True:
        time.sleep(INTERVAL)
        try:
            known_ids = sync_all(known_ids)
        except Exception as e:
            log.error(f"Sync error: {e}")
