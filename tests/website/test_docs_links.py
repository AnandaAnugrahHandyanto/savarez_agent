"""Tests for docs link integrity.

Regression tests for:
- https://github.com/NousResearch/hermes-agent/issues/24108
  Three broken /docs/... links across the docs site
"""

import re
from pathlib import Path

import pytest


class TestDocsLinkIntegrity:
    """Regression tests for the three links described in issue #24108.

    Issue summary:
    1. cron-script-only.md lines 236/244: /docs/user-guide/features/webhooks
       → should be /docs/user-guide/messaging/webhooks
    2. mlops-hermes-atropos-environments.md line 24: /docs/user-guide/skills/bundled/mlops/
       → should be /docs/user-guide/skills/optional/mlops/
    """

    @pytest.fixture
    def docs_root(self):
        return Path(__file__).parent.parent.parent / "website" / "docs"

    def _resolve_link(self, link: str, docs_root: Path) -> Path:
        """Resolve a /docs/ link to an actual filesystem path.

        Takes a link like /docs/guides/foo (no .md extension) and returns the
        actual file by trying:
          1. Exact path (guides/foo)
          2. With .md appended (guides/foo.md)
          3. As a directory index (guides/foo/index.md)
        """
        suffix = link.lstrip("/").replace("docs/", "", 1)
        candidate = docs_root / suffix

        if not candidate.exists() and not suffix.endswith(".md"):
            # Link omits the .md extension — infer it from the actual file
            md_candidate = candidate.with_suffix(".md")
            if md_candidate.exists():
                return md_candidate

            # Maybe it's a directory index page (e.g. /docs/guides/foo → foo/index.md)
            index_candidate = candidate / "index.md"
            if index_candidate.exists():
                return index_candidate

        return candidate

    def _all_links_in(self, content: str) -> list[str]:
        """Extract all /docs/ link targets from markdown content.

        Only matches bracketed links (not images), strips fragment/query parts.
        """
        # Only match [...]() not ...![]() — images are decorative, not navigation links
        raw_links = re.findall(r'\[([^\]]*)\]\((/docs[^\)]+)\)', content)
        links = []
        for _label, href in raw_links:
            clean = href.split("#")[0].split("?")[0]
            if clean:
                links.append(clean)
        return links

    # ----- Specific broken-link regressions (issue #24108) -----

    def test_cron_script_only_webhook_link_points_to_messaging(self, docs_root):
        """Line 236+244 of cron-script-only.md must link to messaging/webhooks.

        The old broken link was /docs/user-guide/features/webhooks.
        The correct link is /docs/user-guide/messaging/webhooks.
        """
        f = docs_root / "guides" / "cron-script-only.md"
        lines = f.read_text(encoding="utf-8").splitlines()

        # Collect every line that has both a webhook mention and a /docs/ link
        webhook_lines = [
            l for l in lines
            if "webhook" in l.lower() and "/docs/user-guide" in l
        ]
        assert webhook_lines, "Expected to find webhook links in cron-script-only.md"

        for line in webhook_lines:
            assert "/docs/user-guide/messaging/webhooks" in line, (
                f"Expected /docs/user-guide/messaging/webhooks in cron-script-only.md, got: {line.strip()}"
            )

    def test_cron_script_only_no_longer_has_features_webhooks(self, docs_root):
        """cron-script-only.md must NOT contain the broken /docs/user-guide/features/webhooks."""
        f = docs_root / "guides" / "cron-script-only.md"
        content = f.read_text(encoding="utf-8")
        assert "/docs/user-guide/features/webhooks" not in content, (
            "cron-script-only.md still contains the broken link /docs/user-guide/features/webhooks"
        )

    def test_atropos_environments_has_no_bundled_links(self, docs_root):
        """mlops-hermes-atropos-environments.md must NOT link to skills/bundled/mlops/."""
        f = docs_root / "user-guide" / "skills" / "optional" / "mlops" / "mlops-hermes-atropos-environments.md"
        content = f.read_text(encoding="utf-8")
        assert "/docs/user-guide/skills/bundled/mlops/" not in content, (
            "mlops-hermes-atropos-environments.md still contains broken links to skills/bundled/mlops/"
        )

    def test_atropos_environments_has_optional_links(self, docs_root):
        """mlops-hermes-atropos-environments.md should link to skills/optional/mlops/."""
        f = docs_root / "user-guide" / "skills" / "optional" / "mlops" / "mlops-hermes-atropos-environments.md"
        content = f.read_text(encoding="utf-8")
        assert "/docs/user-guide/skills/optional/mlops/" in content, (
            "mlops-hermes-atropos-environments.md should link to skills/optional/mlops/"
        )

    # ----- Link resolution unit tests -----

    def test_messaging_webhooks_resolves(self, docs_root):
        """/docs/user-guide/messaging/webhooks should resolve to a real file."""
        resolved = self._resolve_link("/docs/user-guide/messaging/webhooks", docs_root)
        assert resolved.exists(), f"messaging/webhooks does not exist at {resolved}"

    def test_optional_mlops_axolotl_resolves(self, docs_root):
        """/docs/user-guide/skills/optional/mlops/mlops-training-axolotl should resolve."""
        resolved = self._resolve_link("/docs/user-guide/skills/optional/mlops/mlops-training-axolotl", docs_root)
        assert resolved.exists(), f"optional/mlops/mlops-training-axolotl does not exist at {resolved}"

    def test_optional_mlops_trl_resolves(self, docs_root):
        """/docs/user-guide/skills/optional/mlops/mlops-training-trl-fine-tuning should resolve."""
        resolved = self._resolve_link("/docs/user-guide/skills/optional/mlops/mlops-training-trl-fine-tuning", docs_root)
        assert resolved.exists(), f"optional/mlops/mlops-training-trl-fine-tuning does not exist at {resolved}"

    def test_cron_script_only_all_links_are_valid(self, docs_root):
        """Every /docs/ link in cron-script-only.md must resolve to a real file."""
        f = docs_root / "guides" / "cron-script-only.md"
        content = f.read_text(encoding="utf-8")

        broken = []
        for link in self._all_links_in(content):
            resolved = self._resolve_link(link, docs_root)
            if not resolved.exists():
                broken.append((link, str(resolved)))

        assert not broken, (
            "cron-script-only.md has broken links:\n" +
            "\n".join(f"  {l} → {r}" for l, r in broken)
        )