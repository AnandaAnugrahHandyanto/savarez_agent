from pathlib import Path
import re


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "nix-lockfile-fix.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text()


def test_lockfile_fix_workflow_stages_consolidated_hash_file() -> None:
    text = _workflow_text()

    assert text.count("git add nix/lib.nix") == 2
    assert "git add nix/tui.nix nix/web.nix" not in text


def test_lockfile_fix_workflow_guard_allows_only_consolidated_hash_file() -> None:
    text = _workflow_text()

    match = re.search(r"grep -Ev '([^']+)'", text)
    assert match is not None
    allowlist = re.compile(match.group(1))

    assert allowlist.fullmatch("nix/lib.nix")
    assert not allowlist.fullmatch("nix/tui.nix")
    assert not allowlist.fullmatch("nix/web.nix")
    assert not allowlist.fullmatch("package-lock.json")
    assert "nix/(tui|web)" not in text
