#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


SCHEMA = "hermes.autonomy.crypto_bot_gitea_runner_recovery.v1"
RUNNER_NAME = "crypto-bot-linux-runner"
GITEA_CONTAINER = "crypto-bot-gitea"
RUNNER_IMAGE = "gitea/act_runner:0.2.12"
REPO_ROOT = Path(__file__).resolve().parents[1]
CI_JOB_IMAGE = "crypto-bot-ci-runner:python313-node20-go"
CI_JOB_IMAGE_DOCKERFILE = REPO_ROOT / "docker/crypto_bot_ci_runner/Dockerfile"
CI_JOB_IMAGE_LABEL = f"ubuntu-latest:docker://{CI_JOB_IMAGE}"
RUNNER_NETWORK = "crypto-bot-gitea-net"
RUNNER_VOLUME = "crypto-bot-linux-runner-data"
RUNNER_STATE_FILE = "/data/.runner"
RUNNER_CONFIG_FILE = "config.yaml"
RUNNER_CONFIG_PATH = f"/data/{RUNNER_CONFIG_FILE}"
RUNNER_JOB_CONTAINER_NETWORK = RUNNER_NETWORK
RUNNER_DAEMON_COMMAND = f"CONFIG_FILE={RUNNER_CONFIG_PATH} act_runner daemon --config {RUNNER_CONFIG_PATH}"
INSTANCE_URL = "http://crypto-bot-gitea:3000"
RUNNER_LABELS = f"linux,crypto-bot-python-313,{CI_JOB_IMAGE_LABEL}"
REPO_SCOPE = "preston/crypto_bot"
CI_JOB_IMAGE_LABEL_RE = re.compile(rf"(?<!\S){re.escape(CI_JOB_IMAGE_LABEL)}(?=\s|\])")
RUNNER_CONFIG_NETWORK_RE = re.compile(
    rf'(?m)^\s*network:\s*["\']?{re.escape(RUNNER_JOB_CONTAINER_NETWORK)}["\']?\s*$'
)
GITEA_CONFIG_PATH = "/data/gitea/conf/app.ini"
GITEA_WORK_PATH = "/data/gitea"
APPROVAL_PHRASE = (
    "APPROVE CRYPTO_BOT GITEA RUNNER RECOVERY "
    "container=crypto-bot-linux-runner "
    "network=crypto-bot-gitea-net "
    f"labels=linux,crypto-bot-python-313,{CI_JOB_IMAGE_LABEL} "
    f"ci_image={CI_JOB_IMAGE} "
    f"job_container_network={RUNNER_JOB_CONTAINER_NETWORK} "
    f"runner_config={RUNNER_CONFIG_PATH} "
    "no_workflow_dispatch=true "
    "no_pr_mutation=true "
    "no_merge=true"
)

CommandRunner = Callable[[list[str], int], dict[str, Any]]
SleepFn = Callable[[float], None]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def run_command(argv: list[str], timeout: int = 30) -> dict[str, Any]:
    proc = subprocess.run(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def command_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "exit_code": result.get("exit_code"),
        "stderr_tail": str(result.get("stderr") or "")[-500:],
    }


def render_runner_config() -> str:
    labels = "\n".join(f'    - "{label}"' for label in RUNNER_LABELS.split(","))
    return f"""log:
  level: info

runner:
  file: {RUNNER_STATE_FILE}
  capacity: 1
  envs: {{}}
  env_file: ""
  timeout: 3h
  shutdown_timeout: 0s
  insecure: false
  fetch_timeout: 5s
  fetch_interval: 2s
  labels:
{labels}

cache:
  enabled: true
  dir: ""
  host: ""
  port: 0
  external_server: ""

container:
  network: "{RUNNER_JOB_CONTAINER_NETWORK}"
  privileged: false
  options:
  workdir_parent:
  valid_volumes: []
  docker_host: ""
  force_pull: false
  force_rebuild: false

host:
  workdir_parent:
"""


def install_runner_config(
    *,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    config = render_runner_config()
    result = runner(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{RUNNER_VOLUME}:/data",
            "--entrypoint",
            "/bin/sh",
            RUNNER_IMAGE,
            "-c",
            f"cat > {RUNNER_CONFIG_PATH} <<'EOF'\n{config}EOF\n",
        ],
        30,
    )
    summary = command_summary(result)
    summary["config_path"] = RUNNER_CONFIG_PATH
    summary["job_container_network"] = RUNNER_JOB_CONTAINER_NETWORK
    summary["stdout_tail"] = str(result.get("stdout") or "")[-500:]
    return summary


def docker_inspect_exists(
    name: str,
    *,
    runner: CommandRunner = run_command,
) -> bool:
    result = runner(["docker", "container", "inspect", name], 20)
    return result["exit_code"] == 0


