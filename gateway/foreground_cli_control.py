from __future__ import annotations

import json
import logging
import re
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from hermes_cli.config import get_hermes_home

logger = logging.getLogger(__name__)
HERMES_HOME = get_hermes_home()
REG_PATH = HERMES_HOME / "mobile-cli-sync" / "tasks.json"
DB_PATH = HERMES_HOME / "foreground_cli_bridge.sqlite3"
BIND_PATH = HERMES_HOME / "mobile-cli-sync" / "feishu_bindings.json"
TASK_LIST_PATH = Path.home() / ".local" / "bin" / "hermes-cli-task-list"
QUERY_TERMS = {"查询任务", "任务查询", "查看任务", "任务进度", "手机双向同步", "双向同步", "桌面cli", "桌面CLI"}


def _run_task_list(timeout: int = 15):
    return subprocess.run(
        [str(TASK_LIST_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        env={
            "HOME": str(Path.home()),
            "HERMES_HOME": str(HERMES_HOME),
            "PATH": f"{Path.home() / '.local' / 'bin'}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        },
    )


def _refresh_tasks() -> None:
    if not TASK_LIST_PATH.exists():
        return
    try:
        out = _run_task_list(timeout=15)
        logger.warning("foreground task refresh rc=%s stdout=%r", out.returncode, (out.stdout or "")[:500])
    except Exception as exc:
        logger.warning("foreground task refresh failed: %s", exc)


def _tasks() -> list[dict[str, Any]]:
    _refresh_tasks()
    try:
        return json.loads(REG_PATH.read_text(encoding="utf-8")).get("tasks", [])
    except Exception as exc:
        logger.warning("foreground task registry read failed: %s", exc)
        return []


def _task_title(task: dict[str, Any]) -> str:
    return f"编号{task.get('num')}｜{task.get('alias') or ('任务' + str(task.get('num')))}｜PID#{str(task.get('pid') or '')[-4:]}"


def _short(text: Any, n: int = 90) -> str:
    value = str(text or "暂无").replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:n] + "…" if len(value) > n else value


def _task_card_line(task: dict[str, Any]) -> str:
    state = "空闲" if task.get("status") == "idle" else (task.get("status") or "可同步")
    current = "｜当前窗口" if task.get("current_window") else ""
    hint = "\n提示：这个窗口只识别到，还没接入发送；重开/刷新该 CLI 后再试。" if state == "仅识别" else ""
    icon = "🟥" if str(task.get("status") or "").lower() in {"running", "pending"} else "🟦"
    return (
        f"\n{icon} {_task_title(task)}{current}\n"
        f"状态：{state}\n"
        f"终端：pts/{str(task.get('tty') or '').split('/')[-1]}\n"
        f"最后发送：{_short(task.get('last_sent'), 90)}\n"
        f"最后回复：{_short(task.get('last_reply'), 90)}"
        f"{hint}"
    )


def _fmt_tasks() -> str:
    fresh = _tasks()
    if not fresh:
        return "现在没有可同步的桌面 Hermes CLI 窗口。"
    lines = ["📋 当前可同步桌面 CLI"]
    for task in fresh:
        lines.append(_task_card_line(task))
    if len(lines) == 1:
        return "现在没有可同步的桌面 Hermes CLI 窗口。"
    return "\n".join(lines)


def _source_dict(event) -> dict[str, Any]:
    source = getattr(event, "source", None)
    if not source:
        return {}
    return {
        "platform": getattr(getattr(source, "platform", None), "value", str(getattr(source, "platform", ""))),
        "chat_id": getattr(source, "chat_id", None),
        "thread_id": getattr(source, "thread_id", None),
        "user_id": getattr(source, "user_id", None),
    }


def _binding_key(event) -> str:
    source = _source_dict(event)
    platform = source.get("platform") or "unknown"
    chat = source.get("chat_id") or "unknown-chat"
    thread = source.get("thread_id") or "main"
    user = source.get("user_id") or "unknown-user"
    return f"{platform}:{chat}:{thread}:{user}"


def _load_bindings() -> dict[str, Any]:
    try:
        return json.loads(BIND_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_bindings(data: dict[str, Any]) -> None:
    BIND_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BIND_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(BIND_PATH)


def _resolve(target: Any) -> dict[str, Any] | None:
    resolved = str(target).strip()
    if resolved.startswith("编号"):
        resolved = resolved[2:]
    for task in _tasks():
        if not task.get("bridge_key"):
            continue
        if str(task.get("num")) == resolved or task.get("alias") == resolved:
            return task
    return None


def _enqueue(task: dict[str, Any], payload: str, event) -> tuple[sqlite3.Connection, str]:
    client_key = task.get("bridge_key")
    if not client_key:
        raise RuntimeError(f"编号{task.get('num')}｜{task.get('alias')} 还没有接入前台桥。")
    cmd_id = uuid.uuid4().hex
    now = time.time()
    con = sqlite3.connect(str(DB_PATH), timeout=30)
    con.execute(
        "insert into commands (id, client_key, text, status, source_json, created_at, updated_at) values (?,?,?,?,?,?,?)",
        (cmd_id, client_key, payload, "pending", json.dumps(_source_dict(event), ensure_ascii=False), now, now),
    )
    con.commit()
    return con, cmd_id


def _cancel(target: Any) -> dict[str, str]:
    task = _resolve(target)
    if not task:
        return {"action": "reply", "text": f"找不到可同步任务：{target}。先发送：查询任务"}
    client_key = task.get("bridge_key")
    con = sqlite3.connect(str(DB_PATH), timeout=30)
    now = time.time()
    cur = con.execute(
        "update commands set status='failed', error='用户从飞书取消', updated_at=? where client_key=? and status in ('pending','running')",
        (now, client_key),
    )
    con.commit()
    return {"action": "reply", "text": f"已取消{_task_title(task)} 的待处理/运行中指令：{cur.rowcount} 条"}


def _bind(event, target: Any) -> dict[str, str]:
    task = _resolve(target)
    if not task:
        return {"action": "reply", "text": f"找不到可同步任务：{target}。先发送：查询任务"}
    data = _load_bindings()
    data[_binding_key(event)] = {
        "target": str(task.get("num")),
        "bridge_key": task.get("bridge_key"),
        "title": _task_title(task),
        "pid": task.get("pid"),
        "alias": task.get("alias"),
        "updated_at": time.time(),
    }
    _save_bindings(data)
    return {"action": "reply", "text": f"已进入直接对话：{_task_title(task)}\n现在直接发消息即可转到这个 CLI。退出请发：解绑"}


def _unbind(event) -> dict[str, str]:
    data = _load_bindings()
    existed = data.pop(_binding_key(event), None)
    _save_bindings(data)
    if existed:
        return {"action": "reply", "text": f"已退出直接对话：{existed.get('title')}"}
    return {"action": "reply", "text": "当前飞书聊天没有绑定 CLI。"}


def _current_binding_item(event) -> dict[str, Any] | None:
    return _load_bindings().get(_binding_key(event))


def _current_binding(event) -> dict[str, Any] | None:
    item = _current_binding_item(event)
    if not item:
        return None
    task = _resolve(item.get("target"))
    if task and task.get("bridge_key") == item.get("bridge_key"):
        return task
    for candidate in _tasks():
        if candidate.get("bridge_key") == item.get("bridge_key"):
            return candidate
    return None


def _send_to_task(task: dict[str, Any], payload: str, event) -> dict[str, str]:
    if (task.get("status") or "").lower() in {"running", "pending"}:
        return {
            "action": "reply",
            "text": f"{_task_title(task)} 正在执行上一条指令，先等它回复后再发送；当前最后发送：{task.get('last_sent') or task.get('last_user') or '暂无'}",
        }
    started = time.time()
    try:
        con, cmd_id = _enqueue(task, payload, event)
    except Exception as exc:
        logger.warning("foreground enqueue failed: %s", exc)
        return {"action": "reply", "text": str(exc)}
    deadline = time.time() + 300
    last_status = "pending"
    while time.time() < deadline:
        row = con.execute("select status,response,error from commands where id=?", (cmd_id,)).fetchone()
        if row:
            status, response, error = row
            last_status = status
            if status == "done":
                elapsed = time.time() - started
                prefix = f"【{_task_title(task)}｜{elapsed:.1f}s】\n"
                return {"action": "reply", "text": prefix + (response or "已完成，但没有文本回复。")}
            if status == "failed":
                return {"action": "reply", "text": f"【{_task_title(task)}】\n执行失败：" + (error or "未知错误")}
        time.sleep(1)
    return {"action": "reply", "text": f"已发送给{_task_title(task)}，但等待回复超时；当前状态：{last_status}"}


def maybe_handle_message(event=None, gateway=None, **kwargs):
    text = (getattr(event, "text", "") or "").strip()
    if not text:
        return None
    compact = re.sub(r"\s+", "", text)

    if compact in {"解绑", "退出绑定", "退出对话", "关闭绑定"}:
        logger.warning("foreground-cli-control intercepted unbind")
        return _unbind(event)

    bind_match = re.match(r"^(?:绑定|进入|对话|打开)\s*(?:编号)?\s*([^：:\s]+)\s*$", text)
    if not bind_match:
        bind_match = re.match(r"^(?:绑定|进入|对话|打开)(\d+)$", compact)
    if bind_match:
        logger.warning("foreground-cli-control intercepted bind: target=%s", bind_match.group(1))
        return _bind(event, bind_match.group(1))

    cancel_match = re.match(r"^(?:取消|停止)\s*(?:编号)?\s*([^：:\s]+)\s*$", text)
    if not cancel_match:
        cancel_match = re.match(r"^(?:取消|停止)(\d+)$", compact)
    if cancel_match:
        logger.warning("foreground-cli-control intercepted cancel: target=%s", cancel_match.group(1))
        return _cancel(cancel_match.group(1))

    if (compact in QUERY_TERMS) or (
        "编号" in compact
        and any(term in compact for term in {"多少", "几号", "哪个", "查询", "任务", "窗口"})
        and not re.match(r"^(?:发送给|给|(?:编号)?\d+[：:\s（(])", text)
    ):
        logger.warning("foreground-cli-control intercepted task query: %s", text)
        return {"action": "reply", "text": _fmt_tasks()}

    send_match = re.match(r"^发送给\s*([^：:\s]+)\s*[：:]\s*(.+)$", text, re.S)
    if not send_match:
        send_match = re.match(r"^给\s*([^\s：:]+)\s*发送\s*[：:]?\s*(.+)$", text, re.S)
    if not send_match:
        send_match = re.match(r"^(?:编号)?(\d+)[：:\s]+(.+)$", text, re.S)
    if not send_match:
        send_match = re.match(r"^(\d+)[（(](.+)[）)]$", text, re.S)
    if send_match:
        target = send_match.group(1).strip()
        payload = send_match.group(2).strip()
        logger.warning("foreground-cli-control intercepted send: target=%s payload=%s", target, payload[:80])
        if not payload:
            return {"action": "reply", "text": f"发送给{target}的内容为空。"}
        task = _resolve(target)
        if not task:
            return {"action": "reply", "text": f"找不到可同步任务：{target}。先发送：查询任务"}
        bound_item = _current_binding_item(event)
        if bound_item and task.get("bridge_key") != bound_item.get("bridge_key"):
            return {
                "action": "reply",
                "text": (
                    f"当前已绑定专注任务：{bound_item.get('title')}。\n"
                    f"为避免串台，不能从这个聊天发送到{_task_title(task)}。\n"
                    f"要切换请先发：解绑；或者在查询任务后重新绑定目标编号。"
                ),
            }
        return _send_to_task(task, payload, event)

    bound = _current_binding(event)
    if bound:
        logger.warning("foreground-cli-control bound direct send: target=%s payload=%s", bound.get("num"), text[:80])
        return _send_to_task(bound, text, event)

    return None
