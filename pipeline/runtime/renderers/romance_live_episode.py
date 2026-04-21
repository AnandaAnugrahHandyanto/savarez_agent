from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
import re
from typing import Any

import requests
import time
import yaml
from PIL import Image, ImageDraw, ImageFont

PANEL_W = 720
PANEL_H = 1080
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="render_webtoon_fal_live_episode.py",
        description="Render one romance webtoon episode with live fal generation.",
    )
    parser.add_argument("--episode-dir", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-name", default=None)
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def sanitize_prompt_for_policy(prompt: str) -> str:
    replacements = {
        "떨리는 손": "긴장한 손",
        "모의고사 시험지": "모의고사 준비 노트",
        "학생증 자국": "빈 벤치의 흔적",
        "마지막 메시지": "휴대폰 화면",
        "복도에서 시윤을 보는 소라": "복도에서 남학생을 바라보는 여학생",
        "계약학과 건물 뒤 벤치": "캠퍼스 건물 뒤 벤치",
    }
    sanitized = prompt
    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)
    sanitized = re.sub(r"\b\d+세\b", "college-age", sanitized)
    sanitized = sanitized.replace("지방 국립대", "university")
    sanitized = sanitized.replace("반수생", "student")
    sanitized = sanitized.replace("약대", "top admissions track")
    sanitized = sanitized.replace("강시윤", "male student")
    sanitized = sanitized.replace("윤서하", "female student")
    sanitized = sanitized.replace("한소라", "female student")
    sanitized = sanitized.replace("조민우", "male student")
    sanitized = sanitized.replace("시윤의 어머니", "middle-aged Korean woman")
    sanitized = sanitized.replace("시윤", "male student")
    sanitized = sanitized.replace("서하", "female student")
    sanitized = sanitized.replace("소라", "female student")
    sanitized = re.sub(r"\s+", " ", sanitized).strip(" ,")
    return sanitized


def fal_generate(prompt: str) -> tuple[str, str]:
    import fal_client

    arguments = {
        "prompt": prompt,
        "image_size": {"width": PANEL_W, "height": PANEL_H},
        "num_images": 1,
        "output_format": "png",
    }
    try:
        result = fal_client.subscribe("fal-ai/flux-2-pro", arguments=arguments)
        return result["images"][0]["url"], prompt
    except Exception as exc:
        if "content_policy_violation" not in str(exc):
            raise
        sanitized_prompt = sanitize_prompt_for_policy(prompt)
        result = fal_client.subscribe(
            "fal-ai/flux-2-pro",
            arguments={**arguments, "prompt": sanitized_prompt},
        )
        return result["images"][0]["url"], sanitized_prompt


