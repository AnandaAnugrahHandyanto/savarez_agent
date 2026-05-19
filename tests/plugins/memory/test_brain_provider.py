import json
import sqlite3
import stat

from plugins.memory import load_memory_provider
from plugins.memory.brain import BrainMemoryProvider
from plugins.memory.brain.store import BrainStore, DEFAULT_SOURCES


def _provider(tmp_path):
    provider = BrainMemoryProvider(config={"db_path": str(tmp_path / "brain.db")})
    provider.initialize("session-1", hermes_home=str(tmp_path))
    return provider


def test_brain_store_seeds_default_sources(tmp_path):
    store = BrainStore(tmp_path / "brain.db")

    sources = {row["source_id"] for row in store.list_sources()}

    assert set(DEFAULT_SOURCES).issubset(sources)
    # Re-opening should be idempotent and not duplicate anything.
    store.close()
    store = BrainStore(tmp_path / "brain.db")
    sources_again = [row["source_id"] for row in store.list_sources()]
    assert len(sources_again) == len(set(sources_again))
    store.close()


def test_write_and_recall_are_source_isolated(tmp_path):
    store = BrainStore(tmp_path / "brain.db")
    alt_id = store.write_fact(
        source_id="altcoinist",
        content="Altcoinist uses token-gated campaign analytics for creator growth.",
        kind="company_fact",
        confidence=0.9,
    )
    marktr_id = store.write_fact(
        source_id="marktr",
        content="Marktr uses partner-led operations for client delivery.",
        kind="company_fact",
        confidence=0.9,
    )

    altcoinist = store.recall("Altcoinist campaign analytics", source_id="altcoinist")
    marktr = store.recall("Altcoinist campaign analytics", source_id="marktr")

    assert [row["fact_id"] for row in altcoinist] == [alt_id]
    assert marktr == []
    assert store.recall("partner operations", source_id="marktr")[0]["fact_id"] == marktr_id
    assert store.recall("partner operations", source_id="altcoinist") == []
    store.close()


def test_same_content_can_exist_in_different_sources_but_dedupes_within_source(tmp_path):
    store = BrainStore(tmp_path / "brain.db")
    content = "Use weekly leadership reviews for operating cadence."

    first = store.write_fact(source_id="altcoinist", content=content)
    duplicate = store.write_fact(source_id="altcoinist", content="  use weekly leadership reviews for operating cadence.  ")
    other_source = store.write_fact(source_id="marktr", content=content)

    assert duplicate == first
    assert other_source != first
    store.close()


def test_provider_tool_write_recall_and_sources(tmp_path):
    provider = _provider(tmp_path)

    written = json.loads(provider.handle_tool_call("brain", {
        "action": "write",
        "source": "altcoinist",
        "content": "Altcoinist company brain imports must preserve file provenance.",
        "kind": "architecture",
        "confidence": 0.95,
    }))
    assert written["success"] is True
    assert written["source"] == "altcoinist"

    recalled = json.loads(provider.handle_tool_call("brain", {
        "action": "recall",
        "source": "altcoinist",
        "query": "Altcoinist imports provenance",
    }))
    assert recalled["success"] is True
    assert recalled["count"] == 1
    assert recalled["results"][0]["source_id"] == "altcoinist"

    sources = json.loads(provider.handle_tool_call("brain", {"action": "sources"}))
    assert "altcoinist" in {s["source_id"] for s in sources["sources"]}
    provider.shutdown()


def test_provider_prefetch_respects_explicit_company_scope(tmp_path):
    provider = _provider(tmp_path)
    assert provider._store is not None
    store = provider._store
    store.write_fact(
        source_id="altcoinist",
        content="Altcoinist campaign analytics belong only in the Altcoinist brain source.",
        kind="company_fact",
        confidence=0.95,
    )

    assert provider.prefetch("campaign analytics") == ""
    scoped = provider.prefetch("Altcoinist campaign analytics")
    assert "Hermes Brain Recall" in scoped
    assert "altcoinist" in scoped
    assert "campaign analytics" in scoped
    provider.shutdown()


