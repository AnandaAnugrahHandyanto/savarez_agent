"""m2_sandbox — implementer 워커용 sandbox-exec 명령 일반화 조립 (R4 배선, S2)

milestone1 `build_seatbelt_wrapper.py`(fixture 하드핀)를 **live task workspace**용으로 일반화한다.
implementer.sbpl 6 파라미터(SYNTH_ROOT·R2·MW_0·PF_LEAF·ENTRY_BIN·PROXY_SOCK)를 채워
`sandbox-exec -f <sbpl> -D ... -- ENTRY_BIN -I -S -B <worker> <MW_0>` 와 clean env(credential 0)를 만든다.

구조 불변식(milestone1 상속 + 실측):
  - SYNTH_ROOT = task workspace. MW_0 ⊂ workspace ⊂ SYNTH_ROOT(read allow-back) → leaf 경로 컴포넌트 read 가능.
    workspace는 implementer 입장에서 **sanitized/synthetic 영역**이어야 한다(B-track: 실데이터 미접근).
  - 워커 스크립트는 SYNTH_ROOT 안에 있어야 read 가능(/Users 전역 deny + SYNTH_ROOT allow-back).
    단 SYNTH_ROOT 내 process-exec는 deny → 스크립트는 ENTRY_BIN이 **읽어서 실행**(직접 exec 아님).
  - PROXY_SOCK = canonical 절대경로(seatbelt unix-socket 필터가 커널 canonical 매칭, /tmp 심볼릭 거부).
  - env에 credential 0(OPENAI/ANTHROPIC/GITHUB_TOKEN 등 미상속). 워커 egress = PROXY_SOCK 하나뿐.

**R4 한계(문서화)**: implementer.sbpl은 MW_0 literal 1개만 write 허용 → declared_leaves는 **단일**.
다중 leaf는 sbpl 확장(별도 작업)이라 fail-closed로 거부한다.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
IMPLEMENTER_SBPL = Path(__file__).resolve().parent / "sbpl" / "implementer.sbpl"
# 워커 스크립트 basename(SYNTH_ROOT 안에 이 이름으로 복사돼 있어야 함 — prepare_synth_workspace 배치).
WORKER_SCRIPT_NAME = "m2_worker_mock.py"


class SandboxAssemblyError(Exception):
    """fail-closed: 안전한 sandbox 명령을 조립할 수 없음."""


def prepare_synth_workspace(workspace: str) -> str:
    """S3 — task workspace를 implementer SYNTH_ROOT로 준비(라이브 무접촉, 격리).

    - source_staging/·proposal/·synth/ 디렉토리 생성.
    - 워커 스크립트(m2_worker_mock.py)를 SYNTH_ROOT 안으로 복사(read allow-back 영역).
    - sanitized 샘플 입력을 synth/에 배치(워커가 실데이터 아닌 합성 자료만 봄 — B-track).
    반환 = canonical SYNTH_ROOT. **실데이터·credential·git을 넣지 않는다.**
    """
    ws = os.path.realpath(workspace)
    if not os.path.isdir(ws):
        raise SandboxAssemblyError(f"workspace 디렉토리 아님: {ws}")
    for d in ("source_staging", "proposal", "synth"):
        os.makedirs(os.path.join(ws, d), exist_ok=True)
    src = Path(__file__).resolve().parent / WORKER_SCRIPT_NAME
    if not src.is_file():
        raise SandboxAssemblyError(f"워커 스크립트 원본 부재: {src}")
    shutil.copyfile(str(src), os.path.join(ws, WORKER_SCRIPT_NAME))
    sample = os.path.join(ws, "synth", "sample_input.py")
    if not os.path.exists(sample):
        with open(sample, "w", encoding="utf-8") as f:
            f.write("# sanitized synthetic input (실데이터·credential 0)\nSAMPLE_VALUE = 42\n")
    return ws


def resolve_runtime() -> tuple[str, str]:
    """(ENTRY_BIN, R2) 반환. ENTRY_BIN=실 python 인터프리터 canonical, R2=그 설치 루트.

    supervisor의 sys.executable(venv python)을 realpath하면 uv cpython 베이스로 해소된다
    (venv는 베이스 인터프리터의 심볼릭). 베이스를 직접 ENTRY_BIN으로 써 venv 심볼릭 read를 피한다."""
    entry = os.path.realpath(sys.executable)
    if not os.path.isfile(entry):
        raise SandboxAssemblyError(f"ENTRY_BIN 부재: {entry}")
    # .../cpython-X/bin/python3.11 → R2 = .../cpython-X
    r2 = os.path.dirname(os.path.dirname(entry))
    if not os.path.isdir(r2):
        raise SandboxAssemblyError(f"R2(런타임 루트) 부재: {r2}")
    return entry, r2


def _is_canonical_abs(p: str) -> bool:
    return bool(p) and os.path.isabs(p) and os.path.realpath(p) == p


def build_implementer_cmd(
    workspace: str,
    declared_leaves,
    *,
    proxy_sock: str,
    synth_root: str | None = None,
    entry_bin: str | None = None,
    r2: str | None = None,
) -> tuple[list[str], dict]:
    """sandbox-exec 명령 + clean env 조립. 파라미터 누락·비canonical·범위이탈 시 fail-closed.

    synth_root 미지정 시 workspace를 SYNTH_ROOT로 사용(B-track: workspace=sanitized 영역).
    """
    # --- sbpl / sandbox-exec 존재 ---
    if not os.path.exists(SANDBOX_EXEC):
        raise SandboxAssemblyError("sandbox-exec 부재")
    if not IMPLEMENTER_SBPL.is_file():
        raise SandboxAssemblyError(f"implementer.sbpl 부재: {IMPLEMENTER_SBPL}")

    # --- 런타임 ---
    if entry_bin is None or r2 is None:
        entry_bin, r2 = resolve_runtime()
    if not os.path.isfile(entry_bin):
        raise SandboxAssemblyError(f"ENTRY_BIN 부재: {entry_bin}")
    if not os.path.isdir(r2):
        raise SandboxAssemblyError(f"R2 부재: {r2}")

    # --- workspace / synth_root ---
    ws = os.path.realpath(workspace)
    if not os.path.isdir(ws):
        raise SandboxAssemblyError(f"workspace 디렉토리 아님: {ws}")
    sroot = os.path.realpath(synth_root) if synth_root else ws
    if not os.path.isdir(sroot):
        raise SandboxAssemblyError(f"SYNTH_ROOT 디렉토리 아님: {sroot}")

    # --- declared_leaves: R4=단일 ---
    leaves = list(declared_leaves or [])
    if len(leaves) != 1:
        raise SandboxAssemblyError(
            f"R4 implementer.sbpl은 단일 MW_0만 지원(declared_leaves={len(leaves)}개) → fail-closed")
    # MW_0는 canonical(realpath)이어야 seatbelt literal 매칭 성립(milestone1 실측).
    # leaf 미존재 가능 → 부모(존재)를 canonical화하고 basename 결합.
    _leaf_abs = os.path.abspath(leaves[0])
    mw0 = os.path.join(os.path.realpath(os.path.dirname(_leaf_abs)), os.path.basename(_leaf_abs))
    # MW_0는 SYNTH_ROOT(=workspace) 내부여야 leaf 경로 컴포넌트 read + literal write가 성립.
    if not (mw0 == sroot or mw0.startswith(sroot + os.sep)):
        raise SandboxAssemblyError(f"MW_0가 SYNTH_ROOT 밖: {mw0} ⊄ {sroot}")

    # --- PF_LEAF: MW_0와 분리(staging poison 방지) ---
    pf_leaf = os.path.join(os.path.dirname(mw0), ".preflight_check")

    # --- PROXY_SOCK: canonical 강제 ---
    if not _is_canonical_abs(proxy_sock):
        raise SandboxAssemblyError(
            f"PROXY_SOCK은 canonical 절대경로여야(seatbelt 커널 매칭): {proxy_sock!r}")

    # --- 워커 스크립트: SYNTH_ROOT 안 ---
    worker_script = os.path.join(sroot, WORKER_SCRIPT_NAME)
    if not os.path.isfile(worker_script):
        raise SandboxAssemblyError(
            f"워커 스크립트가 SYNTH_ROOT 안에 없음(S3 미배치): {worker_script}")

    # 정책은 **인라인 -p**(milestone1 v6 검증본): -f 파일참조 대신 텍스트를 직접 넘겨
    # spawn 후 정책파일 race를 없애고 `--` 종결자와의 호환을 보장한다.
    policy = IMPLEMENTER_SBPL.read_text(encoding="utf-8")
    if "(version 1)" not in policy or "(deny default)" not in policy:
        raise SandboxAssemblyError("implementer.sbpl 정책 로드 실패(형식)")
    cmd = [
        SANDBOX_EXEC, "-p", policy,
        "-D", f"SYNTH_ROOT={sroot}",
        "-D", f"R2={r2}",
        "-D", f"MW_0={mw0}",
        "-D", f"PF_LEAF={pf_leaf}",
        "-D", f"ENTRY_BIN={entry_bin}",
        "-D", f"PROXY_SOCK={proxy_sock}",
        "--",
        entry_bin, "-I", "-S", "-B", worker_script, mw0,
    ]
    # clean env: credential 0, egress=PROXY_SOCK만. HOME/TMPDIR는 synth 안(읽기 allow-back).
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": sroot,
        "TMPDIR": sroot,
        "LC_ALL": "C",
        "PROXY_SOCK": proxy_sock,
    }
    return cmd, env
