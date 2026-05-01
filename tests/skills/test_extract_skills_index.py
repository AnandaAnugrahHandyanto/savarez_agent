import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "website" / "scripts" / "extract-skills.py"
OUTPUT_PATH = REPO_ROOT / "website" / "src" / "data" / "skills.json"


def load_extract_skills_module():
    spec = importlib.util.spec_from_file_location("extract_skills_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_skills_emits_optional_high_value_entries(tmp_path: Path, monkeypatch):
    mod = load_extract_skills_module()
    monkeypatch.setattr(mod, "OUTPUT", str(tmp_path / "skills.json"))

    mod.main()

    data = json.loads((tmp_path / "skills.json").read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in data}

    assert by_name["agentmail"]["source"] == "optional"
    assert by_name["fastmcp"]["source"] == "built-in"
    assert by_name["domain-intel"]["source"] == "built-in"
    assert by_name["honcho"]["source"] == "built-in"
    assert by_name["docker-management"]["source"] == "built-in"
    assert by_name["siyuan"]["source"] == "optional"
    assert by_name["agentmail"]["category"] in {"email", "other"}
    assert by_name["siyuan"]["category"] == "productivity"
    assert "mcp" in {tag.lower() for tag in by_name["agentmail"]["tags"]}


def test_extract_skills_includes_external_high_value_candidates(tmp_path: Path, monkeypatch):
    mod = load_extract_skills_module()
    monkeypatch.setattr(mod, "OUTPUT", str(tmp_path / "skills.json"))

    mod.main()

    data = json.loads((tmp_path / "skills.json").read_text(encoding="utf-8"))
    names = {item["name"]: item for item in data}

    assert names["webapp-testing"]["source"] == "Anthropic"
    assert names["mcp-builder"]["source"] == "Anthropic"
    assert names["doc-coauthoring"]["source"] == "Anthropic"
    assert "playwright" in names["webapp-testing"]["description"].lower()
    assert "model context protocol" in names["mcp-builder"]["description"].lower()


def test_extract_skills_emits_curated_role_and_workflow_metadata(tmp_path: Path, monkeypatch):
    mod = load_extract_skills_module()
    output = tmp_path / "skills.json"
    curation = tmp_path / "skill-curation.json"
    monkeypatch.setattr(mod, "OUTPUT", str(output))
    monkeypatch.setattr(mod, "CURATION_OUTPUT", str(curation))

    mod.main()

    skills = json.loads(output.read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in skills}
    curation_payload = json.loads(curation.read_text(encoding="utf-8"))

    assert "coding" in by_name["github-pr-workflow"]["roles"]
    assert "build-review-ship" in by_name["github-pr-workflow"]["workflows"]
    assert by_name["github-pr-workflow"]["useCases"] == ["starter"]

    assert "communication" in by_name["himalaya"]["roles"]
    assert "docs" in by_name["himalaya"]["roles"]
    assert "investigate-write-share" in by_name["himalaya"]["workflows"]

    role_shelves = {item["id"]: item for item in curation_payload["roleShelves"]}
    workflow_shelves = {item["id"]: item for item in curation_payload["workflowShelves"]}
    starter_packs = {item["id"]: item for item in curation_payload["starterPacks"]}

    assert "github-pr-workflow" in role_shelves["coding"]["names"]
    assert "himalaya" in role_shelves["communication"]["names"]
    assert "github-pr-workflow" in workflow_shelves["build-review-ship"]["names"]
    assert starter_packs["coding-starter"]["names"][0] == "systematic-debugging"