def inspect_runner(
    *,
    runner_name: str = RUNNER_NAME,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    ps = runner(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^{runner_name}$",
            "--format",
            "{{.Names}}\t{{.Status}}\t{{.Image}}",
        ],
        20,
    )
    logs = runner(["docker", "logs", "--tail", "80", runner_name], 20)
    config = runner(["docker", "exec", runner_name, "sh", "-lc", f"cat {RUNNER_CONFIG_PATH}"], 20)
    log_text = str(logs.get("stdout") or "") + str(logs.get("stderr") or "")
    config_text = str(config.get("stdout") or "")
    return {
        "container": runner_name,
        "docker_ps": str(ps.get("stdout") or "").strip(),
        "docker_ps_exit_code": ps.get("exit_code"),
        "docker_logs_exit_code": logs.get("exit_code"),
        "docker_config_exit_code": config.get("exit_code"),
        "runner_config_network_detected": bool(RUNNER_CONFIG_NETWORK_RE.search(config_text)),
        "token_empty_loop_detected": "token is empty" in log_text,
        "instance_empty_loop_detected": "instance address is empty" in log_text,
        "registered_successfully_detected": "Runner registered successfully" in log_text,
        "dedicated_ci_image_label_detected": bool(CI_JOB_IMAGE_LABEL_RE.search(log_text)),
        "host_ubuntu_latest_label_detected": "ubuntu-latest:host" in log_text,
        "recent_log_tail": log_text[-2000:],
    }


def generate_registration_token(
    *,
    runner: CommandRunner = run_command,
) -> tuple[str | None, dict[str, Any]]:
    result = runner(
        [
            "docker",
            "exec",
            "--user",
            "git",
            GITEA_CONTAINER,
            "/usr/local/bin/gitea",
            "--config",
            GITEA_CONFIG_PATH,
            "--work-path",
            GITEA_WORK_PATH,
            "actions",
            "generate-runner-token",
            "--scope",
            REPO_SCOPE,
        ],
        30,
    )
    stdout = str(result.get("stdout") or "")
    stdout_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    value = stdout_lines[-1] if stdout_lines else ""
    summary = command_summary(result)
    summary["stdout_line_count"] = len(stdout_lines)
    if result.get("exit_code") == 0 and value:
        summary["stdout_redacted"] = "[REDACTED_REGISTRATION_TOKEN]"
    elif stdout:
        summary["stdout_redacted"] = "[REDACTED_NON_TOKEN_OUTPUT]"
    else:
        summary["stdout_redacted"] = ""
    if result.get("exit_code") != 0:
        return None, summary
    return (value if value else None), summary


def build_ci_job_image(
    *,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    result = runner(
        [
            "docker",
            "build",
            "--pull",
            "-t",
            CI_JOB_IMAGE,
            "-f",
            str(CI_JOB_IMAGE_DOCKERFILE),
            str(CI_JOB_IMAGE_DOCKERFILE.parent),
        ],
        300,
    )
    summary = command_summary(result)
    summary["image"] = CI_JOB_IMAGE
    summary["dockerfile"] = str(CI_JOB_IMAGE_DOCKERFILE)
    summary["stdout_tail"] = str(result.get("stdout") or "")[-500:]
    return summary


def execute_recovery(
    *,
    approval_phrase: str | None,
    runner: CommandRunner = run_command,
    sleep_fn: SleepFn = time.sleep,
    wait_seconds: float = 8.0,
) -> dict[str, Any]:
    blockers: list[str] = []
    steps: list[dict[str, Any]] = []
    if approval_phrase != APPROVAL_PHRASE:
        blockers.append("exact_runner_recovery_approval_phrase_required")
        return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    image_step = build_ci_job_image(runner=runner)
    steps.append({"step": "build_dedicated_ci_job_image", **image_step})
    if image_step["exit_code"] != 0:
        blockers.append("dedicated_ci_job_image_build_failed")
        return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    token, token_step = generate_registration_token(runner=runner)
    steps.append({"step": "generate_registration_token", **token_step})
    if not token:
        blockers.append("runner_registration_token_generation_failed")
        return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    if docker_inspect_exists(RUNNER_NAME, runner=runner):
        result = runner(["docker", "rm", "-f", RUNNER_NAME], 30)
        steps.append({"step": "remove_existing_runner_container", **command_summary(result)})
        if result["exit_code"] != 0:
            blockers.append("unable_to_remove_existing_runner_container")
            return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    result = runner(["docker", "volume", "rm", "-f", RUNNER_VOLUME], 30)
    steps.append({"step": "reset_runner_volume_for_label_alignment", **command_summary(result)})
    if result["exit_code"] != 0:
        blockers.append("unable_to_reset_runner_volume")
        return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    result = runner(["docker", "volume", "create", RUNNER_VOLUME], 30)
    steps.append({"step": "ensure_runner_volume", **command_summary(result)})
    if result["exit_code"] != 0:
        blockers.append("unable_to_create_runner_volume")
        return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    config_step = install_runner_config(runner=runner)
    steps.append({"step": "install_runner_config", **config_step})
    if config_step["exit_code"] != 0:
        blockers.append("unable_to_install_runner_config")
        return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    run_args = [
        "docker",
        "run",
        "-d",
        "--name",
        RUNNER_NAME,
        "--network",
        RUNNER_NETWORK,
        "-v",
        f"{RUNNER_VOLUME}:/data",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-e",
        f"GITEA_INSTANCE_URL={INSTANCE_URL}",
        "-e",
        f"GITEA_RUNNER_REGISTRATION_TOKEN={token}",
        "-e",
        f"GITEA_RUNNER_NAME={RUNNER_NAME}",
        "-e",
        f"GITEA_RUNNER_LABELS={RUNNER_LABELS}",
        "-e",
        f"CONFIG_FILE={RUNNER_CONFIG_PATH}",
        RUNNER_IMAGE,
    ]
    result = runner(run_args, 60)
    run_summary = command_summary(result)
    run_summary["env_keys"] = [
        "GITEA_INSTANCE_URL",
        "GITEA_RUNNER_REGISTRATION_TOKEN",
        "GITEA_RUNNER_NAME",
        "GITEA_RUNNER_LABELS",
        "CONFIG_FILE",
    ]
    steps.append({"step": "start_runner_container", **run_summary})
    if result["exit_code"] != 0:
        blockers.append("unable_to_start_runner_container")
        return build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)

    sleep_fn(wait_seconds)
    report = build_report(mode="execute", blockers=blockers, steps=steps, runner=runner)
    post = report["runner_inspection"]
    if post["token_empty_loop_detected"]:
        report["blockers"].append("runner_still_reports_token_empty")
    if post["instance_empty_loop_detected"]:
        report["blockers"].append("runner_still_reports_instance_empty")
    report["conclusion"] = "FAIL" if report["blockers"] else "PASS"
    return report


