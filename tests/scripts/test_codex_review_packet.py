import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKET = REPO_ROOT / "scripts" / "runtime" / "codex_review_packet.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_review_packet_bounds_diff_and_marks_truncation(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    target = tmp_path / "demo.py"
    target.write_text("print('old')\n", encoding="utf-8")
    _git(tmp_path, "add", "demo.py")
    _git(tmp_path, "commit", "-m", "init")
    target.write_text("\n".join(f"print('line {i}')" for i in range(200)) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(PACKET),
            "--workdir",
            str(tmp_path),
            "--file",
            "demo.py",
            "--max-diff-chars",
            "500",
            "--max-total-chars",
            "1400",
        ],
        cwd=str(tmp_path),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert proc.returncode == 0, proc.stderr
    assert "# Bounded Codex review packet" in proc.stdout
    assert "demo.py" in proc.stdout
    assert "[truncated" in proc.stdout
    assert len(proc.stdout) <= 1500


def test_review_packet_includes_bounded_untracked_scope_file(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    untracked = tmp_path / "new_guard.py"
    untracked.write_text("UNTRACKED_SENTINEL = 'included'\n" + "x = 1\n" * 200, encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(PACKET),
            "--workdir",
            str(tmp_path),
            "--file",
            "new_guard.py",
            "--max-diff-chars",
            "500",
            "--max-total-chars",
            "1800",
        ],
        cwd=str(tmp_path),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert proc.returncode == 0, proc.stderr
    assert "## bounded untracked file previews" in proc.stdout
    assert "new_guard.py" in proc.stdout
    assert "UNTRACKED_SENTINEL" in proc.stdout
    assert "[truncated" in proc.stdout
    assert len(proc.stdout) <= 1900
