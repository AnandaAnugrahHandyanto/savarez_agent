"""SOP loader unit tests — resolution paths and stub-property tolerance."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_agent.loops.sop_loader import (
    discover_inbox_messages,
    find_default_sop,
    load_message,
    load_sop_bundle,
    render_company_context_block,
)


def _make_layout(tmp_path: Path, *, with_property_sop: bool = False) -> Path:
    companies = tmp_path / "companies"
    default = companies / "ucpm-default"
    default.mkdir(parents=True)
    (default / "SOP.md").write_text("# default SOP\n", encoding="utf-8")

    prop = companies / "1011-verrado-office"
    prop.mkdir()
    if with_property_sop:
        (prop / "SOP.md").write_text("# property override SOP\n", encoding="utf-8")
    return prop


def test_find_default_sop_resolves_via_sibling_ucpm_default(tmp_path):
    prop = _make_layout(tmp_path)
    sop_path = find_default_sop(prop)
    assert sop_path.read_text(encoding="utf-8") == "# default SOP\n"


def test_find_default_sop_prefers_property_sop_if_present(tmp_path):
    prop = _make_layout(tmp_path, with_property_sop=True)
    sop_path = find_default_sop(prop)
    assert sop_path.read_text(encoding="utf-8") == "# property override SOP\n"


def test_find_default_sop_raises_when_missing(tmp_path):
    # No companies/ucpm-default/SOP.md anywhere.
    standalone = tmp_path / "standalone"
    standalone.mkdir()
    with pytest.raises(FileNotFoundError):
        find_default_sop(standalone)


def test_load_sop_bundle_handles_stub_property_dir(tmp_path):
    """A property dir with no state.yml / no tenants/ must still load."""
    prop = _make_layout(tmp_path)
    bundle = load_sop_bundle(prop)
    assert bundle.company_slug == "1011-verrado-office"
    assert bundle.company_state == {}
    assert bundle.overrides == {}
    assert bundle.extra_context["tenants"] == []


def test_load_sop_bundle_reads_state_and_overrides(tmp_path):
    prop = _make_layout(tmp_path)
    (prop / "state.yml").write_text(
        "property_id: 1011-verrado\n"
        "owner_email: matt@example.com\n",
        encoding="utf-8",
    )
    (prop / "SOP.overrides.yml").write_text(
        "overrides:\n"
        "  P-04:\n"
        "    grace_period_days: 3\n",
        encoding="utf-8",
    )
    tenants = prop / "tenants"
    tenants.mkdir()
    (tenants / "beautiful-minds-a-101.yml").write_text(
        "slug: beautiful-minds-a-101\n"
        "primary_contact: office@beautifulmind.example\n",
        encoding="utf-8",
    )

    bundle = load_sop_bundle(prop)
    assert bundle.company_state["property_id"] == "1011-verrado"
    assert bundle.overrides["overrides"]["P-04"]["grace_period_days"] == 3
    assert bundle.extra_context["tenants"][0]["slug"] == "beautiful-minds-a-101"


def test_render_company_context_block_is_deterministic(tmp_path):
    """Cache stability requires byte-identical output across runs for same inputs."""
    prop = _make_layout(tmp_path)
    bundle = load_sop_bundle(prop)
    a = render_company_context_block(bundle)
    b = render_company_context_block(bundle)
    assert a == b


def test_load_message_validates_required_fields(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"id": "x"}', encoding="utf-8")  # missing 'from' and 'body'
    with pytest.raises(ValueError, match="missing required field"):
        load_message(p)


def test_discover_inbox_messages_returns_sorted_json_files(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "z.json").write_text("{}", encoding="utf-8")
    (inbox / "a.json").write_text("{}", encoding="utf-8")
    (inbox / "ignored.txt").write_text("nope", encoding="utf-8")
    files = discover_inbox_messages(inbox)
    assert [f.name for f in files] == ["a.json", "z.json"]


def test_discover_inbox_messages_returns_empty_for_missing_dir(tmp_path):
    assert discover_inbox_messages(tmp_path / "nope") == []