def build_report(
    *,
    mode: str,
    blockers: list[str] | None = None,
    steps: list[dict[str, Any]] | None = None,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    blockers = blockers or []
    steps = steps or []
    report = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "mode": mode,
        "approval_phrase_required": APPROVAL_PHRASE,
        "runner_container": RUNNER_NAME,
        "gitea_container": GITEA_CONTAINER,
        "runner_image": RUNNER_IMAGE,
        "ci_job_image": CI_JOB_IMAGE,
        "ci_job_image_dockerfile": str(CI_JOB_IMAGE_DOCKERFILE),
        "ci_job_image_label": CI_JOB_IMAGE_LABEL,
        "runner_network": RUNNER_NETWORK,
        "runner_volume": RUNNER_VOLUME,
        "runner_state_file": RUNNER_STATE_FILE,
        "runner_config_path": RUNNER_CONFIG_PATH,
        "runner_job_container_network": RUNNER_JOB_CONTAINER_NETWORK,
        "runner_daemon_command": RUNNER_DAEMON_COMMAND,
        "runner_labels": RUNNER_LABELS,
        "repo_scope": REPO_SCOPE,
        "planned_env_keys": [
            "GITEA_INSTANCE_URL",
            "GITEA_RUNNER_REGISTRATION_TOKEN",
            "GITEA_RUNNER_NAME",
            "GITEA_RUNNER_LABELS",
            "CONFIG_FILE",
        ],
        "forbidden_env_keys": ["GITEA_RUNNER_TOKEN"],
        "runner_inspection": inspect_runner(runner=runner),
        "steps": steps,
        "blockers": blockers,
        "secrets_redacted": True,
        "workflow_dispatch_invoked": False,
        "pr_mutation_invoked": False,
        "merge_invoked": False,
        "direct_db_token_insertion_invoked": False,
    }
    report["conclusion"] = "FAIL" if blockers else "PASS"
    inspection = report["runner_inspection"]
    if inspection["host_ubuntu_latest_label_detected"]:
        report["blockers"].append("runner_host_mode_ubuntu_latest_label_detected")
        report["conclusion"] = "FAIL"
    elif (
        inspection["docker_ps_exit_code"] == 0
        and inspection["docker_logs_exit_code"] == 0
        and inspection["registered_successfully_detected"]
        and not inspection["dedicated_ci_image_label_detected"]
    ):
        report["blockers"].append("runner_dedicated_ci_image_label_not_detected")
        report["conclusion"] = "FAIL"
    elif (
        inspection["docker_ps_exit_code"] == 0
        and inspection["registered_successfully_detected"]
        and (
            inspection["docker_config_exit_code"] != 0
            or not inspection["runner_config_network_detected"]
        )
    ):
        report["blockers"].append("runner_job_container_network_not_configured")
        report["conclusion"] = "FAIL"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gated local Gitea act_runner recovery for crypto_bot."
    )
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-phrase")
    parser.add_argument("--wait-seconds", type=float, default=8.0)
    parser.add_argument("--format", choices=["json"], default="json")
    args = parser.parse_args()
    if args.inspect and args.execute:
        parser.error("choose either --inspect or --execute")
    if args.execute:
        report = execute_recovery(
            approval_phrase=args.approval_phrase,
            wait_seconds=args.wait_seconds,
        )
    else:
        report = build_report(mode="inspect")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
