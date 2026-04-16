from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LANDINGPAGE_DIR = PROJECT_ROOT / "landingpage"
MANIFEST_PATH = LANDINGPAGE_DIR / "manifest.webmanifest"
TODO_PATH = PROJECT_ROOT / "TODO.md"
EXPECTED_MASKABLE_PATH = "icon-maskable-512.png"


def test_manifest_uses_dedicated_maskable_icon() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    maskable_icons = [
        icon for icon in manifest["icons"] if icon.get("purpose") == "maskable"
    ]

    assert maskable_icons == [
        {
            "src": EXPECTED_MASKABLE_PATH,
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        }
    ]
    assert maskable_icons[0]["src"] != "icon-512.png"
    assert (LANDINGPAGE_DIR / EXPECTED_MASKABLE_PATH).is_file()


def test_index_links_manifest() -> None:
    index_html = (LANDINGPAGE_DIR / "index.html").read_text(encoding="utf-8")

    assert '<link rel="manifest" href="manifest.webmanifest" />' in index_html


def test_todo_note_matches_raster_icon_reality() -> None:
    todo_text = TODO_PATH.read_text(encoding="utf-8")

    assert "apple-touch-icon.png" in todo_text
    assert "manifest.webmanifest" in todo_text
    assert "SVG" not in todo_text
