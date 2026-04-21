from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MODULE_PARITY_CASES = [
    (
        "romance_live_episode",
        REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py",
        REPO_ROOT / "pipeline/runtime/renderers/romance_live_episode.py",
        [
            "PANEL_W",
            "PANEL_H",
            "FONT_CANDIDATES",
            "parse_args",
            "load_yaml",
            "load_font",
            "wrap_text",
            "sanitize_prompt_for_policy",
            "fal_generate",
            "download",
            "style_prompt",
            "build_prompt",
            "render_overlays",
            "compose_longscroll",
            "main",
        ],
    ),
    (
        "romance_live_overlay",
        REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001/render_webtoon_fal_live.py",
        REPO_ROOT / "pipeline/runtime/renderers/romance_live_overlay.py",
        [
            "OUT",
            "MANIFEST_PATH",
            "PANEL_W",
            "PANEL_H",
            "FONT_CANDIDATES",
            "load_yaml",
            "load_font",
            "wrap_text",
            "fal_generate",
            "download",
            "style_prompt",
            "build_prompt",
            "render_overlays",
            "compose_longscroll",
            "main",
        ],
    ),
    (
        "romance_live_overlay_vlm",
        REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001/render_webtoon_fal_live_vlm.py",
        REPO_ROOT / "pipeline/runtime/renderers/romance_live_overlay_vlm.py",
        [
            "SOURCE_MANIFEST_PATH",
            "SOURCE_RENDERED_DIR",
            "SOURCE_RAW_DIR",
            "OBSERVATION_PATH",
            "LETTERING_PATH",
            "SCROLL_PLAN_PATH",
            "OUT",
            "MANIFEST_PATH",
            "FONT_CANDIDATES",
            "load_yaml",
            "load_json",
            "load_font",
            "wrap_text",
            "fit_font",
            "normalized_box",
            "normalized_point",
            "build_lettering_index",
            "observation_index",
            "observation_target",
            "observation_zone",
            "observation_anchor",
            "default_caption_box",
            "default_speech_box",
            "build_tail",
            "draw_caption",
            "draw_speech",
            "ensure_source_panels",
            "compose_longscroll",
            "render_panel",
            "main",
        ],
    ),
    (
        "storyboard_renderer",
        REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/storyboard_renderer.py",
        REPO_ROOT / "pipeline/runtime/renderers/storyboard_renderer.py",
        [
            "FONT_CANDIDATES",
            "TITLE_FONT",
            "BODY_FONT",
            "SMALL_FONT",
            "TINY_FONT",
            "SPACING_MAP",
            "load_font",
            "wrap_text",
            "draw_gradient",
            "draw_figure",
            "draw_panel",
            "render_episode",
            "main",
        ],
    ),
    (
        "balloon_zone_analyzer",
        REPO_ROOT / "docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py",
        REPO_ROOT / "pipeline/runtime/analyzers/balloon_zone_analyzer.py",
        [
            "SCREEN_HEAVY_SHOTS",
            "SCREEN_VISUAL_HINTS",
            "PANEL_FORBIDDEN_OVERRIDES",
            "PANEL_ATTACHMENT_PROFILES",
            "BASE_ZONE_LIBRARY",
            "PANEL_SAFE_ZONE_EXTRAS",
            "parse_args",
            "classify_tracks",
            "build_forbidden_zones",
            "build_attachment_contract",
            "analyze_panel",
            "main",
        ],
    ),
    (
        "balloon_overlay_renderer",
        REPO_ROOT / "docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py",
        REPO_ROOT / "pipeline/runtime/renderers/balloon_overlay_renderer.py",
        [
            "PlacementCandidate",
            "TEMPLATE_KIND_MAP",
            "TEMPLATE_ZONE_COMPAT",
            "RENDER_ORDER",
            "parse_args",
            "load_analysis",
            "should_draw_tail",
            "render_shape",
            "render_panel",
            "main",
        ],
    ),
    (
        "balloon_layout_utils",
        REPO_ROOT / "docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py",
        REPO_ROOT / "pipeline/runtime/lib/balloon_layout_utils.py",
        [
            "DEFAULT_FONT_CANDIDATES",
            "PANEL_FILE_RE",
            "DEFAULT_PANEL_PADDING",
            "DEFAULT_BOX_GAP",
            "DEFAULT_FORBIDDEN_OVERLAP_THRESHOLD",
            "SCROLL_SPACING",
            "SpeakerStyle",
            "STYLE_MAP",
            "resolve_font_path",
            "load_font",
            "load_manifest",
            "load_lettering",
            "load_scroll_plan",
            "speech_text_safe_box",
            "speech_inner_size_for_text_bbox",
            "candidate_background_score",
            "compose_longscroll",
        ],
    ),
]


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


