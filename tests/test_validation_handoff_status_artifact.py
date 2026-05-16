from html.parser import HTMLParser
from pathlib import Path


class _TextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


def test_validation_handoff_status_artifact_names_pr_25209():
    path = Path("docs/status/validation-contract-handoff-2026-05-13.html")
    assert path.exists()

    parser = _TextCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    text = " ".join(parser.parts)

    assert "PR #25209" in text
    assert "codex/validation-contract-docs" in text
    assert "Do not duplicate #25209" in text
    assert "stale relative to origin/main" in text
    assert "does not change the wrapper, runner, website sidebar, or validation-contract guide" in text
