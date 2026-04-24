#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

APP_NAME = "codex-windows-manager"


class ManagerError(Exception):
    pass


@dataclass
class StoredAccount:
    id: str
    label: str
    email: str
    access_token: str
    refresh_token: str
    id_token: str | None = None
    account_id: str | None = None
    source: str = "imported"
    created_at: str = ""
    updated_at: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _user_home() -> Path:
    userprofile = os.getenv("USERPROFILE", "").strip()
    if userprofile:
        return Path(userprofile)
    return Path.home()


def manager_root() -> Path:
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "CodexAccountManager"
    return _user_home() / "AppData" / "Roaming" / "CodexAccountManager"


def accounts_file() -> Path:
    return manager_root() / "accounts.json"


def state_file() -> Path:
    return manager_root() / "state.json"


def codex_auth_file() -> Path:
    codex_home = os.getenv("CODEX_HOME", "").strip()
    if codex_home:
        return Path(codex_home) / "auth.json"
    return _user_home() / ".codex" / "auth.json"


def _ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_accounts() -> list[StoredAccount]:
    path = accounts_file()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ManagerError("accounts.json 格式不正确。")
    return [StoredAccount(**item) for item in payload]


def save_accounts(accounts: Iterable[StoredAccount]) -> Path:
    path = _ensure_parent(accounts_file())
    payload = [asdict(item) for item in accounts]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_state() -> dict[str, Any]:
    path = state_file()
    if not path.exists():
        return {"active_account_id": None, "updated_at": now_iso()}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ManagerError("state.json 格式不正确。")
    payload.setdefault("active_account_id", None)
    payload.setdefault("updated_at", now_iso())
    return payload


def save_state(state: dict[str, Any]) -> Path:
    path = _ensure_parent(state_file())
    state = dict(state)
    state["updated_at"] = now_iso()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _decode_jwt_payload(token: str | None) -> dict[str, Any]:
    text = str(token or "").strip()
    if text.count(".") < 2:
        return {}
    payload = text.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _email_from_claims(payload: dict[str, Any]) -> str:
    candidates = [
        payload.get("email"),
        payload.get("upn"),
        payload.get("preferred_username"),
        (payload.get("https://api.openai.com/profile") or {}).get("email") if isinstance(payload.get("https://api.openai.com/profile"), dict) else None,
    ]
    for item in candidates:
        value = str(item or "").strip()
        if "@" in value:
            return value
    return ""


def detect_account_email(tokens: dict[str, Any]) -> str:
    for key in ("id_token", "access_token"):
        payload = _decode_jwt_payload(tokens.get(key))
        email = _email_from_claims(payload)
        if email:
            return email
    return ""


