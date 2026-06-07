"""manifest_phase2 — manifest 2-phase write 검증 (M2-2, DESIGN_v4 §4 / DESIGN_M2 §2)

phase1(선언·검증): 워커가 의도 write 경로 선언 → **마일스톤1 manifest_validate 재사용**으로
  allowlist·의미실행 basename·경로컴포넌트 symlink·core fragment·NUL·casefold 거부 → 검증된 절대 leaf(MW_n).
  + baseline 스냅샷(워커 실행 전 workspace 파일 경로집합 + sha256).
phase2(커밋·대조): 워커 종료 후 부모가 **fs 스냅샷 diff를 직접 생성**(워커 patch/결과 신뢰 0) →
  실제 변경 경로집합 ⊆ 선언 leaf ∧ 선언 밖 변경 0 ∧ 삭제 0 검증 + 각 sha256 기록.

이 모듈은 부모측 결정적 로직. 샌드박스가 1차로 write를 MW_n literal에 가두고, phase2는 부모의 독립 재확인.
M2-3 `writes_match_manifest` check의 입력 산출물.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import stat as _stat
from pathlib import Path

# 마일스톤1 manifest_validate 재사용 (phase1 선언 검증) — hermes_cli 패키지 내 m2_ 복사본
from hermes_cli import m2_manifest_validate as mv  # noqa: E402

ManifestReject = mv.ManifestReject


class ManifestPhaseError(Exception):
    pass


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot(workspace: str) -> dict:
    """workspace allowlist 서브디렉토리의 **일반파일만** {realpath: sha256}. symlink/non-regular 제외."""
    snap: dict[str, str] = {}
    for sub in mv.ALLOWED_SUBDIRS:
        root = Path(workspace) / sub
        if not root.is_dir():
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                p = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if not _stat.S_ISREG(st.st_mode):
                    continue  # symlink·fifo·device 제외
                snap[os.path.realpath(p)] = _sha256(p)
    return snap


def phase1_validate(declared_writes, workspace) -> list[str]:
    """워커 선언 write 경로 → M1 검증 → 절대 leaf 리스트. 실패 시 ManifestReject 전파."""
    return mv.validate_manifest_paths(declared_writes, workspace)


def baseline_snapshot(workspace) -> dict:
    """워커 실행 **전** 호출. phase2 대조용 기준 스냅샷."""
    return _snapshot(str(Path(workspace).resolve()))


def phase2_verify(workspace, declared_leaves, baseline: dict) -> dict:
    """워커 실행 **후** 호출. 부모가 fs diff 직접 생성·대조(워커 신뢰 0).

    반환 dict:
      ok                  : 선언 밖 변경 0 ∧ 삭제 0 일 때만 True
      added/modified/deleted/changed : 경로집합(정렬)
      out_of_manifest     : 변경됐으나 선언 안 된 경로(보안 위반)
      declared_unwritten  : 선언했으나 실제 미작성(허용, 보고만)
      sha256              : {변경경로: post sha256}  (merge proposal 입력)
      reasons             : 실패 사유 리스트
    """
    ws = str(Path(workspace).resolve())
    post = _snapshot(ws)
    declared = {os.path.realpath(p) for p in declared_leaves}
    base_keys, post_keys = set(baseline), set(post)

    added = post_keys - base_keys
    deleted = base_keys - post_keys
    modified = {p for p in (base_keys & post_keys) if baseline[p] != post[p]}
    changed = added | modified
    out_of_manifest = changed - declared
    declared_unwritten = declared - changed

    reasons = []
    if out_of_manifest:
        reasons.append(f"선언 밖 변경: {sorted(out_of_manifest)}")
    if deleted:
        reasons.append(f"삭제 발생: {sorted(deleted)}")
    # Codex M2 #3: 변경 leaf가 하드링크(st_nlink>1)면 workspace 밖 victim을 clobber했을 수 있음 → 거부.
    hardlinked = []
    for p in changed:
        try:
            if os.lstat(p).st_nlink > 1:
                hardlinked.append(p)
        except OSError:
            pass
    if hardlinked:
        reasons.append(f"하드링크 leaf(외부 clobber 위험): {sorted(hardlinked)}")
    # Codex M2 r3 #High + r4 Low: 선언 leaf 자체 symlink OR 부모 디렉토리 symlink 컴포넌트 → hard-fail.
    sym_leaves = [os.path.abspath(p) for p in declared_leaves
                  if os.path.islink(p) or _components_symlink_free(p, ws)]
    if sym_leaves:
        reasons.append(f"선언 leaf symlink/부모 symlink: {sorted(sym_leaves)}")

    ok = not out_of_manifest and not deleted and not hardlinked and not sym_leaves
    return {
        "ok": ok,
        "changed": sorted(changed),
        "added": sorted(added),
        "modified": sorted(modified),
        "deleted": sorted(deleted),
        "out_of_manifest": sorted(out_of_manifest),
        "declared_unwritten": sorted(declared_unwritten),
        "hardlinked": sorted(hardlinked),
        "sym_leaves": sorted(sym_leaves),
        "sha256": {p: post[p] for p in sorted(changed)},
        "reasons": reasons,
    }


def _components_symlink_free(leaf, workspace) -> str | None:
    """Codex M2 r4 Low: workspace 루트~leaf 각 **디렉토리 컴포넌트**가 symlink가 아님을 확인.
    parent dir symlink(source_staging→외부)로의 추종을 capture/precheck 시점에 재차단. 위반 시 사유 문자열."""
    ws = Path(os.path.abspath(workspace))
    p = Path(os.path.abspath(leaf))
    try:
        rel = p.relative_to(ws)
    except ValueError:
        return f"leaf가 workspace 밖: {p}"
    cur = ws
    for part in rel.parts[:-1]:           # leaf 직전까지의 디렉토리 컴포넌트
        cur = cur / part
        if os.path.islink(cur):
            return f"부모 디렉토리 symlink: {cur}"
    return None


def precheck_leaf_safety(workspace, declared_leaves) -> tuple[bool, list]:
    """Codex M2 r2 #High3 + r4 Low: 워커 spawn **전** 호출. workspace allowlist의 기존 파일·디렉토리와
    선언 leaf 경로에 symlink·하드링크(nlink>1)·부모 symlink가 있으면 fail-closed. 통과 시 (True, [])."""
    reasons = []
    ws = str(Path(workspace).resolve())
    # 기존 workspace 파일·디렉토리 전수(디렉토리 엔트리 symlink 포함)
    for sub in mv.ALLOWED_SUBDIRS:
        root = Path(ws) / sub
        if not root.is_dir():
            continue
        for dirpath, dirs, files in os.walk(root):
            for dn in dirs:
                dp = os.path.join(dirpath, dn)
                if os.path.islink(dp):
                    reasons.append(f"기존 디렉토리 symlink: {dp}")
            for fn in files:
                p = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if _stat.S_ISLNK(st.st_mode):
                    reasons.append(f"기존 symlink: {p}")
                elif _stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
                    reasons.append(f"기존 하드링크(nlink={st.st_nlink}): {p}")
    # 선언 leaf: 자체 symlink/하드링크 + 부모 디렉토리 symlink 컴포넌트
    for leaf in declared_leaves:
        comp = _components_symlink_free(leaf, ws)
        if comp:
            reasons.append(comp)
        try:
            st = os.lstat(leaf)
        except OSError:
            continue
        if _stat.S_ISLNK(st.st_mode):
            reasons.append(f"선언 leaf가 symlink: {leaf}")
        elif st.st_nlink > 1:
            reasons.append(f"선언 leaf가 하드링크(nlink={st.st_nlink}): {leaf}")
    return (not reasons), reasons


def capture_leaves(declared_leaves, capture_dir, workspace=None) -> dict:
    """Codex M2 #2(TOCTOU) 방어 + r2(NEW High): 선언 leaf를 **부모 전용 capture_dir**로 즉시 복사·고정.
    capture_dir은 **부모가 만든 workspace 밖 fresh 경로**여야 한다(run_and_capture가 mkdtemp).
    여기서도 capture_dir이 symlink면 거부, dst는 O_CREAT|O_EXCL|O_NOFOLLOW로 열어 symlink 추종 차단.

    각 leaf: 일반파일·st_nlink==1만 capture. symlink/하드링크/비정규/부재는 captured=None + 사유.
    반환 {realpath: {"captured","sha256","reason"}}.
    """
    cap = Path(capture_dir)
    # NEW High: capture_dir symlink 거부
    if cap.is_symlink():
        raise ManifestPhaseError(f"capture_dir이 symlink: {capture_dir}")
    cap.mkdir(parents=True, exist_ok=True)
    if Path(os.path.realpath(cap)) != Path(cap).resolve():
        raise ManifestPhaseError("capture_dir 경로 불일치(symlink 의심)")
    os.chmod(cap, 0o700)
    out: dict[str, dict] = {}
    for leaf in declared_leaves:
        # Codex M2 r3 #High: **realpath 금지**(symlink 추종). 원래 선언 경로로 검증·open.
        key = os.path.abspath(leaf)
        rec = {"captured": None, "sha256": None, "reason": None}
        # Codex M2 r4 Low: workspace 주면 부모 디렉토리 symlink 컴포넌트 재차단.
        if workspace is not None:
            comp = _components_symlink_free(key, workspace)
            if comp:
                rec["reason"] = comp
                out[key] = rec
                continue
        try:
            lst = os.lstat(key)          # 원래 경로 — symlink를 그대로 본다
        except OSError:
            rec["reason"] = "부재(미작성)"
            out[key] = rec
            continue
        if _stat.S_ISLNK(lst.st_mode):
            rec["reason"] = "symlink leaf 거부(외부 추종 차단)"
            out[key] = rec
            continue
        if not _stat.S_ISREG(lst.st_mode):
            rec["reason"] = "비정규"
            out[key] = rec
            continue
        if lst.st_nlink > 1:
            rec["reason"] = f"하드링크(st_nlink={lst.st_nlink})"
            out[key] = rec
            continue
        try:
            fd = os.open(key, os.O_RDONLY | os.O_NOFOLLOW)   # 원래 경로 O_NOFOLLOW → symlink면 ELOOP
        except OSError as e:
            rec["reason"] = f"open 실패({type(e).__name__})"
            out[key] = rec
            continue
        try:
            fst = os.fstat(fd)
            # TOCTOU: lstat↔fstat의 (dev,ino) 일치 + 일반파일·nlink==1 재확인
            if ((fst.st_dev, fst.st_ino) != (lst.st_dev, lst.st_ino)
                    or not _stat.S_ISREG(fst.st_mode) or fst.st_nlink > 1):
                os.close(fd)
                rec["reason"] = "TOCTOU/race(dev/ino 불일치)"
                out[key] = rec
                continue
            with os.fdopen(fd, "rb") as f:
                data = f.read()
        except OSError:
            try:
                os.close(fd)
            except OSError:
                pass
            rec["reason"] = "read 실패"
            out[key] = rec
            continue
        dst = cap / (hashlib.sha256(key.encode()).hexdigest()[:16] + "_" + os.path.basename(key))
        try:
            dfd = os.open(str(dst), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        except OSError as e:
            rec["reason"] = f"capture dst 생성 실패({type(e).__name__})"
            out[key] = rec
            continue
        with os.fdopen(dfd, "wb") as g:
            g.write(data)
        rec["captured"] = str(dst)
        rec["sha256"] = hashlib.sha256(data).hexdigest()
        out[key] = rec
    return out
