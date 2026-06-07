"""parent_proxy — 부모중개 LLM 프록시 (M2-1b, DESIGN_v4 §5-B / DESIGN_M2 §1)

워커는 provider와 직접 통신하지 않고, 부모 소유 Unix domain socket(PROXY_SOCK)으로만 요청한다.
부모(이 모듈)가: provider allowlist·credential 격리·redaction·감사 로깅·template-only 프롬프트를 강제.

보안 계약:
- **canonical 경로 강제**: PROXY_SOCK은 realpath==self 인 절대경로여야 한다(M2-1a 실측: seatbelt
  unix-socket 필터가 커널 canonical 경로로 매칭 → /tmp 심볼릭 주면 워커 연결 실패).
- **자유 프롬프트 금지**: 워커는 raw messages/prompt를 못 보낸다. 등록된 template_id + slots만.
  부모가 실제 프롬프트를 조립 → exfil 표면 축소.
- **credential 격리**: provider 자격증명은 provider_call 클로저에만 존재. 와이어·응답·로그 어디에도 미노출.
- **redaction**: 요청 프롬프트·응답을 로깅 전 마스킹(labeled secret·env line·고엔트로피 토큰).
- **provider 핀**: 서버가 provider 고정. 워커가 override 시도 시 거부.

M2-1b 범위 = 부모측 프레임만. 실제 provider 호출(provider_call)은 주입 콜러블(테스트=stub, M2-1c=mock).
"""
from __future__ import annotations

import json
import os
import re
import socket
import struct
import threading

_MAX_FRAME = 256 * 1024  # 요청 프레임 상한 256KB


class ProxyError(Exception):
    pass


# --------------------------------------------------------------------------
# 와이어 프레이밍: 4-byte big-endian length || UTF-8 JSON
# --------------------------------------------------------------------------
def _recv_exact(conn, n: int):
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return bytes(buf) if len(buf) == n else None


def send_frame(conn, obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    conn.sendall(struct.pack(">I", len(data)) + data)


def recv_frame(conn):
    hdr = _recv_exact(conn, 4)
    if hdr is None:
        return None  # 정상 종료(빈 read)
    (n,) = struct.unpack(">I", hdr)
    if n > _MAX_FRAME:
        raise ProxyError(f"frame too large: {n} > {_MAX_FRAME}")
    body = _recv_exact(conn, n)
    if body is None:
        raise ProxyError("truncated frame body")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProxyError(f"bad JSON: {e}")


# --------------------------------------------------------------------------
# Redaction: 라벨 시크릿 / env line / 토큰 prefix / 고엔트로피
# --------------------------------------------------------------------------
_LABELED = re.compile(
    r'(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|'
    r'credential|private[_-]?key)\b(\s*[:=]\s*)(\S+)')
_ENV_LINE = re.compile(r'(?im)^([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(\S+)\s*$')
# Codex M2 #5: URL-embedded creds(https://user:pass@host) — egress·로그 모두 차단.
_URL_CRED = re.compile(r'(?i)\b([a-z][a-z0-9+.\-]*://)([^/\s:@]+):([^/\s@]+)@')
# 고신호 토큰(egress+log 둘 다 마스킹). 정상 코드 오탐 낮음.
_TOKEN_HIGH = [
    re.compile(r'(?i)\b(?:sk|rk)-[A-Za-z0-9]{12,}'),
    re.compile(r'\bghp_[A-Za-z0-9]{20,}'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'\bgh[oprsu]_[A-Za-z0-9]{20,}'),
    re.compile(r'\bAKIA[0-9A-Z]{12,}'),
    re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}'),
    re.compile(r'\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}'),  # JWT
]
# PEM 블록 전체(여러 줄 body 포함) — Codex M2 r2 #Med5
_PEM_BLOCK = re.compile(
    r'-----BEGIN [A-Z0-9 ]*-----.*?-----END [A-Z0-9 ]*-----', re.DOTALL)
# zero-width/제어 문자(토큰 분할 회피) — 매칭 전 제거
_ZEROWIDTH = re.compile(r'[​‌‍⁠﻿]')
# 공격적(로그 전용). 코드에 흔한 긴 base64/hex라 egress엔 미적용(코드 훼손 방지).
_TOKEN_AGGRESSIVE = [
    re.compile(r'\b[A-Za-z0-9+/]{40,}={0,2}\b'),
    re.compile(r'\b[0-9a-fA-F]{32,}\b'),
]


def _mask(s: str) -> str:
    s = str(s)
    return (s[:3] + "…REDACTED…" + s[-2:]) if len(s) > 8 else "…REDACTED…"


def redact(text, aggressive: bool = True) -> str:
    """aggressive=True: 로그용(긴 base64/hex 포함). aggressive=False: egress용(고신호만, 코드 훼손 최소)."""
    out = text if isinstance(text, str) else str(text)
    out = _ZEROWIDTH.sub("", out)                      # zero-width 분할 토큰 재결합(Med5)
    out = _PEM_BLOCK.sub("…REDACTED-PEM…", out)        # PEM 블록 전체(Med5)
    out = _URL_CRED.sub(lambda m: m.group(1) + m.group(2) + ":" + _mask(m.group(3)) + "@", out)
    out = _LABELED.sub(lambda m: m.group(1) + m.group(2) + _mask(m.group(3)), out)
    out = _ENV_LINE.sub(lambda m: m.group(1) + m.group(2) + _mask(m.group(3)), out)
    for pat in _TOKEN_HIGH:
        out = pat.sub(lambda m: _mask(m.group(0)), out)
    if aggressive:
        for pat in _TOKEN_AGGRESSIVE:
            out = pat.sub(lambda m: _mask(m.group(0)), out)
    return out


