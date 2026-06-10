from __future__ import annotations

from pathlib import Path

from plugins.mobile_bug_agent.simulator_proof import SimulatorProofHarness


def _worktree(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").write_text("gitdir: /tmp/fake-mobile-worktree-git-dir", encoding="utf-8")
    (path / "package.json").write_text('{"scripts":{"ios":"expo run:ios","android":"expo run:android"}}', encoding="utf-8")
    return path


def test_simulator_proof_ios_builds_launches_deep_link_and_screenshots(tmp_path):
    calls = []
    proof_dir = tmp_path / "proof"
    worktree = _worktree(tmp_path / "app")

    def run_text(args, cwd, timeout):
        calls.append((args, cwd, timeout))
        if args[:4] == ("xcrun", "simctl", "io", "SIM-123"):
            Path(args[-1]).write_text("png", encoding="utf-8")
        return "ok"

    harness = SimulatorProofHarness(run_text=run_text)

    result = harness.run(
        worktree=worktree,
        proof_dir=proof_dir,
        platforms=("ios",),
        ios_simulator_udid="SIM-123",
        deep_link="elixir://marketplace/offer/fitness-first",
        timeout_seconds=90,
    )

    assert result == [str(proof_dir / "ios-screenshot.png")]
    assert calls == [
        (("xcrun", "--find", "simctl"), worktree, 90),
        (("xcodebuild", "-version"), worktree, 90),
        (("npm", "run", "ios"), worktree, 90),
        (
            ("xcrun", "simctl", "openurl", "SIM-123", "elixir://marketplace/offer/fitness-first"),
            worktree,
            90,
        ),
        (("xcrun", "simctl", "io", "SIM-123", "screenshot", str(proof_dir / "ios-screenshot.png")), worktree, 90),
    ]


def test_simulator_proof_android_builds_launches_deep_link_and_screenshots(tmp_path):
    text_calls = []
    bytes_calls = []
    proof_dir = tmp_path / "proof"
    worktree = _worktree(tmp_path / "app")

    def run_text(args, cwd, timeout):
        text_calls.append((args, cwd, timeout))
        return "ok"

    def run_bytes(args, cwd, timeout):
        bytes_calls.append((args, cwd, timeout))
        return b"png"

    harness = SimulatorProofHarness(run_text=run_text, run_bytes=run_bytes)

    result = harness.run(
        worktree=worktree,
        proof_dir=proof_dir,
        platforms=("android",),
        android_serial="emulator-5554",
        deep_link="elixir://marketplace/offer/fitness-first",
        timeout_seconds=120,
    )

    assert result == [str(proof_dir / "android-screenshot.png")]
    assert text_calls == [
        (("adb", "-s", "emulator-5554", "version"), worktree, 120),
        (("emulator", "-list-avds"), worktree, 120),
        (("npm", "run", "android"), worktree, 120),
        (
            (
                "adb",
                "-s",
                "emulator-5554",
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                "elixir://marketplace/offer/fitness-first",
            ),
            worktree,
            120,
        ),
    ]
    assert bytes_calls == [
        (("adb", "-s", "emulator-5554", "exec-out", "screencap", "-p"), worktree, 120)
    ]
    assert (proof_dir / "android-screenshot.png").read_bytes() == b"png"


def test_simulator_proof_refuses_non_mobile_worktree(tmp_path):
    proof_dir = tmp_path / "proof"
    worktree = tmp_path / "app"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /tmp/fake-mobile-worktree-git-dir", encoding="utf-8")

    harness = SimulatorProofHarness()

    try:
        harness.run(worktree=worktree, proof_dir=proof_dir, platforms=("ios",))
    except RuntimeError as exc:
        assert "package.json" in str(exc)
    else:
        raise AssertionError("expected proof harness to fail closed")