def test_canonical_runtime_files_exist() -> None:
    for _, _, canonical_path, _ in MODULE_PARITY_CASES:
        assert canonical_path.exists(), canonical_path


def test_canonical_runtime_modules_expose_legacy_api_surface() -> None:
    for name, legacy_path, canonical_path, expected_names in MODULE_PARITY_CASES:
        legacy = _load_module(f"legacy_{name}", legacy_path)
        canonical = _load_module(f"canonical_{name}", canonical_path)
        for attr_name in expected_names:
            assert hasattr(legacy, attr_name), f"{legacy_path} missing {attr_name}"
            assert hasattr(canonical, attr_name), f"{canonical_path} missing {attr_name}"


def test_canonical_runtime_function_signatures_match_legacy() -> None:
    signature_names = {
        "parse_args",
        "load_yaml",
        "load_json",
        "load_font",
        "wrap_text",
        "fit_font",
        "sanitize_prompt_for_policy",
        "download",
        "style_prompt",
        "build_prompt",
        "render_overlays",
        "compose_longscroll",
        "render_panel",
        "render_episode",
        "draw_caption",
        "draw_speech",
        "load_manifest",
        "load_lettering",
        "load_scroll_plan",
        "resolve_font_path",
        "speech_text_safe_box",
        "speech_inner_size_for_text_bbox",
        "candidate_background_score",
        "classify_tracks",
        "build_forbidden_zones",
        "build_attachment_contract",
        "analyze_panel",
        "should_draw_tail",
        "render_shape",
        "main",
    }
    for name, legacy_path, canonical_path, _ in MODULE_PARITY_CASES:
        legacy = _load_module(f"legacy_sig_{name}", legacy_path)
        canonical = _load_module(f"canonical_sig_{name}", canonical_path)
        for attr_name in signature_names:
            if not hasattr(legacy, attr_name):
                continue
            legacy_attr = getattr(legacy, attr_name)
            canonical_attr = getattr(canonical, attr_name)
            if callable(legacy_attr) and callable(canonical_attr):
                assert inspect.signature(canonical_attr) == inspect.signature(legacy_attr), (
                    f"{canonical_path}:{attr_name} signature drifted from legacy"
                )


def test_canonical_runtime_path_constants_point_at_legacy_data_locations() -> None:
    overlay = _load_module(
        "canonical_runtime_overlay_paths",
        REPO_ROOT / "pipeline/runtime/renderers/romance_live_overlay.py",
    )
    assert overlay.BASE == REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001"
    assert overlay.OUT == overlay.BASE / "generated_fal_live_ep001"
    assert overlay.MANIFEST_PATH == overlay.BASE / "generated_fal_live_manifest.json"

    overlay_vlm = _load_module(
        "canonical_runtime_overlay_vlm_paths",
        REPO_ROOT / "pipeline/runtime/renderers/romance_live_overlay_vlm.py",
    )
    assert overlay_vlm.BASE == REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001"
    assert overlay_vlm.SOURCE_MANIFEST_PATH == overlay_vlm.BASE / "generated_fal_live_manifest.json"
    assert overlay_vlm.OUT == overlay_vlm.BASE / "generated_fal_live_ep001_vlm"

    storyboard = _load_module(
        "canonical_runtime_storyboard_paths",
        REPO_ROOT / "pipeline/runtime/renderers/storyboard_renderer.py",
    )
    assert storyboard.BASE == REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421"


def test_canonical_balloon_modules_use_canonical_lib_directory() -> None:
    analyzer = _load_module(
        "canonical_runtime_balloon_analyzer_paths",
        REPO_ROOT / "pipeline/runtime/analyzers/balloon_zone_analyzer.py",
    )
    renderer = _load_module(
        "canonical_runtime_balloon_renderer_paths",
        REPO_ROOT / "pipeline/runtime/renderers/balloon_overlay_renderer.py",
    )
    expected_lib = REPO_ROOT / "pipeline/runtime/lib"
    assert analyzer.CANONICAL_LIB == expected_lib
    assert renderer.CANONICAL_LIB == expected_lib
