"""Static regressions for Docker stage2 ownership reconciliation."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
STAGE2_HOOK = REPO_ROOT / "docker" / "stage2-hook.sh"


def _ownership_block() -> str:
    text = STAGE2_HOOK.read_text(encoding="utf-8")
    start = text.index("# --- Fix ownership of data volume ---")
    end = text.index("# Always reset ownership of $HERMES_HOME/profiles")
    return text[start:end]


def test_custom_uid_does_not_force_recursive_chown_when_ownership_matches() -> None:
    block = _ownership_block()

    assert '"$HERMES_UID" != "10000"' not in block, (
        "A non-default HERMES_UID/PUID must not force recursive chown by itself; "
        "the hook should chown only when the current owner differs from the "
        "remapped hermes UID."
    )
    assert "needs_data_chown" in block
    assert "needs_install_chown" in block


def test_stage2_chown_decision_uses_current_owner_probes() -> None:
    block = _ownership_block()

    assert 'stat -c %u "$path"' in block
    assert 'path_needs_chown()' in block
    assert 'path_needs_chown "$HERMES_HOME/$sub"' in block
    assert '"$INSTALL_DIR/.venv"' in block
    assert 'path_needs_chown "$path"' in block