def test_provider_mirrors_builtin_memory_writes_to_expected_sources(tmp_path):
    provider = _provider(tmp_path)

    provider.on_memory_write("add", "user", "Christian prefers source-separated brain memory.")
    provider.on_memory_write("add", "memory", "Hermes brain provider uses SQLite FTS for MVP.")

    assert provider._store is not None
    store = provider._store
    personal = store.recall("source-separated brain memory", source_id="personal")
    hermes = store.recall("SQLite FTS MVP", source_id="hermes")

    assert personal and personal[0]["kind"] == "user_profile"
    assert hermes and hermes[0]["kind"] == "operating_memory"
    provider.shutdown()


def test_provider_discovery_loads_brain_provider():
    provider = load_memory_provider("brain")

    assert provider is not None
    assert provider.name == "brain"
    assert provider.is_available() is True


def test_document_chunks_recall_with_provenance_and_source_isolation(tmp_path):
    store = BrainStore(tmp_path / "brain.db")

    alt = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        title="Product",
        section="What Altcoinist Builds",
        line_start=3,
        line_end=12,
        repo="altcoinist-company-brain",
        repo_commit="aaa111",
        content="Altcoinist token-gated campaign analytics help creators grow recurring revenue.",
        kind="product_context",
        confidence=0.95,
        metadata={"file_sha256": "alt-sha"},
    )
    marktr = store.write_document_chunk(
        source_id="marktr",
        path="context/marktr/marktr.md",
        title="Marktr",
        section="What Marktr is",
        line_start=4,
        line_end=8,
        repo="altcoinist-company-brain",
        repo_commit="aaa111",
        content="Marktr partner-led client delivery uses campaign analytics for service operations.",
        kind="marktr_context",
        confidence=0.9,
    )

    altcoinist = store.recall_documents("campaign analytics", source_id="altcoinist")
    marktr_results = store.recall_documents("campaign analytics", source_id="marktr")

    assert [row["chunk_id"] for row in altcoinist] == [alt["chunk_id"]]
    assert [row["chunk_id"] for row in marktr_results] == [marktr["chunk_id"]]
    assert altcoinist[0]["document"]["path"] == "context/PRODUCT.md"
    assert altcoinist[0]["provenance"]["repo_commit"] == "aaa111"
    assert altcoinist[0]["provenance"]["line_start"] == 3
    assert altcoinist[0]["source_id"] == "altcoinist"
    store.close()


def test_multiple_chunks_same_commit_share_document_when_no_file_hash(tmp_path):
    store = BrainStore(tmp_path / "brain.db")

    first = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Acquisition",
        line_start=1,
        line_end=10,
        repo="altcoinist-company-brain",
        repo_commit="samecommit",
        content="Altcoinist acquisition analytics chunk should stay active as the first slice.",
    )
    second = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Retention",
        line_start=11,
        line_end=20,
        repo="altcoinist-company-brain",
        repo_commit="samecommit",
        content="Altcoinist retention analytics chunk should stay active as the second slice.",
    )

    assert first["document_id"] == second["document_id"]
    assert second["superseded_chunk_ids"] == []
    acquisition = store.recall_documents("acquisition analytics", source_id="altcoinist")
    retention = store.recall_documents("retention analytics", source_id="altcoinist")
    assert [row["chunk_id"] for row in acquisition] == [first["chunk_id"]]
    assert [row["chunk_id"] for row in retention] == [second["chunk_id"]]
    assert store.stats()["document_chunks"]["altcoinist"] == {"active": 2, "total": 2}
    store.close()


