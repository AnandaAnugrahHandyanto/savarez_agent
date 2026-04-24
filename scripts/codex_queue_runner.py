#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import smtplib
import ssl
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import codex_account_manager as cam

APP_NAME = "codex-queue-runner"
DEFAULT_STATE_DIR = Path(os.getenv("CODEX_QUEUE_STATE_DIR", str(Path.home() / ".hermes" / "codex_queue")))
DEFAULT_STATE_FILE = DEFAULT_STATE_DIR / "state.json"
DEFAULT_LOG_DIR = DEFAULT_STATE_DIR / "logs"
DEFAULT_NOTIFY_EMAIL = os.getenv("CODEX_QUEUE_NOTIFY_EMAIL", "")
DEFAULT_WORKDIR = os.getenv("CODEX_QUEUE_WORKDIR", str(Path.cwd()))
QUOTA_PATTERNS = [
    "quota",
    "insufficient_quota",
    "billing_hard_limit_reached",
    "rate limit",
    "rate_limit",
    "usage limit",
    "limit reached",
    "too many requests",
    "429",
    "credit balance is too low",
    "request was rejected because your organization is out of credits",
]
AUTH_PATTERNS = [
    "invalid api key",
    "authentication",
    "unauthorized",
    "expired",
    "login required",
    "not logged in",
]


@dataclass
class QueuePaths:
    state_file: Path
    log_dir: Path


class QueueError(Exception):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_paths(state_file: Path) -> QueuePaths:
    state_file = state_file.expanduser().resolve()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    log_dir = state_file.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if not state_file.exists():
        write_state(
            state_file,
            {
                "paused": False,
                "pause_reason": None,
                "notify_email": DEFAULT_NOTIFY_EMAIL,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "queue": [],
                "history": [],
                "last_alerts": {},
            },
        )
    return QueuePaths(state_file=state_file, log_dir=log_dir)


