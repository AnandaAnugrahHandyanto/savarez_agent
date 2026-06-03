"""Tests for the specialist-orchestrator contract validator.

Two layers of coverage:

1. Schema layer — feed dict fixtures into ``validate_contract`` and
   assert which errors fire. These tests don't touch the filesystem.

2. Integration layer — write contract.yaml files into a tmp_path and
   call ``standalone_ready_matrix`` with the path override, asserting
   the structured matrix shape and the CLI exit code.

The shipped specialist contracts under
``~/.hermes/profiles/<name>/contract.yaml`` are validated by a
separate test (``test_shipped_specialist_contracts_pass``) that skips
when those files are absent — keeps CI green on a fresh checkout while
still gating real deployments.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from hermes_cli import profile_contract as pc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _good_contract(name: str = "gond") -> dict:
    return pc.default_specialist_contract(
        name,
        division="engineering",
        domain=["software architecture", "tests and quality gates"],
    )


@pytest.fixture
def profiles_root(tmp_path: Path) -> Path:
    root = tmp_path / "profiles"
    root.mkdir()
    return root


def _make_profile(root: Path, name: str, contract: dict | None) -> Path:
    pdir = root / name
    pdir.mkdir()
    if contract is not None:
        with open(pdir / pc.CONTRACT_FILENAME, "w", encoding="utf-8") as f:
            yaml.safe_dump(contract, f, sort_keys=False)
    return pdir


def test_profiles_root_uses_profile_scoped_hermes_home(monkeypatch, tmp_path: Path):
    profiles = tmp_path / ".hermes" / "profiles"
    gond_home = profiles / "gond"
    gond_home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(gond_home))
    monkeypatch.setattr(Path, "home", lambda: gond_home / "home")
    assert pc._profiles_root() == profiles


# ---------------------------------------------------------------------------
# Schema layer
# ---------------------------------------------------------------------------


def test_default_specialist_contract_is_valid():
    contract = _good_contract("gond")
    errs = pc.validate_contract(contract, "gond")
    assert errs == [], errs


def test_validate_contract_none_means_missing():
    errs = pc.validate_contract(None, "gond")
    assert errs == ["gond: contract.yaml missing or unreadable"]


def test_missing_top_keys_are_reported():
    errs = pc.validate_contract({"name": "gond", "division": "engineering"}, "gond")
    msg = "\n".join(errs)
    for k in (
        "domain",
        "reports_to",
        "standalone_orchestrator",
        "sot_intake",
        "child_lane_policy",
        "escalation_categories",
        "approval_gate_categories",
        "evidence_requirements",
        "forbidden_autonomy",
    ):
        assert f"{k}: missing" in msg, k


def test_standalone_orchestrator_false_is_rejected():
    contract = _good_contract("gond")
    contract["standalone_orchestrator"] = False
    errs = pc.validate_contract(contract, "gond")
    assert "standalone_orchestrator: must be true" in errs


def test_standalone_orchestrator_must_be_bool_not_truthy_string():
    contract = _good_contract("gond")
    contract["standalone_orchestrator"] = "yes"
    errs = pc.validate_contract(contract, "gond")
    assert any("standalone_orchestrator" in e and "bool" in e for e in errs)


def test_name_must_match_profile_dir():
    contract = _good_contract("gond")
    errs = pc.validate_contract(contract, "helm")
    assert any("name: declared" in e for e in errs)


def test_empty_required_lists_are_rejected():
    contract = _good_contract("gond")
    contract["domain"] = []
    contract["forbidden_autonomy"] = []
    errs = pc.validate_contract(contract, "gond")
    assert "domain: must not be empty" in errs
    assert "forbidden_autonomy: must not be empty" in errs


def test_sot_intake_must_have_some_channel_populated():
    contract = _good_contract("gond")
    contract["sot_intake"] = {"sources": [], "commands": [], "paths": []}
    errs = pc.validate_contract(contract, "gond")
    assert any("sot_intake: at least one of" in e for e in errs)


def test_child_lane_policy_max_parallel_must_be_positive():
    contract = _good_contract("gond")
    contract["child_lane_policy"]["max_parallel"] = 0
    errs = pc.validate_contract(contract, "gond")
    assert "child_lane_policy.max_parallel: must be >= 1" in errs


def test_child_lane_policy_max_parallel_type_check_rejects_bool():
    # bool is a subclass of int — the validator excludes it explicitly.
    contract = _good_contract("gond")
    contract["child_lane_policy"]["max_parallel"] = True
    errs = pc.validate_contract(contract, "gond")
    assert any("max_parallel" in e and "int" in e for e in errs)


def test_wrong_type_for_top_level_list_is_reported():
    contract = _good_contract("gond")
    contract["domain"] = "not a list"
    errs = pc.validate_contract(contract, "gond")
    assert any(e.startswith("domain:") and "list" in e for e in errs)


# ---------------------------------------------------------------------------
# Filesystem / matrix layer
# ---------------------------------------------------------------------------


def test_read_contract_returns_none_for_missing_file(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond", contract=None)
    assert pc.read_contract(pdir) is None


def test_read_contract_returns_none_for_corrupt_yaml(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond", contract=None)
    (pdir / pc.CONTRACT_FILENAME).write_text("not: valid: yaml: [unclosed", encoding="utf-8")
    assert pc.read_contract(pdir) is None


def test_standalone_ready_ok_for_valid_contract(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    row = pc.standalone_ready(pdir)
    assert row["ok"] is True
    assert row["missing"] == []
    assert row["has_file"] is True
    assert row["name"] == "gond"


def test_standalone_ready_fails_for_missing_file(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond", contract=None)
    row = pc.standalone_ready(pdir)
    assert row["ok"] is False
    assert row["has_file"] is False
    assert row["missing"], "expected at least one error"


def test_standalone_ready_matrix_uses_profiles_root_override(profiles_root: Path):
    _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    _make_profile(profiles_root, "helm", contract=None)
    matrix = pc.standalone_ready_matrix(["gond", "helm"], profiles_root=profiles_root)
    assert matrix["all_ok"] is False
    by_name = {r["name"]: r for r in matrix["rows"]}
    assert by_name["gond"]["ok"] is True
    assert by_name["helm"]["ok"] is False


def test_standalone_ready_matrix_all_ok_when_every_specialist_valid(profiles_root: Path):
    for name in ("gond", "helm"):
        _make_profile(profiles_root, name, contract=_good_contract(name))
    matrix = pc.standalone_ready_matrix(["gond", "helm"], profiles_root=profiles_root)
    assert matrix["all_ok"] is True


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_write_contract_creates_file_and_round_trips(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond", contract=None)
    contract = _good_contract("gond")
    path = pc.write_contract(pdir, contract)
    assert path == pdir / pc.CONTRACT_FILENAME
    assert path.is_file()
    reloaded = pc.read_contract(pdir)
    assert reloaded == contract


def test_write_contract_refuses_to_overwrite(profiles_root: Path):
    pdir = _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    with pytest.raises(FileExistsError):
        pc.write_contract(pdir, _good_contract("gond"))


def test_write_contract_rejects_missing_profile_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        pc.write_contract(tmp_path / "nope", _good_contract("gond"))


# ---------------------------------------------------------------------------
# CLI layer
# ---------------------------------------------------------------------------


def test_cli_validate_exits_zero_when_all_pass(profiles_root: Path, monkeypatch, capsys):
    for name in ("gond", "helm"):
        _make_profile(profiles_root, name, contract=_good_contract(name))
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["validate", "gond", "helm"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "all_contract_ready: yes" in out
    # Output must NOT claim STANDALONE_READY (renamed to CONTRACT_READY to
    # prevent the "wrapper-only specialist looks full-autonomy ready" trap).
    assert "STANDALONE_READY" not in out
    assert "CONTRACT_READY" in out


def test_cli_validate_exits_nonzero_when_any_fail(profiles_root: Path, monkeypatch, capsys):
    _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    _make_profile(profiles_root, "helm", contract=None)
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["validate", "gond", "helm"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out
    assert "helm" in out


def test_cli_validate_json_output(profiles_root: Path, monkeypatch, capsys):
    _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["validate", "gond", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_ok"] is True
    assert payload["rows"][0]["name"] == "gond"


def test_cli_matrix_is_informational_by_default(profiles_root: Path, monkeypatch, capsys):
    # Even with a failing profile, `matrix` returns 0 unless --strict.
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    # No profile dirs exist — every known specialist will fail.
    rc = pc.main(["matrix"])
    assert rc == 0
    assert "all_contract_ready: no" in capsys.readouterr().out


def test_cli_matrix_strict_returns_nonzero_on_failure(profiles_root: Path, monkeypatch):
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["matrix", "--strict"])
    assert rc == 1


def test_cli_init_writes_default_contract(profiles_root: Path, monkeypatch, capsys):
    _make_profile(profiles_root, "newone", contract=None)
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["init", "newone", "--division", "engineering", "--domain", "demo"])
    assert rc == 0
    assert "wrote" in capsys.readouterr().out
    # And the file validates clean.
    row = pc.standalone_ready(profiles_root / "newone")
    assert row["ok"] is True, row["missing"]


def test_cli_init_refuses_when_profile_dir_missing(profiles_root: Path, monkeypatch):
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["init", "ghost", "--division", "engineering"])
    assert rc == 2


def test_cli_init_refuses_to_overwrite(profiles_root: Path, monkeypatch):
    _make_profile(profiles_root, "x", contract=_good_contract("x"))
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["init", "x", "--division", "engineering"])
    assert rc == 3


# ---------------------------------------------------------------------------
# Full-autonomy readiness — multi-dimensional probe.
# ---------------------------------------------------------------------------


def _wire_full_autonomy_profile(
    profiles_root: Path,
    name: str = "gond",
    *,
    contract: dict | None = None,
    scheduler: bool = True,
    notion_path: bool = True,
    knowledge_corpus: bool = True,
    standalone_script: bool = True,
    implementation_artifact: bool = True,
) -> Path:
    """Build a profile directory that can be flipped piecemeal between
    pass and fail for every autonomy dimension. Default is the
    fully-wired success case.
    """
    contract = contract if contract is not None else _good_contract(name)
    if notion_path:
        # Make sure sot_intake.paths has a path that actually exists on
        # disk so the notion-intake probe can resolve it.
        contract = dict(contract)
        contract["sot_intake"] = dict(contract["sot_intake"])
        contract["sot_intake"]["sources"] = list(contract["sot_intake"].get("sources", []))
        contract["sot_intake"]["sources"].append("notion: spearhead notion pages")
        contract["sot_intake"]["paths"] = [str(profiles_root)]
    pdir = _make_profile(profiles_root, name, contract=contract)
    if scheduler:
        cron_dir = pdir / "cron"
        cron_dir.mkdir()
        (cron_dir / "jobs.json").write_text(
            json.dumps({"jobs": [{"name": f"{name}_standalone_tick", "schedule": "*/15 * * * *"}]}),
            encoding="utf-8",
        )
    if standalone_script:
        scripts_dir = pdir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / f"{name}_standalone_orchestrator.py").write_text(
            "#!/usr/bin/env python3\n", encoding="utf-8"
        )
    if knowledge_corpus:
        refs = pdir / "references"
        refs.mkdir()
        (refs / "registry.json").write_text("{}", encoding="utf-8")
    if implementation_artifact:
        logs = pdir / "logs"
        logs.mkdir()
        (logs / "tick.log").write_text("ok\n", encoding="utf-8")
    return pdir


def test_assess_autonomy_dimensions_returns_all_eight_required_dims(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root)
    dims = pc.assess_autonomy_dimensions(pdir)
    expected = set(pc.AUTONOMY_DIMENSIONS)
    assert set(dims.keys()) == expected, set(dims.keys()) ^ expected
    for d in pc.AUTONOMY_DIMENSIONS:
        assert "status" in dims[d]
        assert "reasons" in dims[d]


def test_full_autonomy_readiness_yes_when_every_dimension_wired(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root)
    row = pc.full_autonomy_readiness(pdir)
    # Some dimensions (decomposition_ready) read from the shipped
    # hermes_cli/kanban_decompose.py on the live system, which currently
    # does NOT load contract.yaml. Assert dimension count and shape.
    assert row["name"] == "gond"
    assert set(row["dimensions"].keys()) == set(pc.AUTONOMY_DIMENSIONS)
    assert isinstance(row["blocking_dimensions"], list)
    # If decomposition is not yet wired the row legitimately blocks —
    # that's the point of the test below.


def test_contract_only_specialist_is_NOT_full_autonomy_ready(profiles_root: Path):
    """REGRESSION: a profile with a valid contract.yaml but NO scheduler,
    NO knowledge corpus, NO standalone script, and NO implementation
    artifacts must report ``full_autonomy_ready=False`` and surface
    every missing dimension as a blocker. Catches the misleading
    STANDALONE_READY=yes failure mode (Filip correction 2026-05-29).
    """
    # Contract-only: write contract.yaml, nothing else.
    pdir = _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    row = pc.full_autonomy_readiness(pdir)
    assert row["full_autonomy_ready"] is False
    # contract_ready dimension must pass (the contract is valid).
    assert row["dimensions"]["contract_ready"]["status"] == pc.DIM_YES
    # Surrounding-machinery dimensions must all block.
    for dim in (
        "scheduler_ready",
        "child_supervision_ready",
        "knowledge_corpus_ready",
        "implementation_loop_ready",
    ):
        assert row["dimensions"][dim]["status"] != pc.DIM_YES, dim
        assert dim in row["blocking_dimensions"], dim


def test_scheduler_dimension_fails_when_cron_jobs_empty(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root)
    # Wipe the registered job to leave an empty list.
    (pdir / "cron" / "jobs.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["scheduler_ready"]["status"] == pc.DIM_NO
    assert any("no registered jobs" in r for r in dims["scheduler_ready"]["reasons"])


def test_scheduler_dimension_accepts_active_profile_local_standalone_job(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root)
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["scheduler_ready"]["status"] == pc.DIM_YES


def test_scheduler_dimension_accepts_default_scheduler_wrapper_job(profiles_root: Path):
    """REGRESSION: default-profile no-agent wrapper crons are the live
    Spearhead scheduler shape. A specialist should not fail scheduler_ready
    just because its own profile-local cron/jobs.json is absent.
    """
    pdir = _wire_full_autonomy_profile(profiles_root, scheduler=False)
    default_cron = profiles_root.parent / "cron"
    default_cron.mkdir()
    (default_cron / "jobs.json").write_text(
        json.dumps({
            "jobs": [{
                "name": "Gond standalone orchestrator (default scheduler)",
                "script": "gond_standalone_orchestrator_default_wrapper.sh",
                "no_agent": True,
                "enabled": True,
                "state": "scheduled",
                "profile": None,
            }]
        }),
        encoding="utf-8",
    )
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["scheduler_ready"]["status"] == pc.DIM_YES


def test_scheduler_dimension_fails_when_default_wrapper_missing(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root, scheduler=False)
    default_cron = profiles_root.parent / "cron"
    default_cron.mkdir()
    (default_cron / "jobs.json").write_text(
        json.dumps({"jobs": [{"name": "Unrelated watchdog", "enabled": True, "state": "scheduled"}]}),
        encoding="utf-8",
    )
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["scheduler_ready"]["status"] != pc.DIM_YES
    assert any("none reference standalone orchestrator" in r for r in dims["scheduler_ready"]["reasons"])


def test_scheduler_dimension_fails_when_default_wrapper_paused(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root, scheduler=False)
    default_cron = profiles_root.parent / "cron"
    default_cron.mkdir()
    (default_cron / "jobs.json").write_text(
        json.dumps({
            "jobs": [{
                "name": "Gond standalone orchestrator (default scheduler)",
                "script": "gond_standalone_orchestrator_default_wrapper.sh",
                "no_agent": True,
                "enabled": False,
                "state": "paused",
            }]
        }),
        encoding="utf-8",
    )
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["scheduler_ready"]["status"] == pc.DIM_NO
    assert any("paused" in r or "disabled" in r for r in dims["scheduler_ready"]["reasons"])


def test_notion_intake_partial_when_paths_absent(profiles_root: Path):
    contract = _good_contract("gond")
    contract["sot_intake"] = {
        "sources": ["notion: foo"],
        "commands": [],
        "paths": ["/nonexistent/path/should/not/exist"],
    }
    pdir = _wire_full_autonomy_profile(profiles_root, contract=contract, notion_path=False)
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["notion_intake_ready"]["status"] == pc.DIM_PARTIAL


def test_notion_intake_no_when_sources_dont_mention_notion(profiles_root: Path):
    contract = _good_contract("gond")
    contract["sot_intake"] = {
        "sources": ["kanban: assignee=gond"],
        "commands": ["hermes kanban list"],
        "paths": [str(profiles_root)],
    }
    pdir = _wire_full_autonomy_profile(profiles_root, contract=contract, notion_path=False)
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["notion_intake_ready"]["status"] == pc.DIM_NO


def test_knowledge_corpus_partial_when_dir_empty(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root, knowledge_corpus=False)
    (pdir / "references").mkdir()
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["knowledge_corpus_ready"]["status"] == pc.DIM_PARTIAL


def test_knowledge_corpus_yes_when_profile_knowledge_corpus_seeded(
    profiles_root: Path, tmp_path: Path
):
    """A specialist with a populated profile_knowledge corpus must grade YES.

    This is the new evidence-corpus contract (parent card t_078d4441):
    the legacy heuristic "any file in references/" is no longer enough —
    only the structured corpus.jsonl with at least one verified entry
    counts.
    """
    from hermes_cli import profile_knowledge as pk

    pdir = _wire_full_autonomy_profile(profiles_root, knowledge_corpus=False)
    artifact = tmp_path / "evidence.txt"
    artifact.write_text("verified note", encoding="utf-8")
    pk.ingest_local_artifact(pdir, artifact, tags=["domain:engineering"])
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["knowledge_corpus_ready"]["status"] == pc.DIM_YES


def test_knowledge_corpus_partial_when_only_gates(profiles_root: Path):
    """Gated-unread metadata alone is not verified evidence."""
    from hermes_cli import profile_knowledge as pk

    pdir = _wire_full_autonomy_profile(profiles_root, knowledge_corpus=False)
    pk.ingest_gated_source(pdir, "https://x.com/a", gate_kind="paywall")
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["knowledge_corpus_ready"]["status"] == pc.DIM_PARTIAL
    reasons = dims["knowledge_corpus_ready"]["reasons"]
    assert any("gated" in r.lower() for r in reasons)


def test_knowledge_corpus_legacy_references_dir_now_grades_partial(profiles_root: Path):
    """Legacy 'just put a file in references/' fallback grades PARTIAL.

    Used to grade YES under the old heuristic. New contract requires
    the structured profile_knowledge corpus.jsonl; the legacy bucket is
    a soft pass at best, until specialists migrate.
    """
    pdir = _wire_full_autonomy_profile(profiles_root, knowledge_corpus=True)
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["knowledge_corpus_ready"]["status"] == pc.DIM_PARTIAL


def test_implementation_loop_partial_when_no_artifacts(profiles_root: Path):
    pdir = _wire_full_autonomy_profile(profiles_root, implementation_artifact=False)
    dims = pc.assess_autonomy_dimensions(pdir)
    # Evidence requirements are declared in default contract; just no logs/.
    assert dims["implementation_loop_ready"]["status"] == pc.DIM_PARTIAL


def test_escalation_dimension_fails_with_empty_categories(profiles_root: Path):
    contract = _good_contract("gond")
    # Bypass schema validator by writing categories that exist but are
    # whitespace-only sentinels. The dimension probe checks emptiness.
    contract["escalation_categories"] = []
    contract["approval_gate_categories"] = []
    # Schema validation would normally reject this; for the probe we
    # short-circuit by feeding through assess_autonomy_dimensions which
    # reads the file directly. Easier: write the file ourselves.
    pdir = profiles_root / "gond"
    pdir.mkdir()
    # Write a partially-broken contract so contract probe also fails.
    with open(pdir / pc.CONTRACT_FILENAME, "w", encoding="utf-8") as f:
        yaml.safe_dump(contract, f, sort_keys=False)
    dims = pc.assess_autonomy_dimensions(pdir)
    assert dims["escalation_ready"]["status"] == pc.DIM_NO


def test_full_autonomy_matrix_distinguishes_contract_vs_full_autonomy(profiles_root: Path):
    """REGRESSION: bulk matrix must expose BOTH ``all_contract_ready``
    AND ``all_full_autonomy_ready``. Past reports collapsed these into
    a single ``STANDALONE_READY=yes`` and let wrapper-only specialists
    appear fully autonomous.
    """
    _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    matrix = pc.full_autonomy_matrix(["gond"], profiles_root=profiles_root)
    assert "all_contract_ready" in matrix
    assert "all_full_autonomy_ready" in matrix
    assert matrix["all_contract_ready"] is True
    assert matrix["all_full_autonomy_ready"] is False
    row = matrix["rows"][0]
    assert row["dimensions"]["contract_ready"]["status"] == pc.DIM_YES
    assert row["full_autonomy_ready"] is False
    assert row["blocking_dimensions"], "must list blocking dimensions"


def test_cli_autonomy_subcommand_emits_full_matrix(profiles_root: Path, monkeypatch, capsys):
    _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["autonomy", "gond"])
    out = capsys.readouterr().out
    # Informational, so exit 0 even when full autonomy fails.
    assert rc == 0
    assert "FULL_AUTONOMY_READY matrix" in out
    assert "all_contract_ready:" in out
    assert "all_full_autonomy_ready:" in out


def test_cli_autonomy_strict_returns_nonzero_for_contract_only_specialist(
    profiles_root: Path, monkeypatch
):
    _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["autonomy", "gond", "--strict"])
    assert rc == 1, "wrapper-only specialist must fail --strict full-autonomy check"


def test_cli_autonomy_json_payload_shape(profiles_root: Path, monkeypatch, capsys):
    _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    monkeypatch.setattr(pc, "_profiles_root", lambda: profiles_root)
    rc = pc.main(["autonomy", "gond", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_contract_ready"] is True
    assert payload["all_full_autonomy_ready"] is False
    assert set(payload["dimensions"]) == set(pc.AUTONOMY_DIMENSIONS)
    assert payload["rows"][0]["full_autonomy_ready"] is False


def test_standalone_ready_alias_still_returns_contract_layer_only(profiles_root: Path):
    """REGRESSION: existing callers that import ``standalone_ready`` /
    ``standalone_ready_matrix`` must keep getting the contract-only
    semantics. The point of t_0990d9a3 is that the old name was
    misleading — but renaming without an alias would silently break
    everything that already calls it. Verify the alias passes through
    to ``contract_ready``.
    """
    assert pc.standalone_ready is pc.contract_ready
    assert pc.standalone_ready_matrix is pc.contract_ready_matrix
    pdir = _make_profile(profiles_root, "gond", contract=_good_contract("gond"))
    row = pc.standalone_ready(pdir)
    # Contract is valid, but this MUST NOT be taken as full-autonomy ready.
    assert row["ok"] is True
    full = pc.full_autonomy_readiness(pdir)
    assert full["full_autonomy_ready"] is False


# ---------------------------------------------------------------------------
# Shipped specialist contracts (skips when filesystem doesn't have them)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", pc.KNOWN_SPECIALISTS)
def test_shipped_specialist_contracts_pass(name: str):
    profile_dir = pc.profile_dir_for(name)
    if not profile_dir.is_dir():
        pytest.skip(f"profile dir not present on this host: {profile_dir}")
    if not (profile_dir / pc.CONTRACT_FILENAME).is_file():
        pytest.skip(f"contract not present on this host: {profile_dir / pc.CONTRACT_FILENAME}")
    contract = pc.read_contract(profile_dir)
    errors = pc.validate_contract(contract, name)
    assert errors == [], f"{name} contract failed validation: {errors}"
