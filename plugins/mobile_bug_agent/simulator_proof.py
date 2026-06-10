from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Callable, Sequence


RunText = Callable[[tuple[str, ...], Path, int], str]
RunBytes = Callable[[tuple[str, ...], Path, int], bytes]


class SimulatorProofHarness:
    def __init__(
        self,
        *,
        run_text: RunText | None = None,
        run_bytes: RunBytes | None = None,
    ) -> None:
        self._run_text = run_text or _run_text_command
        self._run_bytes = run_bytes or _run_bytes_command

    def run(
        self,
        *,
        worktree: str | Path,
        proof_dir: str | Path,
        platforms: Sequence[str],
        ios_simulator_udid: str = "",
        android_serial: str = "",
        deep_link: str = "",
        timeout_seconds: int = 600,
    ) -> list[str]:
        worktree_path = Path(worktree)
        proof_path = Path(proof_dir)
        self._validate_worktree(worktree_path)
        proof_path.mkdir(parents=True, exist_ok=True)

        artifacts: list[str] = []
        for platform in _clean_platforms(platforms):
            if platform == "ios":
                artifacts.append(
                    self._capture_ios(
                        worktree=worktree_path,
                        proof_dir=proof_path,
                        simulator_udid=ios_simulator_udid,
                        deep_link=deep_link,
                        timeout_seconds=timeout_seconds,
                    )
                )
            elif platform == "android":
                artifacts.append(
                    self._capture_android(
                        worktree=worktree_path,
                        proof_dir=proof_path,
                        android_serial=android_serial,
                        deep_link=deep_link,
                        timeout_seconds=timeout_seconds,
                    )
                )
            else:
                raise RuntimeError(f"unsupported proof platform: {platform}")
        return artifacts

    @staticmethod
    def _validate_worktree(worktree: Path) -> None:
        if not worktree.is_dir():
            raise RuntimeError(f"worktree does not exist: {worktree}")
        if not (worktree / ".git").exists():
            raise RuntimeError(f"worktree is not a git worktree: {worktree}")
        if not (worktree / "package.json").exists():
            raise RuntimeError(f"package.json was not found in worktree: {worktree}")

    def _capture_ios(
        self,
        *,
        worktree: Path,
        proof_dir: Path,
        simulator_udid: str,
        deep_link: str,
        timeout_seconds: int,
    ) -> str:
        target = simulator_udid.strip() or "booted"
        screenshot = proof_dir / "ios-screenshot.png"
        self._run_text(("xcrun", "--find", "simctl"), worktree, timeout_seconds)
        self._run_text(("xcodebuild", "-version"), worktree, timeout_seconds)
        self._run_text(("npm", "run", "ios"), worktree, timeout_seconds)
        if deep_link.strip():
            self._run_text(("xcrun", "simctl", "openurl", target, deep_link.strip()), worktree, timeout_seconds)
        self._run_text(("xcrun", "simctl", "io", target, "screenshot", str(screenshot)), worktree, timeout_seconds)
        if not screenshot.is_file():
            raise RuntimeError(f"iOS simulator screenshot was not created: {screenshot}")
        return str(screenshot)

    def _capture_android(
        self,
        *,
        worktree: Path,
        proof_dir: Path,
        android_serial: str,
        deep_link: str,
        timeout_seconds: int,
    ) -> str:
        screenshot = proof_dir / "android-screenshot.png"
        adb = ("adb", "-s", android_serial.strip()) if android_serial.strip() else ("adb",)
        self._run_text((*adb, "version"), worktree, timeout_seconds)
        self._run_text(("emulator", "-list-avds"), worktree, timeout_seconds)
        self._run_text(("npm", "run", "android"), worktree, timeout_seconds)
        if deep_link.strip():
            self._run_text(
                (
                    *adb,
                    "shell",
                    "am",
                    "start",
                    "-a",
                    "android.intent.action.VIEW",
                    "-d",
                    deep_link.strip(),
                ),
                worktree,
                timeout_seconds,
            )
        screenshot.write_bytes(self._run_bytes((*adb, "exec-out", "screencap", "-p"), worktree, timeout_seconds))
        if not screenshot.is_file() or screenshot.stat().st_size == 0:
            raise RuntimeError(f"Android emulator screenshot was not created: {screenshot}")
        return str(screenshot)


def _clean_platforms(platforms: Sequence[str]) -> tuple[str, ...]:
    values = tuple(str(platform).strip().lower() for platform in platforms if str(platform).strip())
    return values or ("ios", "android")


def _run_text_command(args: tuple[str, ...], cwd: Path, timeout: int) -> str:
    proc = _run(args, cwd, timeout, capture_bytes=False)
    return str(proc.stdout or "")


def _run_bytes_command(args: tuple[str, ...], cwd: Path, timeout: int) -> bytes:
    proc = _run(args, cwd, timeout, capture_bytes=True)
    return bytes(proc.stdout or b"")


def _run(
    args: tuple[str, ...],
    cwd: Path,
    timeout: int,
    *,
    capture_bytes: bool,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    try:
        proc = subprocess.run(
            list(args),
            cwd=str(cwd),
            text=not capture_bytes,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"executable not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"command timed out: {' '.join(args)}") from exc
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace") if isinstance(proc.stderr, bytes) else proc.stderr
        stdout = proc.stdout.decode("utf-8", errors="replace") if isinstance(proc.stdout, bytes) else proc.stdout
        raise RuntimeError(
            "\n".join(
                part
                for part in [
                    f"command failed ({proc.returncode}): {' '.join(args)}",
                    f"stdout: {str(stdout or '').strip()[-2000:]}",
                    f"stderr: {str(stderr or '').strip()[-2000:]}",
                ]
                if part
            )
        )
    return proc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Monica simulator proof artifacts.")
    parser.add_argument("--worktree", default="")
    parser.add_argument("--proof-dir", default="")
    parser.add_argument("--platform", dest="platforms", action="append", default=[])
    parser.add_argument("--ios-simulator-udid", default="")
    parser.add_argument("--android-serial", default="")
    parser.add_argument("--deep-link", default="")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args(argv)

    import os

    worktree = args.worktree or os.getenv("MONICA_WORKTREE", "")
    proof_dir = args.proof_dir or os.getenv("MONICA_PROOF_DIR", "")
    platforms = args.platforms or os.getenv("MONICA_PROOF_PLATFORM_ORDER", "").split(",")
    deep_link = args.deep_link or os.getenv("MONICA_DEEP_LINK", "")
    if not worktree:
        raise SystemExit("MONICA_WORKTREE is required")
    if not proof_dir:
        raise SystemExit("MONICA_PROOF_DIR is required")

    try:
        artifacts = SimulatorProofHarness().run(
            worktree=worktree,
            proof_dir=proof_dir,
            platforms=platforms,
            ios_simulator_udid=args.ios_simulator_udid or os.getenv("MONICA_IOS_SIMULATOR_UDID", ""),
            android_serial=args.android_serial or os.getenv("MONICA_ANDROID_SERIAL", ""),
            deep_link=deep_link,
            timeout_seconds=max(args.timeout_seconds, 1),
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({"artifacts": artifacts}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