def read_state(state_file: Path) -> dict[str, Any]:
    ensure_paths(state_file)
    with state_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_state(state_file: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    tmp = state_file.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(state_file)


def normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    task.setdefault("id", uuid.uuid4().hex[:12])
    task.setdefault("status", "queued")
    task.setdefault("created_at", now_iso())
    task.setdefault("updated_at", now_iso())
    task.setdefault("attempts", 0)
    task.setdefault("workdir", DEFAULT_WORKDIR)
    task.setdefault("env", {})
    task.setdefault("metadata", {})
    task.setdefault("last_error", None)
    task.setdefault("log_file", None)
    return task


def add_task(state_file: Path, command: str, workdir: str, name: str | None, env_pairs: list[str]) -> dict[str, Any]:
    state = read_state(state_file)
    env = parse_env_pairs(env_pairs)
    task = normalize_task(
        {
            "command": command,
            "workdir": workdir or DEFAULT_WORKDIR,
            "name": name or command[:80],
            "env": env,
        }
    )
    state["queue"].append(task)
    write_state(state_file, state)
    return task


def parse_env_pairs(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise QueueError(f"无效环境变量参数: {item}，应为 KEY=VALUE")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


def find_task(state: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for collection_name in ("queue", "history"):
        for task in state.get(collection_name, []):
            if task.get("id") == task_id:
                return task
    return None


def set_pause(state_file: Path, paused: bool, reason: str | None) -> dict[str, Any]:
    state = read_state(state_file)
    state["paused"] = paused
    state["pause_reason"] = reason if paused else None
    write_state(state_file, state)
    return state


def detect_failure_kind(output: str, returncode: int) -> tuple[str | None, str | None]:
    haystack = output.lower()
    if any(p in haystack for p in QUOTA_PATTERNS):
        return "quota", "检测到额度/频率限制，队列已自动暂停"
    if any(p in haystack for p in AUTH_PATTERNS):
        return "auth", "检测到认证失败，队列已自动暂停"
    if returncode != 0:
        return "command_failed", "命令执行失败"
    return None, None


def is_codex_command(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return command.strip().startswith("codex ") or command.strip() == "codex"
    return bool(parts) and Path(parts[0]).name == "codex"


def finalize_round_summary(task: dict[str, Any], workdir: Path) -> dict[str, Any]:
    summary_path = workdir / "plans" / "trs-logwhisperer-v2" / "LATEST_ROUND_SUMMARY.md"
    result: dict[str, Any] = {
        "path": str(summary_path),
        "exists": summary_path.exists(),
        "updated": False,
    }
    if not summary_path.exists():
        result["reason"] = "missing"
        return result

    text = summary_path.read_text(encoding="utf-8")
    task_id = str(task.get("id") or "")
    started_at = str(task.get("started_at") or "")
    workdir_str = str(workdir)
    if task_id not in text or started_at not in text or workdir_str not in text:
        result["reason"] = "identity_mismatch"
        return result

    finished_at = str(task.get("finished_at") or "")
    finished_display = finished_at
    if not finished_at:
        result["reason"] = "missing_finished_at"
        return result

    new_text, replaced = re.subn(
        r"(^- `finished_at`: `)([^`]*)(`\s*$)",
        rf"\g<1>{finished_display}\g<3>",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if replaced == 0:
        new_text, replaced = re.subn(
            r"(^finished_at=)(.+)$",
            rf"\g<1>{finished_display}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    if replaced == 0:
        bullet_marker = f"- `CODEX_QUEUE_TASK_WORKDIR`: `{workdir_str}`"
        plain_marker = f"CODEX_QUEUE_TASK_WORKDIR={workdir_str}"
        replacement_bullet = bullet_marker + f"\n- `finished_at`: `{finished_display}`"
        replacement_plain = plain_marker + f"\nfinished_at={finished_display}"
        if bullet_marker in text:
            new_text = text.replace(bullet_marker, replacement_bullet, 1)
        elif plain_marker in text:
            new_text = text.replace(plain_marker, replacement_plain, 1)
        else:
            result["reason"] = "finished_marker_insert_failed"
            return result

    new_text = re.sub(r"(?m)^finished_at=.*(?:\nfinished_at=.*)+$", f"finished_at={finished_display}", new_text)
    new_text = re.sub(r"(?m)^- `finished_at`: `[^`]*`(?:\n- `finished_at`: `[^`]*`)+$", f"- `finished_at`: `{finished_display}`", new_text)
    new_text = re.sub(r"(?m)^(finished_at=.*)\n- `finished_at`: `[^`]*`$", r"\1", new_text)
    new_text = re.sub(r"(?m)^(- `finished_at`: `[^`]*`)\nfinished_at=.*$", r"\1", new_text)

    if new_text != text:
        summary_path.write_text(new_text, encoding="utf-8")
        result["updated"] = True
    os.utime(summary_path, None)
    result["mtime"] = datetime.fromtimestamp(summary_path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return result


def _git_run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def maybe_auto_commit_and_push(task: dict[str, Any], workdir: Path, env: dict[str, str]) -> dict[str, Any]:
    enabled = str(env.get("CODEX_AUTO_GIT_PUSH", "")).strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"enabled": False, "reason": "disabled"}

    result: dict[str, Any] = {"enabled": True, "workdir": str(workdir)}
    inside = _git_run(["rev-parse", "--is-inside-work-tree"], workdir)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        result["reason"] = "not_git_repo"
        result["stderr"] = (inside.stderr or inside.stdout).strip()
        return result

    status = _git_run(["status", "--porcelain"], workdir)
    if status.returncode != 0:
        result["reason"] = "status_failed"
        result["stderr"] = (status.stderr or status.stdout).strip()
        return result

    changed_files = [line for line in status.stdout.splitlines() if line.strip()]
    result["changed_files"] = changed_files
    if not changed_files:
        result["reason"] = "clean_worktree"
        return result

    add_proc = _git_run(["add", "-A"], workdir)
    if add_proc.returncode != 0:
        result["reason"] = "git_add_failed"
        result["stderr"] = (add_proc.stderr or add_proc.stdout).strip()
        return result

    branch_proc = _git_run(["branch", "--show-current"], workdir)
    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else ""
    if not branch:
        branch = env.get("CODEX_AUTO_GIT_BRANCH", "").strip() or "master"
    result["branch"] = branch

    remote_proc = _git_run(["config", "--get", f"branch.{branch}.remote"], workdir)
    remote = remote_proc.stdout.strip() if remote_proc.returncode == 0 else ""
    if not remote:
        remotes_proc = _git_run(["remote"], workdir)
        remotes = [line.strip() for line in remotes_proc.stdout.splitlines() if line.strip()]
        if "github" in remotes:
            remote = "github"
        elif "origin" in remotes:
            remote = "origin"
        elif len(remotes) == 1:
            remote = remotes[0]
    result["remote"] = remote
    if not remote:
        result["reason"] = "missing_remote"
        return result

    task_name = str(task.get("name") or "").strip()
    task_suffix = f" {task_name}" if task_name else ""
    commit_message = env.get("CODEX_AUTO_GIT_COMMIT_MESSAGE", "").strip() or f"chore(codex): auto-commit {task.get('id')}{task_suffix}"
    result["commit_message"] = commit_message

    commit_proc = _git_run(
        [
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            commit_message,
        ],
        workdir,
    )
    commit_output = ((commit_proc.stdout or "") + ("\n" if commit_proc.stdout and commit_proc.stderr else "") + (commit_proc.stderr or "")).strip()
    result["commit_output"] = commit_output
    if commit_proc.returncode != 0:
        result["reason"] = "git_commit_failed"
        return result

    push_proc = _git_run(["push", remote, branch], workdir)
    push_output = ((push_proc.stdout or "") + ("\n" if push_proc.stdout and push_proc.stderr else "") + (push_proc.stderr or "")).strip()
    result["push_output"] = push_output
    if push_proc.returncode != 0:
        result["reason"] = "git_push_failed"
        return result

    head_proc = _git_run(["rev-parse", "HEAD"], workdir)
    result["commit"] = head_proc.stdout.strip() if head_proc.returncode == 0 else None
    result["reason"] = "committed_and_pushed"
    return result


def run_task_with_auto_switch(
    command: str,
    *,
    notify_email: str | None = None,
    max_switches: int | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    stream_output: bool = False,
    event_callback=None,
) -> tuple[int, str]:
    return cam.execute_command_with_auto_switch(
        command,
        notify_email=notify_email,
        max_switches=max_switches,
        cwd=cwd,
        env=env,
        stream_output=stream_output,
        event_callback=event_callback,
    )


def send_email(subject: str, body: str, to_email: str) -> None:
    qq_script = Path("/root/.hermes/bin/send_qq.py")
    qq_cfg = Path.home() / ".config" / "openclaw-mail" / "qq_smtp.json"
    qq_pass = Path.home() / ".config" / "openclaw-mail" / "qq_smtp.pass"

    if qq_script.exists() and qq_cfg.exists() and qq_pass.exists():
        proc = subprocess.run(
            [
                sys.executable,
                str(qq_script),
                "--to",
                to_email,
                "--subject",
                subject,
                "--body",
                body,
            ],
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise QueueError(f"QQ 邮件脚本发送失败: {(proc.stderr or proc.stdout).strip()}")
        return

    address = os.getenv("EMAIL_ADDRESS", "")
    password = os.getenv("EMAIL_PASSWORD", "")
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    if not all([address, password, smtp_host, to_email]):
        raise QueueError("邮件环境未配置完整，且未找到可用 QQ 发件脚本")

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = to_email

    smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
    try:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(address, password)
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            smtp.close()


def maybe_alert(state: dict[str, Any], state_file: Path, alert_key: str, subject: str, body: str, notify_email: str | None) -> None:
    notify_email = notify_email or state.get("notify_email") or DEFAULT_NOTIFY_EMAIL
    if not notify_email:
        return
    sent_at = state.get("last_alerts", {}).get(alert_key)
    if sent_at:
        return
    send_email(subject, body, notify_email)
    state.setdefault("last_alerts", {})[alert_key] = now_iso()
    write_state(state_file, state)


def clear_alert(state: dict[str, Any], state_file: Path, alert_key: str) -> None:
    if state.get("last_alerts", {}).pop(alert_key, None):
        write_state(state_file, state)


def get_process_command_lines() -> list[str]:
    proc = subprocess.run(
        ["ps", "-eo", "args="],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def task_runtime_signature(task: dict[str, Any]) -> list[str]:
    command = str(task.get("command") or "")
    workdir = str(task.get("workdir") or "")
    signatures: list[str] = []
    if workdir:
        signatures.append(workdir)
    if "codex exec" in command:
        signatures.append("codex exec")
    elif command:
        signatures.append(command[:160])
    return signatures


def is_task_process_alive(task: dict[str, Any], process_lines: list[str] | None = None) -> bool:
    process_lines = process_lines or get_process_command_lines()
    signatures = task_runtime_signature(task)
    if not signatures:
        return False
    for line in process_lines:
        if all(signature in line for signature in signatures):
            return True
    return False


def recover_stale_running_tasks(state_file: Path, state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    recovered: list[str] = []
    process_lines = get_process_command_lines()
    changed = False
    for task in state.get("queue", []):
        if task.get("status") != "running":
            continue
        if is_task_process_alive(task, process_lines=process_lines):
            continue
        task["status"] = "queued"
        task["last_error"] = "recovered_from_stale_running_state"
        task["started_at"] = None
        task["finished_at"] = None
        task["duration_seconds"] = None
        task["returncode"] = None
        task["updated_at"] = now_iso()
        recovered.append(str(task.get("id") or "unknown"))
        changed = True
    if changed:
        write_state(state_file, state)
    return state, recovered


def run_next(state_file: Path, notify_email: str | None = None) -> int:
    paths = ensure_paths(state_file)
    state = read_state(state_file)
    if state.get("paused"):
        print(f"队列已暂停: {state.get('pause_reason') or '未说明原因'}")
        return 2

    state, recovered = recover_stale_running_tasks(state_file, state)
    if recovered:
        print(f"已自动回收 stale running 任务: {', '.join(recovered)}")

    active_running = next((t for t in state.get("queue", []) if t.get("status") == "running"), None)
    if active_running:
        print(f"run-next skip: active task id={active_running.get('id')}")
        return 0

    queued = next((t for t in state.get("queue", []) if t.get("status") == "queued"), None)
    if not queued:
        print("队列为空，没有可执行任务。")
        return 0

    queued["status"] = "running"
    queued["started_at"] = now_iso()
    queued["attempts"] = int(queued.get("attempts", 0)) + 1
    log_file = paths.log_dir / f"{queued['id']}.log"
    queued["log_file"] = str(log_file)
    write_state(state_file, state)

    env = os.environ.copy()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ):
        value = os.environ.get(key)
        if value:
            env[key] = value
    env.update(queued.get("env", {}))
    env["CODEX_QUEUE_TASK_ID"] = str(queued.get("id", ""))
    env["CODEX_QUEUE_TASK_NAME"] = str(queued.get("name", ""))
    env["CODEX_QUEUE_TASK_STARTED_AT"] = str(queued.get("started_at", ""))
    workdir = Path(queued.get("workdir") or DEFAULT_WORKDIR).expanduser()
    env["CODEX_QUEUE_TASK_WORKDIR"] = str(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    transient_events: list[dict[str, Any]] = []

    def event_callback(event: dict[str, Any]) -> None:
        transient_events.append({**event, "at": now_iso()})

    command = queued["command"]
    start = time.time()
    if is_codex_command(command):
        returncode, output = run_task_with_auto_switch(
            command,
            notify_email=notify_email,
            cwd=str(workdir),
            env=env,
            stream_output=False,
            event_callback=event_callback,
        )
    else:
        proc = subprocess.run(
            command,
            cwd=str(workdir),
            env=env,
            shell=True,
            text=True,
            capture_output=True,
        )
        returncode = proc.returncode
        output = (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")
    duration = round(time.time() - start, 2)
    log_file.write_text(output, encoding="utf-8")

    failure_kind, failure_reason = detect_failure_kind(output, returncode)
    queued["finished_at"] = now_iso()
    queued["duration_seconds"] = duration
    queued["returncode"] = returncode
    queued["updated_at"] = now_iso()
    if is_codex_command(command):
        queued["summary_finalize"] = finalize_round_summary(queued, workdir)
        queued["git_sync"] = maybe_auto_commit_and_push(queued, workdir, env)
        if queued["git_sync"].get("reason") == "git_push_failed":
            failure_kind = "command_failed"
            failure_reason = "git push 失败"
        elif queued["git_sync"].get("reason") == "git_commit_failed":
            failure_kind = "command_failed"
            failure_reason = "git commit 失败"
        elif queued["git_sync"].get("reason") == "git_add_failed":
            failure_kind = "command_failed"
            failure_reason = "git add 失败"
    if transient_events:
        queued["transient_events"] = transient_events
        queued["transient_retry_count"] = sum(1 for event in transient_events if event.get("type") == "transient_retry")
        last_switch = next((event for event in reversed(transient_events) if event.get("type") == "transient_switch"), None)
        if last_switch:
            queued["last_account_switch"] = {
                "reason": "transient_reconnect",
                "from_account_id": last_switch.get("from_account_id"),
                "from_account_label": last_switch.get("from_account_label"),
                "to_account_id": last_switch.get("to_account_id"),
                "to_account_label": last_switch.get("to_account_label"),
                "at": last_switch.get("at"),
            }
    queued["updated_at"] = now_iso()

    if failure_kind is None:
        queued["status"] = "done"
        queued["last_error"] = None
        state["history"].append(dict(queued))
        state["queue"] = [t for t in state["queue"] if t.get("id") != queued.get("id")]
        clear_alert(state, state_file, "queue_paused")
        write_state(state_file, state)
        print(f"任务完成: {queued['id']} ({duration}s)")
        return 0

    queued["status"] = "paused" if failure_kind in {"quota", "auth"} else "failed"
    queued["last_error"] = failure_reason

    if failure_kind in {"quota", "auth"}:
        state["paused"] = True
        state["pause_reason"] = f"{failure_reason}；任务 {queued['id']} 已暂停"
        subject = f"[Codex队列提醒] {failure_reason}"
        body = (
            f"时间: {now_iso()}\n"
            f"原因: {failure_reason}\n"
            f"任务ID: {queued['id']}\n"
            f"任务名: {queued.get('name')}\n"
            f"工作目录: {queued.get('workdir')}\n"
            f"命令: {queued.get('command')}\n"
            f"日志: {queued.get('log_file')}\n"
            f"返回码: {returncode}\n"
        )
        try:
            maybe_alert(state, state_file, "queue_paused", subject, body, notify_email)
            queued["alert_sent"] = True
        except Exception as exc:
            queued["alert_sent"] = False
            queued["alert_error"] = str(exc)
    else:
        state["history"].append(dict(queued))
        state["queue"] = [t for t in state["queue"] if t.get("id") != queued.get("id")]

    write_state(state_file, state)
    print(f"任务失败: {queued['id']} ({failure_reason})")
    return returncode or 1


def cmd_status(state_file: Path) -> int:
    state = read_state(state_file)
    print(json.dumps({
        "paused": state.get("paused", False),
        "pause_reason": state.get("pause_reason"),
        "notify_email": state.get("notify_email"),
        "queued": [
            {
                "id": t.get("id"),
                "status": t.get("status"),
                "name": t.get("name"),
                "workdir": t.get("workdir"),
                "attempts": t.get("attempts"),
                "last_error": t.get("last_error"),
            }
            for t in state.get("queue", [])
        ],
        "history_count": len(state.get("history", [])),
        "updated_at": state.get("updated_at"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_resume(state_file: Path, clear_error: bool) -> int:
    state = read_state(state_file)
    state["paused"] = False
    state["pause_reason"] = None
    if clear_error:
        for task in state.get("queue", []):
            if task.get("status") == "paused":
                task["status"] = "queued"
                task["last_error"] = None
    clear_alert(state, state_file, "queue_paused")
    write_state(state_file, state)
    print("队列已恢复。")
    return 0


def cmd_set_email(state_file: Path, email: str) -> int:
    state = read_state(state_file)
    state["notify_email"] = email
    write_state(state_file, state)
    print(f"提醒邮箱已设置为: {email}")
    return 0


def cmd_retry(state_file: Path, task_id: str) -> int:
    state = read_state(state_file)
    task = find_task(state, task_id)
    if not task:
        raise QueueError(f"未找到任务: {task_id}")
    task_copy = dict(task)
    task_copy["id"] = uuid.uuid4().hex[:12]
    task_copy["status"] = "queued"
    task_copy["created_at"] = now_iso()
    task_copy["updated_at"] = now_iso()
    task_copy["started_at"] = None
    task_copy["finished_at"] = None
    task_copy["duration_seconds"] = None
    task_copy["returncode"] = None
    task_copy["last_error"] = None
    task_copy["log_file"] = None
    state["queue"].append(task_copy)
    write_state(state_file, state)
    print(f"已重新入队: {task_copy['id']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex 任务队列：失败暂停、人工恢复、邮件提醒。")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="状态文件路径")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="添加任务")
    p_add.add_argument("command_text", help="要执行的命令，例如: codex exec 'fix bug'")
    p_add.add_argument("--workdir", default=DEFAULT_WORKDIR, help="任务工作目录")
    p_add.add_argument("--name", default=None, help="任务显示名称")
    p_add.add_argument("--env", action="append", default=[], help="额外环境变量 KEY=VALUE，可重复")

    p_run = sub.add_parser("run-next", help="执行下一个排队任务")
    p_run.add_argument("--notify-email", default=None, help="本次运行覆盖提醒邮箱")

    sub.add_parser("status", help="查看状态")

    p_resume = sub.add_parser("resume", help="恢复队列")
    p_resume.add_argument("--clear-paused-tasks", action="store_true", help="把 paused 任务重置回 queued")

    p_email = sub.add_parser("set-email", help="设置提醒邮箱")
    p_email.add_argument("email", help="提醒邮箱地址")

    p_retry = sub.add_parser("retry", help="重试历史任务")
    p_retry.add_argument("task_id", help="历史或队列中的任务 ID")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    state_file = Path(args.state_file)
    ensure_paths(state_file)

    try:
        if args.command == "add":
            task = add_task(state_file, args.command_text, args.workdir, args.name, args.env)
            print(json.dumps(task, ensure_ascii=False, indent=2))
            return 0
        if args.command == "run-next":
            return run_next(state_file, notify_email=args.notify_email)
        if args.command == "status":
            return cmd_status(state_file)
        if args.command == "resume":
            return cmd_resume(state_file, clear_error=args.clear_paused_tasks)
        if args.command == "set-email":
            return cmd_set_email(state_file, args.email)
        if args.command == "retry":
            return cmd_retry(state_file, args.task_id)
        parser.error("未知命令")
        return 2
    except QueueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