def download(url: str, path: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = requests.get(url, timeout=180)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            return
        except Exception as exc:
            last_error = exc
            if attempt == 5:
                raise
            time.sleep(2 * attempt)
    if last_error:
        raise last_error


def style_prompt(panel_data: dict[str, Any]) -> str:
    positive = panel_data["style_anchor"]["positive"]
    negative = ", ".join(panel_data["style_anchor"]["negative"])
    return (
        f"{positive}, clean Korean romance webtoon cartoon illustration, 2D cel shading, "
        f"polished digital manhwa style, no readable text, no speech bubbles, no letters, avoid {negative}"
    )


def build_prompt(panel_data: dict[str, Any], panel_spec: dict[str, Any]) -> str:
    chars = []
    for key in panel_spec.get("visible_characters", []):
        info = panel_data["characters"].get(key, {})
        chars.append(f"{info.get('role', key)} with {info.get('visual', '')}")
    char_block = ", ".join(chars)
    return ", ".join(
        p for p in [
            style_prompt(panel_data),
            panel_spec["prompt"],
            char_block,
            "mobile vertical webtoon panel with strong facial acting and clean composition",
        ] if p
    )


def render_overlays(img_path: Path, panel_id: str, lettering: dict[str, Any]) -> None:
    image = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    caption_font = load_font(28)
    balloon_font = load_font(30)

    captions = {c["panel_id"]: c["text"] for c in lettering.get("captions", [])}
    balloons = [b for b in lettering.get("balloons", []) if b["panel_id"] == panel_id]

    if panel_id in captions:
        text = captions[panel_id]
        lines = wrap_text(draw, text, caption_font, PANEL_W - 140)
        box_h = 26 + len(lines) * 36 + 24
        box = (50, 56, PANEL_W - 50, 56 + box_h)
        draw.rounded_rectangle(box, radius=24, fill=(10, 10, 10, 200))
        y = box[1] + 20
        for line in lines:
            draw.text((box[0] + 24, y), line, font=caption_font, fill=(255, 255, 255, 255))
            y += 36

    top = PANEL_H - 250
    for balloon in balloons:
        lines = wrap_text(draw, balloon["text"], balloon_font, PANEL_W - 260)
        box_h = 30 + len(lines) * 38 + 28
        box = (100, top, PANEL_W - 100, top + box_h)
        draw.rounded_rectangle(box, radius=46, fill=(248, 248, 248, 235), outline=(20, 20, 20, 255), width=3)
        y = top + 22
        for line in lines:
            draw.text((box[0] + 40, y), line, font=balloon_font, fill=(25, 25, 25, 255))
            y += 38
        top -= box_h + 36

    image.convert("RGB").save(img_path)


def compose_longscroll(panel_paths: list[Path], scroll_plan: dict[str, Any], out_path: Path) -> None:
    spacing_map = {block["block_id"]: block.get("spacing", "medium") for block in scroll_plan["blocks"]}
    gap_px = {"tight": 30, "medium": 70, "tall_drop": 180, "end_cliff": 260}
    blocks = {f"p{i:02d}": block["block_id"] for i, block in enumerate(scroll_plan["blocks"], start=1)}
    images = []
    total_h = 0
    panel_ids = [f"p{i:02d}" for i in range(1, len(panel_paths) + 1)]

    for idx, panel_path in enumerate(panel_paths):
        img = Image.open(panel_path).convert("RGB")
        panel_id = panel_ids[idx]
        gap = gap_px.get(spacing_map.get(blocks[panel_id], "medium"), 70)
        images.append((img, gap))
        total_h += img.height
        if idx < len(panel_paths) - 1:
            total_h += gap

    canvas = Image.new("RGB", (PANEL_W, total_h), (244, 244, 244))
    y = 0
    for idx, (img, gap) in enumerate(images):
        canvas.paste(img, (0, y))
        y += img.height
        if idx < len(images) - 1:
            y += gap
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main() -> None:
    args = parse_args()
    episode_dir = Path(args.episode_dir).resolve()
    project_root = Path(args.project_root).resolve()
    episode = episode_dir.name
    panel_data = load_yaml(episode_dir / "panel_prompts.yaml")
    lettering = load_yaml(episode_dir / "lettering_script.yaml")
    scroll_plan = load_yaml(episode_dir / "scroll_plan.yaml")

    generated_dir = episode_dir / f"generated_fal_live_{episode}"
    generated_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = episode_dir / f"generated_fal_live_manifest_{episode}.json"

    renders_dir = project_root / "renders" / episode
    panels_dir = renders_dir / "panels"
    panels_dir.mkdir(parents=True, exist_ok=True)
    longscroll_path = renders_dir / f"{episode}_longscroll.png"

    manifest: dict[str, Any] = {"episode": episode, "mode": "fal_live_flux2_pro", "panels": []}
    panel_paths: list[Path] = []

    for panel_spec in panel_data["panels"]:
        panel_id = panel_spec["panel_id"]
        prompt = build_prompt(panel_data, panel_spec)
        url, final_prompt = fal_generate(prompt)
        generated_panel_path = generated_dir / f"{panel_id}.png"
        download(url, generated_panel_path)
        render_overlays(generated_panel_path, panel_id, lettering)
        final_panel_path = panels_dir / f"{panel_id}.png"
        shutil.copy2(generated_panel_path, final_panel_path)
        panel_paths.append(final_panel_path)
        manifest["panels"].append({
            "panel_id": panel_id,
            "prompt": prompt,
            "final_prompt": final_prompt,
            "url": url,
            "generated_panel_path": str(generated_panel_path.resolve()),
            "final_panel_path": str(final_panel_path.resolve()),
        })

    compose_longscroll(panel_paths, scroll_plan, longscroll_path)
    manifest["longscroll"] = str(longscroll_path.resolve())
    manifest["generated_dir"] = str(generated_dir.resolve())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"episode": episode, "panel_count": len(panel_paths), "longscroll": str(longscroll_path.resolve()), "manifest": str(manifest_path.resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