def test_document_chunk_supersession_keeps_recall_current(tmp_path):
    store = BrainStore(tmp_path / "brain.db")

    old = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Product strategy",
        line_start=10,
        line_end=20,
        repo="altcoinist-company-brain",
        repo_commit="oldcommit",
        content="Altcoinist old launch motion centered on broad agency services.",
        kind="product_context",
    )
    duplicate = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Product strategy",
        line_start=10,
        line_end=20,
        repo="altcoinist-company-brain",
        repo_commit="oldcommit",
        content=" Altcoinist old launch motion centered on broad agency services. ",
        kind="product_context",
    )
    new = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Product strategy",
        line_start=10,
        line_end=20,
        repo="altcoinist-company-brain",
        repo_commit="newcommit",
        content="Altcoinist current product-led growth motion centers on token-gated analytics.",
        kind="product_context",
    )

    assert duplicate["chunk_id"] == old["chunk_id"]
    assert new["chunk_id"] != old["chunk_id"]
    assert new["superseded_chunk_ids"] == [old["chunk_id"]]
    assert store.recall_documents("old launch agency", source_id="altcoinist") == []
    inactive = store.recall_documents("old launch agency", source_id="altcoinist", include_inactive=True)
    assert [row["chunk_id"] for row in inactive] == [old["chunk_id"]]
    current = store.recall_documents("product-led token-gated", source_id="altcoinist")
    assert [row["chunk_id"] for row in current] == [new["chunk_id"]]
    stats = store.stats()
    assert stats["document_chunks"]["altcoinist"] == {"active": 1, "total": 2}
    store.close()


def test_provider_tool_writes_and_recalls_document_chunks(tmp_path):
    provider = _provider(tmp_path)

    written = json.loads(provider.handle_tool_call("brain", {
        "action": "write_document",
        "source": "altcoinist",
        "path": "context/PRODUCT.md",
        "title": "Product",
        "section": "What Altcoinist Builds",
        "line_start": 1,
        "line_end": 9,
        "repo": "altcoinist-company-brain",
        "repo_commit": "abc123",
        "content": "Altcoinist PLG motion uses creator analytics as the product surface.",
        "kind": "product_context",
        "confidence": 0.92,
    }))
    assert written["success"] is True
    assert written["source"] == "altcoinist"
    assert written["chunk_id"] > 0

    recalled = json.loads(provider.handle_tool_call("brain", {
        "action": "recall_documents",
        "source": "altcoinist",
        "query": "creator analytics product surface",
        "limit": 3,
    }))

    assert recalled["success"] is True
    assert recalled["count"] == 1
    assert recalled["results"][0]["source_id"] == "altcoinist"
    assert recalled["results"][0]["document"]["path"] == "context/PRODUCT.md"
    provider.shutdown()


def test_brain_store_redacts_secret_like_fact_and_document_content(tmp_path):
    store = BrainStore(tmp_path / "brain" / "brain.db")

    store.write_fact(
        source_id="hermes",
        content="temporary api_key=sk-testsecretvalue123456 should never persist",
        provenance={"authorization": "Bearer abcdefghijklmnopqrstuvwxyz"},
    )
    fact = store.recall("temporary", source_id="hermes")[0]
    assert "sk-testsecretvalue" not in fact["content"]
    assert "abcdefghijklmnopqrstuvwxyz" not in fact["provenance"]
    assert "[REDACTED]" in fact["content"]

    store.write_document_chunk(
        source_id="altcoinist",
        path="context/SECRETS.md",
        content="Do not store Bearer abcdefghijklmnopqrstuvwxyz in document text.",
        metadata={"password": "supersecretpassword"},
        provenance={"api_key": "sk-doc...3456"},
    )
    chunk = store.recall_documents("document text", source_id="altcoinist")[0]
    serialized = json.dumps(chunk, sort_keys=True)
    assert "abcdefghijklmnopqrstuvwxyz" not in serialized
    assert "supersecretpassword" not in serialized
    assert "***" not in serialized
    assert "[REDACTED]" in serialized

    raw_chunk = store.write_document_chunk(
        source_id="altcoinist",
        path="context/MANUAL.md",
        content="Manual final redaction visible content.",
    )
    store._conn.execute(
        "UPDATE document_chunks SET content = ?, normalized_content = ? WHERE chunk_id = ?",
        (
            "Manual final redaction api_key=returnContentSecret123456 should redact on return.",
            "manual final redaction api_key=returncontentsecret123456 should redact on return.",
            raw_chunk["chunk_id"],
        ),
    )
    store._conn.commit()
    manual = store.recall_documents("manual final redaction", source_id="altcoinist")[0]
    assert "returnContentSecret123456" not in json.dumps(manual, sort_keys=True)
    assert "[REDACTED]" in manual["content"]
    store.close()


