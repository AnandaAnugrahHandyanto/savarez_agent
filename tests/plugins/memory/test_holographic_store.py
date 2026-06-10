"""Tests for holographic MemoryStore._resolve_entity edge cases.

Regression tests for LIKE → = / INSTR fix: LIKE treats _ and % as
wildcards and is case-insensitive for ASCII, causing false matches and
duplicate entity creation.
"""

import pytest


@pytest.fixture()
def store():
    from plugins.memory.holographic.store import MemoryStore

    return MemoryStore(":memory:")


class TestResolveEntityExactMatch:
    """_resolve_entity must use exact (=) comparison, not LIKE."""

    def test_same_name_returns_same_id(self, store):
        eid1 = store._resolve_entity("TestEntity")
        eid2 = store._resolve_entity("TestEntity")
        assert eid1 == eid2

    def test_underscore_not_treated_as_wildcard(self, store):
        """LIKE '_' matches any single char; = must not."""
        eid1 = store._resolve_entity("test_entity")
        eid2 = store._resolve_entity("testXentity")
        assert eid1 != eid2

    def test_percent_not_treated_as_wildcard(self, store):
        """LIKE '%' matches any substring; = must not."""
        eid1 = store._resolve_entity("test%entity")
        eid2 = store._resolve_entity("test123entity")
        assert eid1 != eid2

    def test_case_sensitive(self, store):
        """SQLite LIKE is case-insensitive for ASCII; = must be case-sensitive."""
        eid1 = store._resolve_entity("Apple")
        eid2 = store._resolve_entity("apple")
        assert eid1 != eid2

    def test_new_entity_created_on_miss(self, store):
        eid1 = store._resolve_entity("alpha")
        eid2 = store._resolve_entity("beta")
        assert eid1 != eid2


class TestResolveEntityAliasMatch:
    """Alias search must also avoid LIKE wildcard pitfalls."""

    def test_alias_resolves_to_existing_entity(self, store):
        eid = store._resolve_entity("primary_name")
        store._conn.execute(
            "UPDATE entities SET aliases = ? WHERE entity_id = ?",
            ("alt_name,another_name", eid),
        )
        store._conn.commit()
        assert store._resolve_entity("alt_name") == eid

    def test_underscore_in_alias_not_wildcard(self, store):
        """INSTR-based alias search must not treat _ as wildcard."""
        eid = store._resolve_entity("real_entity")
        store._conn.execute(
            "UPDATE entities SET aliases = ? WHERE entity_id = ?",
            ("real_entity", eid),
        )
        store._conn.commit()
        # "realXentity" should NOT match alias "real_entity"
        other = store._resolve_entity("realXentity")
        assert other != eid

    def test_percent_in_alias_not_wildcard(self, store):
        """INSTR-based alias search must not treat % as wildcard."""
        eid = store._resolve_entity("widget")
        store._conn.execute(
            "UPDATE entities SET aliases = ? WHERE entity_id = ?",
            ("widget%", eid),
        )
        store._conn.commit()
        # "widget123" should NOT match alias "widget%"
        other = store._resolve_entity("widget123")
        assert other != eid

    def test_alias_substring_does_not_match(self, store):
        """INSTR must match exact comma-delimited token, not substring."""
        eid = store._resolve_entity("foo")
        store._conn.execute(
            "UPDATE entities SET aliases = ? WHERE entity_id = ?",
            ("foobar,baz", eid),
        )
        store._conn.commit()
        # "foo" is NOT a standalone alias — "foobar" is
        # Resolving "foo" should find via name match, not alias
        assert store._resolve_entity("foo") == eid
        # "bar" should NOT match
        other = store._resolve_entity("bar")
        assert other != eid
