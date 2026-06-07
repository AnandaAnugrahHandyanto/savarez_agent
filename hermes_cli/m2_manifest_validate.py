"""manifest_validate — manifest 경로 검증 (DESIGN_v4 §4-A, 결정적)

워커가 선언한 write 대상 경로들이 안전한지 부모가 검증한다.
의미실행/설정 파일·symlink·directory·core 경로를 거부한다.

reject 시 ManifestReject 예외. 통과 시 검증된 절대경로 리스트 반환.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

# write 허용 디렉토리(workspace 상대) — 이 밖은 reject
ALLOWED_SUBDIRS = ("source_staging", "reviews", "output", "proposal")

# 의미실행/설정 파일 basename — import·실행 시 부수효과 → reject
FORBIDDEN_BASENAMES = frozenset({
    "conftest.py", "__init__.py", "sitecustomize.py", "usercustomize.py",
    "pytest.ini", "tox.ini", "setup.py", "setup.cfg", "pyproject.toml",
    ".envrc", "Makefile", "manage.py",
})
FORBIDDEN_SUFFIXES = (".pth", ".toml", ".cfg", ".ini")

# forbidden core 경로 조각(invest 핵심) — hard fail
FORBIDDEN_CORE_FRAGMENTS = (
    "order", "trade_allowed", "decision_packet", "collector",
    "stock_daily_review_collect.py",
)


class ManifestReject(Exception):
    pass


def _no_symlink_components(p: Path, workspace: Path) -> None:
    """workspace 경계부터 leaf까지 각 컴포넌트가 symlink/non-regular가 아님을 lstat로 확인."""
    rel = p.relative_to(workspace)
    cur = workspace
    for part in rel.parts:
        cur = cur / part
        if cur.is_symlink():
            raise ManifestReject(f"symlink 경로 컴포넌트 거부: {cur}")
        if cur.exists():
            st = cur.lstat()
            # 디렉토리/일반파일만 허용(소켓·fifo·device 거부)
            if not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):
                raise ManifestReject(f"non-regular 경로 컴포넌트 거부: {cur}")


def validate_manifest_paths(writes, workspace) -> list[str]:
    """writes: 워커 선언 경로 리스트. workspace: 절대 경로.
    통과 시 검증된 절대경로 리스트, 실패 시 ManifestReject."""
    ws = Path(workspace).resolve()
    if not ws.is_dir():
        raise ManifestReject(f"workspace 디렉토리 아님: {ws}")
    if not writes:
        raise ManifestReject("빈 manifest")

    out: list[str] = []
    for w in writes:
        if not w or w.startswith("-"):
            raise ManifestReject(f"잘못된 경로: {w!r}")
        # embedded NUL(다운스트림 C truncation) 차단 (#4 v2)
        if "\x00" in str(w):
            raise ManifestReject("경로에 NUL 포함")
        p = Path(w)
        if not p.is_absolute():
            p = ws / w
        # 정규화(symlink 미해석) 후 workspace 내부 강제
        p = Path(os.path.normpath(str(p)))
        try:
            rel = p.relative_to(ws)
        except ValueError:
            raise ManifestReject(f"workspace 밖 경로: {p}")
        # allowlist 서브디렉토리
        if not rel.parts or rel.parts[0] not in ALLOWED_SUBDIRS:
            raise ManifestReject(f"허용 서브디렉토리 밖: {rel}")
        # exact leaf(디렉토리 금지)
        if str(p).endswith(os.sep) or p.is_dir():
            raise ManifestReject(f"디렉토리는 leaf 불가: {p}")
        # macOS case-insensitive FS 우회 차단(#4): casefold + trailing dot/space strip 비교
        base_cf = p.name.casefold().rstrip(" .")
        if base_cf in {b.casefold() for b in FORBIDDEN_BASENAMES} \
                or base_cf.endswith(tuple(s.casefold() for s in FORBIDDEN_SUFFIXES)):
            raise ManifestReject(f"의미실행/설정 파일 거부: {p.name}")
        low = str(p).casefold()
        for frag in FORBIDDEN_CORE_FRAGMENTS:
            if frag in low:
                raise ManifestReject(f"forbidden core 경로: {frag} in {p}")
        _no_symlink_components(p, ws)
        out.append(str(p))
    return out