def test_brain_store_redacts_secret_like_document_locator_fields(tmp_path):
    store = BrainStore(tmp_path / "brain" / "brain.db")

    written = store.write_document_chunk(
        source_id="hermes",
        path="context/api_key=pathSecretValue123456.md",
        title="Release Bearer abcdefghijklmnopqrstuvwxyz notes",
        section="Deploy password=supersecretpassword",
        repo="token=repoSecretValue123",
        repo_commit="token=commitSecretValue123456",
        content="Hermes locator redaction sentinel content should remain searchable.",
        metadata={"file_sha256": "locator-redaction-sha"},
    )

    assert "[REDACTED]" in written["path"]
    recalled = store.recall_documents("locator redaction sentinel", source_id="hermes")[0]
    assert "[REDACTED]" in recalled["path"]
    assert "[REDACTED]" in recalled["section"]
    assert "[REDACTED]" in recalled["repo"]
    assert "[REDACTED]" in recalled["repo_commit"]
    assert "[REDACTED]" in recalled["document"]["title"]

    persisted_rows = []
    for sql in (
        "SELECT path, title, repo, repo_commit, metadata FROM documents",
        "SELECT path, section, repo, repo_commit, provenance FROM document_chunks",
        "SELECT path, section, provenance FROM chunks_fts",
    ):
        persisted_rows.extend(dict(row) for row in store._conn.execute(sql).fetchall())
    serialized = json.dumps({"recalled": recalled, "persisted": persisted_rows}, sort_keys=True)
    for raw in (
        "pathSecretValue123456",
        "abcdefghijklmnopqrstuvwxyz",
        "supersecretpassword",
        "repoSecretValue123",
        "commitSecretValue123456",
    ):
        assert raw not in serialized
    assert "[REDACTED]" in serialized
    store.close()


def test_brain_store_uses_private_file_permissions(tmp_path):
    db_path = tmp_path / "brain" / "brain.db"
    store = BrainStore(db_path)
    store.write_fact(source_id="personal", content="Private local memory permissions test.")
    store.close()

    assert stat.S_IMODE(db_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600


def test_document_reingest_with_changed_sections_hides_old_chunks(tmp_path):
    store = BrainStore(tmp_path / "brain.db")
    old = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Legacy section",
        line_start=1,
        line_end=5,
        repo="altcoinist-company-brain",
        repo_commit="oldcommit",
        content="Altcoinist legacy agency services chunk should disappear after full document reingest.",
    )
    new = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Current section renamed",
        line_start=20,
        line_end=30,
        repo="altcoinist-company-brain",
        repo_commit="newcommit",
        content="Altcoinist current product analytics chunk survives document reingest.",
    )

    assert old["chunk_id"] != new["chunk_id"]
    assert store.recall_documents("legacy agency services", source_id="altcoinist") == []
    inactive = store.recall_documents("legacy agency services", source_id="altcoinist", include_inactive=True)
    assert [row["chunk_id"] for row in inactive] == [old["chunk_id"]]
    current = store.recall_documents("current product analytics", source_id="altcoinist")
    assert [row["chunk_id"] for row in current] == [new["chunk_id"]]
    store.close()


