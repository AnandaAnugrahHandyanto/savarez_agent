from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from gateway.image2_feishu_ingress import (
    Image2IngressSettings,
    enqueue_feishu_job,
    launch_image2_worker,
    load_image2_ingress_settings,
)


def test_image2_settings_default_to_profile_owned_runtime_not_marketing_hub(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "config.yaml").write_text(
        "image2_feishu_ingress:\n"
        "  enabled: true\n"
        "  launch_worker: true\n",
        encoding="utf-8",
    )

    settings = load_image2_ingress_settings(profile_home=profile, environ={"PATH": ""})

    assert settings.runtime_root == profile / "runtime" / "image2"
    assert settings.db_path == profile / "runtime" / "image2" / "image2_jobs.sqlite"
    assert "marketing-hub" not in str(settings.runtime_root)
    assert not getattr(settings, "marketing_hub_root", None)


def test_config_cannot_enable_legacy_marketing_hub_sidecar_without_explicit_legacy_flag(tmp_path):
    profile = tmp_path / "profile"
    legacy = tmp_path / "marketing-hub"
    profile.mkdir()
    (profile / "config.yaml").write_text(
        "image2_feishu_ingress:\n"
        "  enabled: true\n"
        f"  marketing_hub_root: {legacy}\n"
        "  launch_worker: true\n",
        encoding="utf-8",
    )

    settings = load_image2_ingress_settings(profile_home=profile, environ={"PATH": ""})

    assert settings.enabled is False
    assert settings.launch_worker is False
    assert settings.runtime_root == profile / "runtime" / "image2"
    assert settings.db_path == profile / "runtime" / "image2" / "image2_jobs.sqlite"
    assert getattr(settings, "legacy_disabled_reason", "")


def test_legacy_marketing_hub_runtime_paths_are_ignored_and_fail_closed(tmp_path):
    profile = tmp_path / "profile"
    legacy_runtime = tmp_path / "runtime-pack" / "workspaces" / "marketing-hub" / "runtime-data" / "image-jobs"
    profile.mkdir()
    (profile / "config.yaml").write_text(
        "image2_feishu_ingress:\n"
        "  enabled: true\n"
        f"  runtime_root: {legacy_runtime}\n"
        f"  db_path: {legacy_runtime / 'image2_jobs.sqlite'}\n"
        f"  log_dir: {legacy_runtime / 'worker-logs'}\n"
        "  launch_worker: true\n",
        encoding="utf-8",
    )

    settings = load_image2_ingress_settings(profile_home=profile, environ={"PATH": ""})

    assert settings.enabled is False
    assert settings.launch_worker is False
    assert settings.runtime_root == profile / "runtime" / "image2"
    assert settings.db_path == profile / "runtime" / "image2" / "image2_jobs.sqlite"
    assert "marketing-hub" not in str(settings.log_dir)
    assert getattr(settings, "legacy_disabled_reason", "")


def test_enqueue_feishu_job_uses_hermes_job_store_not_marketing_hub_subprocess(tmp_path):
    runtime = tmp_path / "runtime"
    settings = Image2IngressSettings(
        enabled=True,
        runtime_root=runtime,
        db_path=runtime / "image2_jobs.sqlite",
        log_dir=runtime / "worker-logs",
    )
    called = []

    def forbidden_runner(cmd, **kwargs):
        called.append((cmd, kwargs))
        raise AssertionError("enqueue must not shell out to marketing-hub scripts")

    result = enqueue_feishu_job(
        settings,
        {"feishu_message_id": "om", "chat_id": "oc", "root_id": "root", "thread_id": "root", "text": "做海报"},
        runner=forbidden_runner,
    )

    assert result["task_id"].startswith("img2_")
    assert result["status"] == "ack_sent"
    assert result["already_existed"] is False
    assert called == []
    assert settings.db_path.exists()
    job_dir = runtime / result["task_id"]
    assert (job_dir / "message.json").is_file()
    assert json.loads((job_dir / "message.json").read_text(encoding="utf-8"))["text"] == "做海报"


def test_enqueue_feishu_job_is_idempotent_and_does_not_resurrect_terminal_jobs(tmp_path):
    runtime = tmp_path / "runtime"
    settings = Image2IngressSettings(enabled=True, runtime_root=runtime, db_path=runtime / "image2_jobs.sqlite")
    payload = {"feishu_message_id": "om-dup", "chat_id": "oc", "root_id": "root", "thread_id": "root", "text": "做海报"}
    first = enqueue_feishu_job(settings, payload)
    with sqlite3.connect(str(settings.db_path)) as conn:
        conn.execute(
            "UPDATE image2_jobs SET status = 'failed_final', worker_id = 'worker-1', claimed_at = '2026-04-29T00:00:00+00:00', completed_at = '2026-04-29T00:01:00+00:00', last_error = 'terminal' WHERE task_id = ?",
            (first["task_id"],),
        )

    second = enqueue_feishu_job(settings, payload)

    assert second["task_id"] == first["task_id"]
    assert second["already_existed"] is True
    assert second["status"] == "failed_final"
    with sqlite3.connect(str(settings.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (first["task_id"],)).fetchone())
    assert row["status"] == "failed_final"
    assert row["worker_id"] == "worker-1"
    assert row["claimed_at"] == "2026-04-29T00:00:00+00:00"
    assert row["completed_at"] == "2026-04-29T00:01:00+00:00"
    assert row["last_error"] == "terminal"


def test_launch_worker_uses_hermes_worker_module_not_marketing_hub_script(tmp_path):
    runtime = tmp_path / "runtime"
    settings = Image2IngressSettings(
        enabled=True,
        launch_worker=True,
        runtime_root=runtime,
        db_path=runtime / "image2_jobs.sqlite",
        log_dir=tmp_path / "logs",
        python_executable="pythonX",
    )
    launched = {}

    class FakePopen:
        pid = 123

        def __init__(self, cmd, **kwargs):
            launched["cmd"] = cmd
            launched["kwargs"] = kwargs
            launched["stdout"] = kwargs["stdout"]
            launched["stderr"] = kwargs["stderr"]

    info = launch_image2_worker(settings, task_id="img2_abc", popen=FakePopen)

    assert info["pid"] == 123
    joined_cmd = " ".join(launched["cmd"])
    assert "image2_browser_worker.py" not in joined_cmd
    assert "marketing-hub" not in joined_cmd
    assert launched["cmd"][:3] == ["pythonX", "-m", "gateway.image2_worker"]
    assert "--task-id" in launched["cmd"]
    assert launched["cmd"][launched["cmd"].index("--task-id") + 1] == "img2_abc"
    assert launched["stdout"].closed is True
    assert launched["stderr"].closed is True
    assert "marketing-hub/scripts" not in launched["kwargs"]["env"].get("PYTHONPATH", "")