def read_codex_auth(path: Path | None = None) -> dict[str, Any]:
    auth_path = path or codex_auth_file()
    if not auth_path.exists():
        raise ManagerError(f"没找到 Codex 登录文件：{auth_path}")
    payload = json.loads(auth_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ManagerError("Codex auth.json 格式不正确。")
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise ManagerError("Codex auth.json 缺少 tokens。")
    if not tokens.get("access_token") or not tokens.get("refresh_token"):
        raise ManagerError("Codex auth.json 缺少 access_token / refresh_token。")
    return payload


def write_codex_auth(account: StoredAccount, path: Path | None = None) -> Path:
    auth_path = _ensure_parent(path or codex_auth_file())
    existing: dict[str, Any] = {}
    if auth_path.exists():
        try:
            loaded = json.loads(auth_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except Exception:
            existing = {}
    payload = dict(existing)
    tokens = dict(payload.get("tokens") or {})
    tokens["access_token"] = account.access_token
    tokens["refresh_token"] = account.refresh_token
    if account.id_token:
        tokens["id_token"] = account.id_token
    else:
        tokens.pop("id_token", None)
    if account.account_id:
        tokens["account_id"] = account.account_id
    else:
        tokens.pop("account_id", None)
    payload["tokens"] = tokens
    auth_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return auth_path


def resolve_account(accounts: list[StoredAccount], target: str | None) -> StoredAccount:
    if not accounts:
        raise ManagerError("当前没有已保存账号。")
    text = str(target or "").strip()
    if not text:
        raise ManagerError("请提供要操作的账号目标。")
    if text.isdigit():
        index = int(text) - 1
        if 0 <= index < len(accounts):
            return accounts[index]
    lowered = text.lower()
    for account in accounts:
        if account.id == text:
            return account
    for account in accounts:
        if account.email and account.email.lower() == lowered:
            return account
    for account in accounts:
        if account.label.lower() == lowered:
            return account
    raise ManagerError(f"找不到账号：{target}")


def upsert_account(account: StoredAccount) -> StoredAccount:
    accounts = load_accounts()
    lowered_email = account.email.lower() if account.email else ""
    updated_accounts: list[StoredAccount] = []
    replacement = account
    replaced = False
    for item in accounts:
        same_email = lowered_email and item.email.lower() == lowered_email
        same_id = item.id == account.id
        if same_email or same_id:
            replacement = StoredAccount(
                id=item.id,
                label=account.label,
                email=account.email,
                access_token=account.access_token,
                refresh_token=account.refresh_token,
                id_token=account.id_token,
                account_id=account.account_id,
                source=account.source,
                created_at=item.created_at or account.created_at,
                updated_at=account.updated_at,
            )
            updated_accounts.append(replacement)
            replaced = True
        else:
            updated_accounts.append(item)
    if not replaced:
        updated_accounts.append(replacement)
    save_accounts(updated_accounts)
    return replacement


def add_current_account(label: str | None = None, auth_path: Path | None = None) -> StoredAccount:
    payload = read_codex_auth(auth_path)
    tokens = payload["tokens"]
    email = detect_account_email(tokens)
    now = now_iso()
    account = StoredAccount(
        id=uuid.uuid4().hex[:8],
        label=(label or email or f"account-{uuid.uuid4().hex[:6]}").strip(),
        email=email,
        access_token=str(tokens.get("access_token") or "").strip(),
        refresh_token=str(tokens.get("refresh_token") or "").strip(),
        id_token=str(tokens.get("id_token") or "").strip() or None,
        account_id=str(tokens.get("account_id") or "").strip() or None,
        source="current-codex-auth",
        created_at=now,
        updated_at=now,
    )
    saved = upsert_account(account)
    state = load_state()
    state["active_account_id"] = saved.id
    save_state(state)
    write_codex_auth(saved)
    return saved


def switch_account(target: str) -> StoredAccount:
    accounts = load_accounts()
    selected = resolve_account(accounts, target)
    write_codex_auth(selected)
    state = load_state()
    state["active_account_id"] = selected.id
    save_state(state)
    return selected


def remove_account(target: str) -> StoredAccount:
    accounts = load_accounts()
    selected = resolve_account(accounts, target)
    remaining = [item for item in accounts if item.id != selected.id]
    save_accounts(remaining)
    state = load_state()
    if state.get("active_account_id") == selected.id:
        next_active = remaining[0] if remaining else None
        state["active_account_id"] = next_active.id if next_active else None
        auth_path = codex_auth_file()
        if next_active is not None:
            write_codex_auth(next_active, path=auth_path)
        elif auth_path.exists():
            auth_path.unlink()
    save_state(state)
    return selected


def doctor() -> dict[str, Any]:
    accounts = load_accounts()
    state = load_state()
    auth = None
    auth_error = None
    try:
        auth = read_codex_auth()
    except Exception as exc:
        auth_error = str(exc)
    active = next((item for item in accounts if item.id == state.get("active_account_id")), None)
    cli_tokens = (auth or {}).get("tokens") if isinstance(auth, dict) else None
    cli_match = bool(
        active
        and isinstance(cli_tokens, dict)
        and cli_tokens.get("access_token") == active.access_token
        and cli_tokens.get("refresh_token") == active.refresh_token
    )
    return {
        "checked_at": now_iso(),
        "account_count": len(accounts),
        "active_account": asdict(active) if active else None,
        "codex_auth_present": isinstance(cli_tokens, dict),
        "codex_auth_matches_active": cli_match,
        "codex_auth_error": auth_error,
    }


def _rows_for_display() -> list[dict[str, Any]]:
    accounts = load_accounts()
    active_id = load_state().get("active_account_id")
    rows = []
    for index, item in enumerate(accounts, start=1):
        rows.append(
            {
                "index": index,
                "id": item.id,
                "label": item.label,
                "email": item.email,
                "active": item.id == active_id,
                "source": item.source,
                "account_id": item.account_id,
            }
        )
    return rows


def cmd_add(args: argparse.Namespace) -> int:
    account = add_current_account(label=args.label, auth_path=Path(args.auth_file) if args.auth_file else None)
    print(f"已导入账号: {account.label} [{account.id}]")
    if account.email:
        print(f"邮箱: {account.email}")
    print(f"已写入当前 Codex 登录态: {codex_auth_file()}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = _rows_for_display()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("当前没有已保存账号。先用 codex login 登录一个账号，再执行 add。")
        return 0
    for row in rows:
        marker = "*" if row["active"] else " "
        name = row["email"] or row["label"]
        tail = [f"label={row['label']}", f"source={row['source']}"]
        if row["account_id"]:
            tail.append(f"account_id={row['account_id']}")
        print(f"{marker} {row['index']}. {name} [{row['id']}] | " + " | ".join(tail))
    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    account = switch_account(args.target)
    print(f"已切换到账号: {account.email or account.label} [{account.id}]")
    print(f"Codex 登录文件: {codex_auth_file()}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    account = remove_account(args.target)
    print(f"已删除账号: {account.email or account.label} [{account.id}]")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    payload = doctor()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"检查时间: {payload['checked_at']}")
    print(f"账号总数: {payload['account_count']}")
    active = payload.get("active_account")
    if active:
        print(f"活动账号: {active.get('email') or active.get('label')} [{active.get('id')}]")
    else:
        print("活动账号: 无")
    print(f"Codex auth 存在: {'是' if payload['codex_auth_present'] else '否'}")
    print(f"Codex auth 与活动账号一致: {'是' if payload['codex_auth_matches_active'] else '否'}")
    if payload.get("codex_auth_error"):
        print(f"Codex auth 读取错误: {payload['codex_auth_error']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Windows 版 Codex 账号管理脚本：导入当前 Codex 登录态、保存多个账号，并一键切换 .codex/auth.json。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="导入当前账号", description="从当前 Codex auth.json 导入一个账号并保存到 Windows 账号池。")
    add_parser.add_argument("--label", help="自定义账号备注")
    add_parser.add_argument("--auth-file", help="指定要导入的 auth.json 路径；默认读取当前用户的 .codex/auth.json")
    add_parser.set_defaults(func=cmd_add)

    list_parser = subparsers.add_parser("list", help="列出账号", description="列出所有已保存账号，并标记当前活动账号。")
    list_parser.add_argument("--json", action="store_true", help="JSON 输出")
    list_parser.set_defaults(func=cmd_list)

    switch_parser = subparsers.add_parser("switch", help="切换账号", description="按序号 / id / 邮箱 / label 切换当前 Codex 登录账号。")
    switch_parser.add_argument("target", help="序号 / id / 邮箱 / label")
    switch_parser.set_defaults(func=cmd_switch)

    remove_parser = subparsers.add_parser("remove", help="删除账号", description="从本地账号池删除一个账号。")
    remove_parser.add_argument("target", help="序号 / id / 邮箱 / label")
    remove_parser.set_defaults(func=cmd_remove)

    doctor_parser = subparsers.add_parser("doctor", help="检查状态", description="检查账号池中的活动账号是否与当前 .codex/auth.json 一致。")
    doctor_parser.add_argument("--json", action="store_true", help="JSON 输出")
    doctor_parser.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ManagerError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
