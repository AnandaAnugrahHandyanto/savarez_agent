import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "website" / "scripts" / "skills_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("skills_inventory_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_inventory_report_includes_expected_local_skill_flags(tmp_path: Path):
    mod = load_module()
    out_json = tmp_path / "inventory.json"
    out_md = tmp_path / "inventory.md"

    rc = mod.main(["--json", str(out_json), "--markdown", str(out_md)])
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))

    assert payload["summary"]["local_total"] >= 120
    by_name = {item["name"]: item for item in payload["skills"]}

    assert by_name["docx"]["source"] == "built-in"
    assert by_name["docx"]["has_verification_section"] is True
    assert by_name["docx"]["has_pitfalls_section"] is True
    assert by_name["docx"]["quality_tier"] in {"D2", "D3", "D4"}

    assert by_name["domain-intel"]["source"] == "built-in"
    assert by_name["domain-intel"]["has_scripts"] is True
    assert by_name["domain-intel"]["quality_tier"] in {"D1", "D2", "D3", "D4"}
    assert by_name["fastmcp"]["source"] == "built-in"
    assert by_name["honcho"]["source"] == "built-in"
    assert by_name["docker-management"]["source"] == "built-in"

    markdown = out_md.read_text(encoding="utf-8")
    assert "# Hermes Skills Inventory" in markdown
    assert "## Source Summary" in markdown


def test_inventory_detects_tests_for_recently_covered_skills(tmp_path: Path):
    mod = load_module()
    out_json = tmp_path / "inventory.json"

    rc = mod.main(["--json", str(out_json)])
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in payload["skills"]}

    assert by_name["agentmail"]["has_tests"] is True
    assert by_name["siyuan"]["has_tests"] is True
    assert by_name["telephony"]["has_tests"] is True


def test_inventory_marks_promotion_candidates_consistently(tmp_path: Path):
    mod = load_module()
    out_json = tmp_path / "inventory.json"

    rc = mod.main(["--json", str(out_json)])
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in payload["skills"]}

    assert by_name["fastmcp"]["promotion_candidate"] is False
    assert by_name["honcho"]["promotion_candidate"] is False
    assert by_name["docker-management"]["promotion_candidate"] is False
    assert by_name["domain-intel"]["promotion_candidate"] is False
    assert by_name["duckduckgo-search"]["promotion_candidate"] is False
    assert by_name["docx"]["promotion_candidate"] is False


def test_runtime_inventory_marks_imported_variants_as_deprecated_duplicates(tmp_path: Path):
    mod = load_module()
    out_json = tmp_path / "inventory.json"
    runtime_json = tmp_path / "runtime.json"
    compat_md = tmp_path / "compat.md"

    rc = mod.main([
        "--json", str(out_json),
        "--runtime-json", str(runtime_json),
        "--compat-markdown", str(compat_md),
    ])
    assert rc == 0

    payload = json.loads(runtime_json.read_text(encoding="utf-8"))
    items = payload["skills"]
    imported = [item for item in items if item["path"] == "openclaw-imports/lark-base-imported"]
    assert len(imported) == 1
    assert imported[0]["status"] == "deprecated"
    assert imported[0]["duplicateOf"] == "lark-base"
    assert imported[0]["variant"] == "imported"

    primary = [item for item in items if item["path"] == "openclaw-imports/lark-base"]
    assert len(primary) == 1
    assert primary[0]["status"] == "active"
    assert primary[0]["variant"] == "primary"

    alias_stock = [item for item in items if item["path"] == "openclaw-imports/stock-team-strategy"]
    assert len(alias_stock) == 1
    assert alias_stock[0]["name"] == "a-stock-team-strategy"
    assert alias_stock[0]["status"] == "deprecated"
    assert alias_stock[0]["duplicateOf"] == "stock-team-strategy"
    assert alias_stock[0]["variant"] == "primary"

    alias_self = [item for item in items if item["path"] == "openclaw-imports/self-improving"]
    assert len(alias_self) == 1
    assert alias_self[0]["name"] == "Self-Improving + Proactive Agent"
    assert alias_self[0]["status"] == "deprecated"
    assert alias_self[0]["duplicateOf"] == "self-improving"
    assert alias_self[0]["variant"] == "primary"

    summary = payload["summary"]
    assert summary["physical_total"] == 175
    assert summary["effective_total"] == 156
    assert summary["archived_total"] == 19
    assert summary["by_status"]["deprecated"] >= 26
    assert summary["duplicates"] >= 27

    compat_text = compat_md.read_text(encoding="utf-8")
    assert "Compatibility imported/duplicate variants" in compat_text
    assert "| `lark-base` | imported | deprecated | lark-base | `openclaw-imports/lark-base-imported` |" in compat_text
    assert "| `a-stock-team-strategy` | primary | deprecated | stock-team-strategy | `openclaw-imports/stock-team-strategy` |" in compat_text
    assert "| `Self-Improving + Proactive Agent` | primary | deprecated | self-improving | `openclaw-imports/self-improving` |" in compat_text