# --------------------------------------------------------------------------
# ParentProxy
# --------------------------------------------------------------------------
class ParentProxy:
    def __init__(self, sock_path: str, *, provider: str, provider_allowlist,
                 templates: dict, provider_call, audit_log_path: str,
                 max_tokens: int = 1024, io_timeout: float = 5.0,
                 max_concurrency: int = 16):
        rp = os.path.realpath(sock_path)
        if rp != sock_path:
            raise ProxyError(
                f"PROXY_SOCK은 canonical(realpath) 경로여야: {sock_path!r} != {rp!r}")
        if provider not in set(provider_allowlist):
            raise ProxyError(f"provider가 allowlist 밖: {provider!r}")
        self.sock_path = sock_path
        self.provider = provider
        self.provider_allowlist = set(provider_allowlist)
        self.templates = dict(templates)
        self.provider_call = provider_call   # callable(prompt:str, max_tokens:int)->str (credential은 클로저)
        self.audit_log_path = audit_log_path
        self.max_tokens = int(max_tokens)
        self.io_timeout = float(io_timeout)   # Codex M2 #4: per-connection I/O timeout(slow-loris 차단)
        # Codex M2 r2 #Med4: 동시 핸들러 스레드 상한(connection-flood 스레드 고갈 차단)
        self.max_concurrency = int(max_concurrency)
        self._sem = threading.BoundedSemaphore(self.max_concurrency)
        self._srv = None
        self._stop = threading.Event()
        self._thread = None
        self._audit_lock = threading.Lock()

    # ---- lifecycle ----
    def start(self):
        if os.path.exists(self.sock_path):
            os.unlink(self.sock_path)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(self.sock_path)
        os.chmod(self.sock_path, 0o600)   # 부모 전용
        s.listen(16)
        self._srv = s
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._srv:
            try:
                self._srv.close()
            except OSError:
                pass
        try:
            os.unlink(self.sock_path)
        except OSError:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # ---- serving ----
    def _serve(self):
        self._srv.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            # Codex M2 #4 + r2 #Med4: 동시성 cap 확보 후에만 스레드 생성. 초과 시 즉시 busy 거부(스레드 고갈 차단).
            if not self._sem.acquire(blocking=False):
                try:
                    conn.settimeout(self.io_timeout)
                    send_frame(conn, self._err("server busy (max_concurrency)"))
                except OSError:
                    pass
                finally:
                    try:
                        conn.close()
                    except OSError:
                        pass
                continue
            th = threading.Thread(target=self._handle_conn, args=(conn,), daemon=True)
            th.start()

    def _handle_conn(self, conn):
        try:
            conn.settimeout(self.io_timeout)
            self._handle(conn)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            try:
                self._sem.release()
            except (ValueError, RuntimeError):
                pass

    def _handle(self, conn):
        try:
            req = recv_frame(conn)
        except (socket.timeout, TimeoutError, OSError) as e:
            try:
                send_frame(conn, self._err(f"io timeout/err: {type(e).__name__}"))
            except OSError:
                pass
            return
        except ProxyError as e:
            send_frame(conn, self._err(f"frame: {e}"))
            return
        if req is None:
            return
        send_frame(conn, self._process(req))

    # ---- request processing ----
    def _process(self, req) -> dict:
        if not isinstance(req, dict) or req.get("v") != 1 or req.get("kind") != "llm_call":
            return self._err("bad request schema (v=1, kind=llm_call 필요)")
        if "messages" in req or "prompt" in req:
            return self._err("raw prompt/messages 금지 (template_id+slots만)")
        if "provider" in req and req["provider"] != self.provider:
            return self._err("provider override 금지")
        tid = req.get("template_id")
        if tid not in self.templates:
            return self._err(f"unknown template_id: {tid!r}")
        slots = req.get("slots") or {}
        if not isinstance(slots, dict):
            return self._err("slots는 object여야")
        try:
            prompt = self.templates[tid].format(**{k: str(v) for k, v in slots.items()})
        except (KeyError, IndexError, ValueError) as e:
            return self._err(f"template slot 오류: {e}")
        try:
            max_tokens = min(int(req.get("max_tokens") or self.max_tokens), self.max_tokens)
        except (TypeError, ValueError):
            max_tokens = self.max_tokens

        # Codex M2 #5: egress redaction — provider에도 raw secret 미전달(고신호 패턴만, 코드 훼손 최소).
        safe_prompt = redact(prompt, aggressive=False)
        self._audit(req.get("task_id"), tid, kind="request", prompt=redact(prompt))
        try:
            content = str(self.provider_call(safe_prompt, max_tokens))
        except Exception:
            self._audit(req.get("task_id"), tid, kind="error", note="provider 호출 실패")
            return self._err("provider call failed")
        char_cap = max_tokens * 8
        truncated = len(content) > char_cap
        if truncated:
            content = content[:char_cap]
        self._audit(req.get("task_id"), tid, kind="response", output=redact(content))
        return {"v": 1, "ok": True, "content": content, "error": None, "truncated": truncated}

    @staticmethod
    def _err(msg: str) -> dict:
        return {"v": 1, "ok": False, "content": None, "error": msg, "truncated": False}

    def _audit(self, task_id, tid, *, kind, prompt=None, output=None, note=None):
        rec = {"kind": kind, "task_id": task_id, "template_id": tid}
        if prompt is not None:
            rec["prompt_redacted"] = prompt
        if output is not None:
            rec["output_redacted"] = output
        if note is not None:
            rec["note"] = note
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        with self._audit_lock:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(line)
