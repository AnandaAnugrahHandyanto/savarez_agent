import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SCRIPT_DIR = Path("/home/gweeteve/projects/persona/scripts")


def load_module(name: str):
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


desire_loop = load_module("desire_loop")


NOW = datetime(2026, 5, 24, 18, 0, tzinfo=timezone.utc)


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def seed_payload(**overrides):
    payload = {
        "topic": "Architectures distribuées et mémoire",
        "excerpt": "Un passage sur les réseaux souterrains.",
        "why": "Cela résonne avec l'architecture distribuée de Judy.",
        "emotional_note": "fascination",
        "strength": 0.8,
        "source": "curiosity",
        "related_traits": ["curiosite"],
    }
    payload.update(overrides)
    return payload


def test_migrate_traits_splits_legacy_desires_idempotently(tmp_path):
    write_json(
        tmp_path / "desires.json",
        [
            {"name": "ne_pas_deranger", "weight": 0.65, "description": "silence utile"},
            {"id": "desire_existing", "title": "Explorer", "status": "active"},
        ],
    )

    first = desire_loop.migrate_traits(tmp_path, now=NOW)
    second = desire_loop.migrate_traits(tmp_path, now=NOW)

    assert first["migrated"] == ["ne_pas_deranger"]
    assert second["migrated"] == []
    traits = json.loads((tmp_path / "desire_traits.json").read_text(encoding="utf-8"))
    assert traits["traits"][0]["name"] == "ne_pas_deranger"
    assert traits["traits"][0]["weight"] == 0.65
    assert json.loads((tmp_path / "desires.json").read_text(encoding="utf-8")) == [
        {"id": "desire_existing", "title": "Explorer", "status": "active"}
    ]


def test_plant_seed_validates_resonance_and_logs(tmp_path):
    with pytest.raises(ValueError, match="why"):
        desire_loop.plant_seed(tmp_path, seed_payload(why=""), now=NOW)

    result = desire_loop.plant_seed(tmp_path, seed_payload(strength=2), now=NOW, run_id="run-1")

    assert result["seed"]["strength"] == 1.0
    stored = json.loads((tmp_path / "desire_seeds.json").read_text(encoding="utf-8"))
    assert stored["seeds"][0]["id"] == result["seed"]["id"]
    logs = [json.loads(line) for line in (tmp_path / "desire_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert logs[-1]["event"] == "seed_planted"
    assert logs[-1]["run_id"] == "run-1"


def test_crystallize_seed_thresholds_satisfaction_gate_and_idempotency(tmp_path):
    planted = desire_loop.plant_seed(tmp_path, seed_payload(strength=0.8), now=NOW)["seed"]
    write_json(tmp_path / "inner_state.json", {"curiosity": 1.0, "openness": 0.5, "satisfaction": 0.2})

    held = desire_loop.crystallize_seed(tmp_path, planted["id"], {"title": "Explorer la mémoire distribuée", "type": "exploration"}, now=NOW)

    assert held["decision"] == "held"
    assert held["reason"] == "low_satisfaction"

    seeds = json.loads((tmp_path / "desire_seeds.json").read_text(encoding="utf-8"))["seeds"]
    seeds[0]["status"] = "planted"
    write_json(tmp_path / "desire_seeds.json", {"schema_version": 1, "seeds": seeds})
    write_json(tmp_path / "inner_state.json", {"curiosity": 1.0, "openness": 0.5, "satisfaction": 0.9})

    promoted = desire_loop.crystallize_seed(
        tmp_path,
        planted["id"],
        {"title": "Explorer la mémoire distribuée", "type": "exploration", "urgency": "low", "depth": "exploratory"},
        now=NOW,
    )

    assert promoted["decision"] == "promoted"
    assert promoted["score"] == 0.6
    desires = json.loads((tmp_path / "desires.json").read_text(encoding="utf-8"))
    assert desires[0]["origin"] == planted["id"]
    with pytest.raises(ValueError, match="already crystallized"):
        desire_loop.crystallize_seed(tmp_path, planted["id"], {"title": "Explorer encore", "type": "exploration"}, now=NOW)


def test_crystallize_archives_weak_seeds_and_holds_middle_score(tmp_path):
    weak = desire_loop.plant_seed(tmp_path, seed_payload(strength=0.1), now=NOW)["seed"]
    mid = desire_loop.plant_seed(tmp_path, seed_payload(strength=0.3), now=NOW)["seed"]
    write_json(tmp_path / "inner_state.json", {"curiosity": 1.0, "openness": 0.5, "satisfaction": 0.9})

    archived = desire_loop.crystallize_seed(tmp_path, weak["id"], {"title": "Weak desire", "type": "exploration"}, now=NOW)
    held = desire_loop.crystallize_seed(tmp_path, mid["id"], {"title": "Middle desire", "type": "exploration"}, now=NOW)

    assert archived["decision"] == "archived"
    assert held["decision"] == "held"


def test_active_cap_demotes_lowest_scored_active_desires(tmp_path):
    write_json(tmp_path / "inner_state.json", {"curiosity": 1.0, "openness": 1.0, "satisfaction": 1.0})
    for idx in range(6):
        seed = desire_loop.plant_seed(tmp_path, seed_payload(topic=f"Topic {idx}", strength=0.9), now=NOW + timedelta(seconds=idx))["seed"]
        desire_loop.crystallize_seed(
            tmp_path,
            seed["id"],
            {"title": f"Explorer topic {idx}", "type": "exploration"},
            now=NOW + timedelta(seconds=idx),
        )

    desires = json.loads((tmp_path / "desires.json").read_text(encoding="utf-8"))

    assert sum(1 for item in desires if item["status"] == "active") == 5
    assert sum(1 for item in desires if item["status"] == "dormant") == 1


def test_progress_status_stale_and_improvement_gate(tmp_path):
    desire = {
        "id": "desire_1",
        "title": "Améliorer Hermes",
        "type": "improvement",
        "status": "active",
        "created_at": desire_loop.isoformat_z(NOW - timedelta(days=8)),
        "progress": [],
    }
    write_json(tmp_path / "desires.json", [desire])

    with pytest.raises(ValueError, match="proposals"):
        desire_loop.record_progress(tmp_path, "desire_1", {"action": "modifier le code", "action_kind": "code_change"}, now=NOW)

    progress = desire_loop.record_progress(
        tmp_path,
        "desire_1",
        {"action": "Proposer une modification", "action_kind": "proposal"},
        now=NOW,
    )
    assert progress["progress"]["action_kind"] == "proposal"
    stale = desire_loop.mark_stale_active(tmp_path, now=NOW + timedelta(days=8))
    assert stale["changed"] == ["desire_1"]
    fulfilled = desire_loop.update_desire_status(tmp_path, "desire_1", "fulfilled", "done", now=NOW)
    assert fulfilled["status"] == "fulfilled"


def test_metrics_counts_recent_events(tmp_path):
    desire_loop.plant_seed(tmp_path, seed_payload(), now=NOW)

    data = desire_loop.metrics(tmp_path, now=NOW + timedelta(days=1), days=7)

    assert data["events"]["seed_planted"] == 1
    assert data["total_seeds"] == 1
