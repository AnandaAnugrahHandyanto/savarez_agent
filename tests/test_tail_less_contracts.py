from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageChops

REPO_ROOT = Path(__file__).resolve().parents[1]
TREND_RENDERER = REPO_ROOT / "docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py"
ROMANCE_RENDERER = REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001/render_webtoon_fal_live.py"
ROMANCE_VLM_RENDERER = REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001/render_webtoon_fal_live_vlm.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_trend_renderer_should_not_draw_speech_tails() -> None:
    renderer = _load_module("trend_tail_less_renderer", TREND_RENDERER)

    placement = renderer.PlacementCandidate(
        item={"id": "l01", "kind": "dialogue", "text": "테스트"},
        template="speech",
        bubble_kind="speech",
        speaker="mother",
        box=(80, 80, 280, 180),
        inner_box=(110, 100, 250, 160),
        score=0.0,
        zone_id="z01",
        zone_kind="speech",
        confidence=1.0,
        font_size=24,
        lines=["테스트"],
        tail_points=[(120, 176), (160, 176), (140, 220)],
        tail_entry_edge="bottom",
        tail_cross_ratio=0.0,
        overlap_metrics=[],
        selected_with_warning=False,
        warning_reason=None,
        candidate_class="speaker_local",
        resolved_anchor_id="mother_mouth_primary",
        resolved_anchor_role="mouth",
        selected_zone_score=0.0,
        score_breakdown={},
        fallback_reason=None,
        review_reasons=[],
    )

    assert renderer.should_draw_tail(placement) is False


def test_romance_live_overlay_does_not_paint_tail_pixels(tmp_path: Path) -> None:
    renderer = _load_module("romance_tail_less_renderer", ROMANCE_RENDERER)
    image_path = tmp_path / "panel.png"
    Image.new("RGB", (renderer.PANEL_W, renderer.PANEL_H), (255, 255, 255)).save(image_path)

    lettering = {
        "captions": [],
        "balloons": [
            {"panel_id": "p99", "text": "학교 어디 다녀?"},
        ],
    }

    renderer.render_overlays(image_path, "p99", lettering)
    rendered = Image.open(image_path).convert("RGB")

    tail_probe = rendered.crop((180, renderer.PANEL_H - 140, 260, renderer.PANEL_H - 70))
    assert not ImageChops.difference(tail_probe, Image.new("RGB", tail_probe.size, (255, 255, 255))).getbbox()


def test_romance_live_vlm_draw_speech_is_tail_less() -> None:
    renderer = _load_module("romance_tail_less_vlm_renderer", ROMANCE_VLM_RENDERER)
    image = Image.new("RGBA", (720, 1080), (255, 255, 255, 255))
    box = (100, 700, 620, 860)
    result = renderer.draw_speech(image, box, "반수하는 사람은 연애할 시간 없지 않나.", (160, 940))

    assert result.get("tail_points") in (None, [])
    tail_probe = image.crop((130, 870, 230, 980))
    assert not ImageChops.difference(tail_probe, Image.new("RGBA", tail_probe.size, (255, 255, 255, 255))).getbbox()