def test_changed_document_hash_with_unchanged_chunk_gets_new_active_chunk(tmp_path):
    store = BrainStore(tmp_path / "brain.db")
    content = "Altcoinist unchanged chunk across file hashes remains current and active."

    old = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Stable section",
        line_start=7,
        line_end=9,
        repo="altcoinist-company-brain",
        repo_commit="samecommit",
        content=content,
        metadata={"file_sha256": "old-file-hash"},
    )
    new = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Stable section",
        line_start=7,
        line_end=9,
        repo="altcoinist-company-brain",
        repo_commit="samecommit",
        content=content,
        metadata={"file_sha256": "new-file-hash"},
    )

    assert new["document_id"] != old["document_id"]
    assert new["chunk_id"] != old["chunk_id"]
    assert new["is_active"] is True
    assert new["superseded_chunk_ids"] == [old["chunk_id"]]
    current = store.recall_documents("unchanged chunk across file hashes", source_id="altcoinist")
    assert [row["chunk_id"] for row in current] == [new["chunk_id"]]
    rows = store._conn.execute(
        "SELECT chunk_id, document_id, content_hash, is_active FROM document_chunks ORDER BY chunk_id"
    ).fetchall()
    assert [(row["chunk_id"], row["document_id"], row["content_hash"], row["is_active"]) for row in rows] == [
        (old["chunk_id"], old["document_id"], "old-file-hash", 0),
        (new["chunk_id"], new["document_id"], "new-file-hash", 1),
    ]
    store.close()


def test_reimporting_previously_superseded_document_version_reactivates_current_chunk(tmp_path):
    store = BrainStore(tmp_path / "brain.db")

    old = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Reimport section",
        line_start=1,
        line_end=4,
        repo="altcoinist-company-brain",
        repo_commit="oldcommit",
        content="Altcoinist reimportable legacy chunk becomes current again.",
        metadata={"file_sha256": "old-reimport-hash"},
    )
    new = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Reimport section",
        line_start=1,
        line_end=4,
        repo="altcoinist-company-brain",
        repo_commit="newcommit",
        content="Altcoinist replacement chunk should be inactive after old version reimport.",
        metadata={"file_sha256": "new-reimport-hash"},
    )
    reimported = store.write_document_chunk(
        source_id="altcoinist",
        path="context/PRODUCT.md",
        section="Reimport section",
        line_start=1,
        line_end=4,
        repo="altcoinist-company-brain",
        repo_commit="oldcommit",
        content="Altcoinist reimportable legacy chunk becomes current again.",
        metadata={"file_sha256": "old-reimport-hash"},
    )

    assert reimported["document_id"] == old["document_id"]
    assert reimported["chunk_id"] == old["chunk_id"]
    assert reimported["is_active"] is True
    assert reimported["superseded_chunk_ids"] == [new["chunk_id"]]
    assert store.recall_documents("replacement chunk should be inactive", source_id="altcoinist") == []
    current = store.recall_documents("reimportable legacy chunk", source_id="altcoinist")
    assert [row["chunk_id"] for row in current] == [old["chunk_id"]]
    rows = store._conn.execute(
        "SELECT document_id, repo_commit, is_active FROM documents ORDER BY document_id"
    ).fetchall()
    assert [(row["document_id"], row["repo_commit"], row["is_active"]) for row in rows] == [
        (old["document_id"], "oldcommit", 1),
        (new["document_id"], "newcommit", 0),
    ]
    store.close()


def test_same_path_in_different_repos_remains_active_in_both_repos(tmp_path):
    store = BrainStore(tmp_path / "brain.db")
    content = "Hermes shared same-path repository chunk remains active in both repos."

    first = store.write_document_chunk(
        source_id="hermes",
        path="docs/README.md",
        section="Overview",
        line_start=1,
        line_end=3,
        repo="repo-alpha",
        repo_commit="samecommit",
        content=content,
        metadata={"file_sha256": "same-file-hash"},
    )
    second = store.write_document_chunk(
        source_id="hermes",
        path="docs/README.md",
        section="Overview",
        line_start=1,
        line_end=3,
        repo="repo-beta",
        repo_commit="samecommit",
        content=content,
        metadata={"file_sha256": "same-file-hash"},
    )

    assert first["chunk_id"] != second["chunk_id"]
    recalled = store.recall_documents("same-path repository chunk", source_id="hermes")
    assert {row["chunk_id"] for row in recalled} == {first["chunk_id"], second["chunk_id"]}
    assert store.stats()["documents"]["hermes"] == {"active": 2, "total": 2}
    assert store.stats()["document_chunks"]["hermes"] == {"active": 2, "total": 2}
    store.close()


