"""Static checks on the Dockerfile's INCLUDE_BROWSER build arg.

Verifies the slim-build path stays wired up — i.e. the Dockerfile
declares the arg, gates the Playwright install on it, and doesn't
accidentally drop the conditional during a future refactor. Cheap to
run; doesn't actually invoke `docker build`.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile"


@pytest.fixture(scope="module")
def dockerfile_text() -> str:
    return DOCKERFILE.read_text()


def test_dockerfile_exists(dockerfile_text):
    assert dockerfile_text.strip(), "Dockerfile is empty"


def test_include_browser_arg_declared(dockerfile_text):
    """The build arg must be declared with a default of `true` so the
    full image keeps building unchanged when the flag isn't passed."""
    assert "ARG INCLUDE_BROWSER=true" in dockerfile_text


def test_playwright_install_is_conditional(dockerfile_text):
    """`npx playwright install --with-deps chromium --only-shell` must run
    only when INCLUDE_BROWSER=true — i.e. it lives inside an `if` block
    that checks the build arg. We assert the literal install line is
    nested under such a check."""
    assert 'if [ "$INCLUDE_BROWSER" = "true" ]; then' in dockerfile_text
    install_line = "npx playwright install --with-deps chromium --only-shell"
    assert install_line in dockerfile_text

    # The install line must appear AFTER the conditional opening and
    # BEFORE its `fi` close. Cheap structural check.
    if_idx = dockerfile_text.find('if [ "$INCLUDE_BROWSER" = "true" ]; then')
    fi_idx = dockerfile_text.find("fi", if_idx)
    install_idx = dockerfile_text.find(install_line)
    assert if_idx < install_idx < fi_idx, (
        "Playwright install line is not nested inside the INCLUDE_BROWSER conditional"
    )


def test_no_unconditional_playwright_install(dockerfile_text):
    """Regression guard: a future edit must not re-introduce an
    unconditional `npx playwright install` outside the `if` block."""
    install_line = "npx playwright install --with-deps chromium --only-shell"
    occurrences = dockerfile_text.count(install_line)
    assert occurrences == 1, (
        f"Expected exactly 1 occurrence of the playwright install line "
        f"(inside the INCLUDE_BROWSER conditional), found {occurrences}"
    )