def test_v2_document_tables_migrate_to_repo_aware_unique_constraints(tmp_path):
    db_path = tmp_path / "brain.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
            source_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner_kind TEXT DEFAULT 'unknown',
            default_visibility TEXT DEFAULT 'private',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            path TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'document',
            repo TEXT NOT NULL DEFAULT '',
            repo_commit TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL,
            metadata TEXT DEFAULT '',
            visibility TEXT NOT NULL DEFAULT 'private',
            is_active INTEGER NOT NULL DEFAULT 1,
            supersedes_document_id INTEGER,
            superseded_at TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, path, repo_commit, content_hash)
        );
        CREATE TABLE document_chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            source_id TEXT NOT NULL,
            path TEXT NOT NULL,
            section TEXT NOT NULL DEFAULT '',
            line_start INTEGER NOT NULL DEFAULT 0,
            line_end INTEGER NOT NULL DEFAULT 0,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            content TEXT NOT NULL,
            normalized_content TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'document_chunk',
            confidence REAL NOT NULL DEFAULT 0.75,
            notability TEXT NOT NULL DEFAULT 'medium',
            provenance TEXT DEFAULT '',
            visibility TEXT NOT NULL DEFAULT 'private',
            repo TEXT NOT NULL DEFAULT '',
            repo_commit TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            supersedes_chunk_id INTEGER,
            superseded_at TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, path, repo_commit, section, line_start, line_end, normalized_content)
        );
        INSERT INTO sources (source_id, title) VALUES ('hermes', 'Hermes');
        INSERT INTO documents (
            document_id, source_id, path, title, kind, repo, repo_commit, content_hash,
            metadata, visibility, is_active, created_at, updated_at
        ) VALUES (
            1, 'hermes', 'context/api_key=legacyPathSecret123456.md',
            'Legacy Bearer abcdefghijklmnopqrstuvwxyz title', 'document',
            'token=legacyRepoSecret123456', 'token=legacyCommitSecret123456',
            'legacy-file-hash', '{"password":"legacyMetaSecret123456"}',
            'private', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        );
        INSERT INTO document_chunks (
            chunk_id, document_id, source_id, path, section, line_start, line_end,
            chunk_index, content, normalized_content, kind, confidence, notability,
            provenance, visibility, repo, repo_commit, content_hash, is_active,
            created_at, updated_at
        ) VALUES (
            1, 1, 'hermes', 'context/api_key=legacyPathSecret123456.md',
            'Deploy password=legacySectionSecret123456', 1, 3, 0,
            'Legacy migration sentinel text with api_key=legacyContentSecret123456',
            'legacy migration sentinel text with api_key=legacyContentSecret123456',
            'document_chunk', 0.9, 'medium',
            '{"authorization":"Bearer abcdefghijklmnopqrstuvwxyz","path":"api_key=legacyProvSecret123456"}',
            'private', 'token=legacyRepoSecret123456', 'token=legacyCommitSecret123456',
            'legacy-file-hash', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()

    store = BrainStore(db_path)
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] >= 3
    assert store._has_unique_columns("documents", ["source_id", "path", "repo", "repo_commit", "content_hash"])
    assert store._has_unique_columns(
        "document_chunks",
        ["source_id", "path", "repo", "repo_commit", "section", "line_start", "line_end", "normalized_content", "content_hash"],
    )
    migrated = store.recall_documents("legacy migration sentinel", source_id="hermes", include_inactive=True)
    assert migrated and "[REDACTED]" in json.dumps(migrated[0], sort_keys=True)
    persisted_rows = []
    for sql in (
        "SELECT path, title, repo, repo_commit, metadata FROM documents",
        "SELECT path, section, repo, repo_commit, content, normalized_content, provenance FROM document_chunks",
        "SELECT content, path, section, provenance FROM chunks_fts",
    ):
        persisted_rows.extend(dict(row) for row in store._conn.execute(sql).fetchall())
    serialized_legacy = json.dumps(persisted_rows, sort_keys=True)
    raw_legacy_values = (
        "legacyPathSecret123456",
        "abcdefghijklmnopqrstuvwxyz",
        "legacySectionSecret123456",
        "legacyRepoSecret123456",
        "legacyCommitSecret123456",
        "legacyContentSecret123456",
        "legacyProvSecret123456",
        "legacyMetaSecret123456",
    )
    for raw in raw_legacy_values:
        assert raw not in serialized_legacy

    first = store.write_document_chunk(
        source_id="hermes",
        path="docs/README.md",
        section="Overview",
        line_start=1,
        line_end=3,
        repo="repo-alpha",
        repo_commit="samecommit",
        content="Hermes migrated repo alpha chunk remains active.",
        metadata={"file_sha256": "same-file-hash"},
    )
    second = store.write_document_chunk(
        source_id="hermes",
        path="docs/README.md",
        section="Overview",
        line_start=1,
        line_end=3,
        repo="repo-beta",
        repo_commit="samecommit",
        content="Hermes migrated repo beta chunk remains active.",
        metadata={"file_sha256": "same-file-hash"},
    )
    assert first["chunk_id"] != second["chunk_id"]
    assert {row["chunk_id"] for row in store.recall_documents("migrated repo", source_id="hermes")} == {
        first["chunk_id"],
        second["chunk_id"],
    }
    store.close()
    db_bytes = b"".join(
        path.read_bytes()
        for path in (db_path, db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm"))
        if path.exists()
    )
    for raw in raw_legacy_values:
        assert raw.encode() not in db_bytes


def test_legacy_fact_schema_is_migrated_and_indexed(tmp_path):
    db_path = tmp_path / "brain.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
            source_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner_kind TEXT DEFAULT 'unknown',
            default_visibility TEXT DEFAULT 'private',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE facts (
            fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            content TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'note',
            confidence REAL NOT NULL DEFAULT 0.7,
            notability TEXT NOT NULL DEFAULT 'medium',
            provenance TEXT DEFAULT '',
            visibility TEXT NOT NULL DEFAULT 'private',
            valid_from TEXT DEFAULT '',
            valid_until TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO sources (source_id, title) VALUES ('hermes', 'Hermes');
        INSERT INTO facts (source_id, content, kind, confidence, provenance)
            VALUES (
                'hermes',
                'Legacy facts-only brain schema survives migration.',
                'architecture',
                0.95,
                '{"api_key":"legacyFactSecret123456","note":"safe provenance"}'
            );
        """
    )
    conn.commit()
    conn.close()

    store = BrainStore(db_path)
    rows = store.recall("facts-only schema", source_id="hermes")
    assert len(rows) == 1
    assert "legacyFactSecret123456" not in json.dumps(rows, sort_keys=True)
    assert "[REDACTED]" in rows[0]["provenance"]
    persisted_rows = []
    for sql in (
        "SELECT content, provenance FROM facts",
        "SELECT content, provenance FROM facts_fts",
    ):
        persisted_rows.extend(dict(row) for row in store._conn.execute(sql).fetchall())
    assert "legacyFactSecret123456" not in json.dumps(persisted_rows, sort_keys=True)
    existing_id = rows[0]["fact_id"]
    duplicate = store.write_fact(source_id="hermes", content=" legacy facts-only brain schema survives migration. ")
    assert duplicate == existing_id
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] >= 2
    store.close()
    db_bytes = b"".join(
        path.read_bytes()
        for path in (db_path, db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm"))
        if path.exists()
    )
    assert b"legacyFactSecret123456" not in db_bytes


def test_memory_replace_mirror_supersedes_old_brain_fact(tmp_path):
    provider = _provider(tmp_path)
    provider.on_memory_write("add", "memory", "Hermes brain old operating rule.")
    provider.on_memory_write(
        "replace",
        "memory",
        "Hermes brain new operating rule.",
        metadata={
            "old_text": "old operating",
            "resolved_old_text": "Hermes brain old operating rule.",
        },
    )

    assert provider._store is not None
    assert provider._store.recall("old operating rule", source_id="hermes") == []
    assert provider._store.recall("new operating rule", source_id="hermes")
    provider.shutdown()
