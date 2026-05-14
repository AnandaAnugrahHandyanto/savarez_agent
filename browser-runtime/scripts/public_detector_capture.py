#!/usr/bin/env python3
"""Capture public detector screenshots and build redacted manifests.

The manifest is public-redacted comparison evidence. It keeps detector names,
capture counts, and screenshot nonblank metadata while removing public IP
literals, stable hashes, CDP/takeover capability URLs, cookies, tokens,
authorization headers, and private paths from text fields.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import json
import re
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "hbr.p4.public_detector_capture.v1"
REDACTED = "[REDACTED]"
IP_LITERAL_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DETECTOR_HASH_RE = re.compile(r"\b[a-fA-F0-9]{32,128}\b")
CDP_WS_RE = re.compile(r"wss?://[^\s\"'<>]+/devtools/browser/[^\s\"'<>]+", re.IGNORECASE)
TAKEOVER_TOKEN_RE = re.compile(r"https?://[^\s\"'<>]+/takeover/[^\s\"'<>]+", re.IGNORECASE)
TOKEN_RE = re.compile(r"(?i)\btoken=[^\s&\"'<>]+")
COOKIE_RE = re.compile(r"(?i)\bcookie=[^\s&\"'<>]+")
AUTH_RE = re.compile(r"(?i)\bAuthorization\s*:\s*[^\n\r]+")
HOME_PATH_RE = re.compile(r"/(?:home|Users)/[^\s\"'<>]+")
WINDOWS_USER_PATH_RE = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\s\"'<>]+")
PRIVATE_RUNTIME_PATH_RE = re.compile(r"[^\s\"'<>]*runtime-data/(?:profiles|tmp)[^\s\"'<>]*")

# Keep the default harness list aligned with the P4 public detector baseline
# run-20260512T113556Z. public_detector_compare intentionally treats slug-set
# changes as coverage deltas, so additions like fpscanner must not replace a
# baseline detector in DEFAULT_TESTS.
DEFAULT_TESTS = [
    {"slug": "browserleaks-ip", "title": "BrowserLeaks — IP", "url": "https://browserleaks.com/ip", "wait_secs": 12},
    {"slug": "browserleaks-dns", "title": "BrowserLeaks — DNS", "url": "https://browserleaks.com/dns", "wait_secs": 18},
    {"slug": "browserleaks-webrtc", "title": "BrowserLeaks — WebRTC", "url": "https://browserleaks.com/webrtc", "wait_secs": 12},
    {"slug": "browserleaks-canvas", "title": "BrowserLeaks — Canvas", "url": "https://browserleaks.com/canvas", "wait_secs": 10},
    {"slug": "browserleaks-webgl", "title": "BrowserLeaks — WebGL", "url": "https://browserleaks.com/webgl", "wait_secs": 12},
    {"slug": "browserleaks-fonts", "title": "BrowserLeaks — Fonts", "url": "https://browserleaks.com/fonts", "wait_secs": 12},
    {
        "slug": "browserleaks-javascript",
        "title": "BrowserLeaks — JavaScript",
        "url": "https://browserleaks.com/javascript",
        "wait_secs": 12,
    },
    {"slug": "browserleaks-tls", "title": "BrowserLeaks — TLS fingerprint", "url": "https://browserleaks.com/tls", "wait_secs": 12},
    {"slug": "creepjs", "title": "CreepJS", "url": "https://abrahamjuliot.github.io/creepjs/", "wait_secs": 32},
    {"slug": "sannysoft", "title": "bot.sannysoft", "url": "https://bot.sannysoft.com/", "wait_secs": 16},
    {"slug": "pixelscan-fingerprint", "title": "Pixelscan — fingerprint check", "url": "https://pixelscan.net/fingerprint-check", "wait_secs": 24},
    {"slug": "pixelscan-bot", "title": "Pixelscan — bot check", "url": "https://pixelscan.net/bot-check", "wait_secs": 24},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-json", type=Path, help="session create JSON with live cdp_ws_url for detector capture")
    parser.add_argument("--out-dir", type=Path, required=True, help="detector run directory")
    parser.add_argument(
        "--results-json",
        type=Path,
        help="optional precomputed detector result list JSON; skips live CDP capture and only builds a manifest",
    )
    parser.add_argument("--manifest", type=Path, help="output manifest path; defaults to <out-dir>/manifest.json")
    parser.add_argument("--viewport-width", type=int, default=1440, help="initial detector viewport width")
    parser.add_argument("--viewport-height", type=int, default=1000, help="initial detector viewport height")
    parser.add_argument("--max-height", type=int, default=12000, help="maximum full-page screenshot capture height")
    parser.add_argument(
        "--strict-nonblank",
        action="store_true",
        help="write the manifest, then exit non-zero unless every attempted detector has a nonblank screenshot",
    )
    args = parser.parse_args()
    if args.results_json is None and args.session_json is None:
        parser.error("one of --session-json or --results-json is required")
    return args


def valid_ip_literal(value: str) -> bool:
    octets = value.split(".")
    return len(octets) == 4 and all(octet.isdigit() and 0 <= int(octet) <= 255 for octet in octets)


def redact_text(text: str) -> str:
    text = CDP_WS_RE.sub("[REDACTED_CDP_URL]", text)
    text = TAKEOVER_TOKEN_RE.sub("[REDACTED_TAKEOVER_URL]", text)
    text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = COOKIE_RE.sub("[REDACTED_COOKIE]", text)
    text = AUTH_RE.sub("[REDACTED_AUTH]", text)
    text = PRIVATE_RUNTIME_PATH_RE.sub("[REDACTED_PRIVATE_PATH]", text)
    text = HOME_PATH_RE.sub("[REDACTED_PRIVATE_PATH]", text)
    text = WINDOWS_USER_PATH_RE.sub("[REDACTED_PRIVATE_PATH]", text)
    text = DETECTOR_HASH_RE.sub("[REDACTED_HASH]", text)

    def redact_ip(match: re.Match[str]) -> str:
        value = match.group(0)
        return "[REDACTED_IP]" if valid_ip_literal(value) else value

    return IP_LITERAL_RE.sub(redact_ip, text)


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value


def relative_or_name(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


SAFE_SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def canonical_screenshot_file(index: int, path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SAFE_SCREENSHOT_EXTENSIONS:
        suffix = ".png"
    return f"screenshot-{index:03d}{suffix}"


def canonical_screenshot_path(index: int, path: Path) -> str:
    return f"screenshots/{canonical_screenshot_file(index, path)}"


def image_stats(path: Path, *, public_file: str | None = None) -> dict[str, Any]:
    file_name = public_file or redact_text(path.name)
    if not path.exists():
        return {"file": file_name, "exists": False, "nonblank": False}
    try:
        from PIL import Image, ImageStat  # type: ignore[import-not-found]

        with Image.open(path) as image:
            grayscale = image.convert("L")
            stat = ImageStat.Stat(grayscale)
            extrema = grayscale.getextrema()
            nonblank = bool(extrema and extrema[0] != extrema[1])
            return {
                "file": file_name,
                "exists": True,
                "width": image.width,
                "height": image.height,
                "size_bytes": path.stat().st_size,
                "stddev": round(float(stat.stddev[0]), 2),
                "nonblank": nonblank,
            }
    except Exception as exc:  # pragma: no cover - depends on image codecs
        return {"file": file_name, "exists": True, "nonblank": False, "error": type(exc).__name__}


def result_screenshot_path(result: dict[str, Any]) -> Path | None:
    screenshot = result.get("screenshot")
    if isinstance(screenshot, dict) and screenshot.get("path"):
        return Path(str(screenshot["path"]))
    if isinstance(screenshot, str) and screenshot:
        return Path(screenshot)
    if result.get("screenshot_path"):
        return Path(str(result["screenshot_path"]))
    return None


def sanitize_result(result: dict[str, Any], *, index: int) -> tuple[dict[str, Any], bool, bool]:
    sanitized: dict[str, Any] = {}
    for key in ("slug", "title", "url", "url_after", "page_title", "ok", "error"):
        if key in result:
            sanitized[key] = redact_value(result[key])

    screenshot_path = result_screenshot_path(result)
    captured = bool(result.get("ok")) and screenshot_path is not None
    nonblank = False
    if screenshot_path is not None:
        stats = image_stats(screenshot_path, public_file=canonical_screenshot_file(index, screenshot_path))
        stats["path"] = canonical_screenshot_path(index, screenshot_path)
        nonblank = bool(stats.get("nonblank"))
        sanitized["screenshot"] = stats

    if isinstance(result.get("detector_summary"), dict):
        sanitized["detector_summary"] = redact_value(result["detector_summary"])
    sanitized["raw_values_redacted"] = True
    return sanitized, captured, nonblank


def build_manifest(out_dir: Path, results: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
    out_dir = out_dir.resolve()
    detectors: list[dict[str, Any]] = []
    captured_count = 0
    nonblank_count = 0
    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            continue
        sanitized, captured, nonblank = sanitize_result(result, index=index)
        detectors.append(sanitized)
        captured_count += int(captured)
        nonblank_count += int(nonblank)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "out_dir": out_dir.name,
        "config": redact_value(config or {}),
        "counts": {
            "attempted": len(results),
            "captured": captured_count,
            "nonblank": nonblank_count,
        },
        "detectors": detectors,
        "redaction_policy": [
            "public IP literals",
            "stable detector hashes",
            "CDP/takeover capability URLs",
            "cookies, authorization headers, and tokens",
            "private filesystem and runtime profile paths",
        ],
    }


class CDP:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws: Any = None
        self.next_id = 0
        self.pending: dict[int, asyncio.Future[Any]] = {}
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.reader_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> CDP:
        try:
            import websockets  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on optional live-capture dependency
            raise RuntimeError("websockets is required for --session-json live detector capture") from exc
        self.ws = await websockets.connect(self.ws_url, max_size=64 * 1024 * 1024)
        self.reader_task = asyncio.create_task(self._reader())
        return self

    async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()

    async def _reader(self) -> None:
        assert self.ws is not None
        async for message in self.ws:
            data = json.loads(message)
            if "id" in data and data["id"] in self.pending:
                fut = self.pending.pop(data["id"])
                if "error" in data:
                    fut.set_exception(RuntimeError(data["error"]))
                else:
                    fut.set_result(data.get("result", {}))
            else:
                await self.events.put(data)

    async def send(self, method: str, params: dict[str, Any] | None = None, *, session_id: str | None = None) -> Any:
        self.next_id += 1
        msg: dict[str, Any] = {"id": self.next_id, "method": method}
        if params is not None:
            msg["params"] = params
        if session_id:
            msg["sessionId"] = session_id
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.next_id] = fut
        assert self.ws is not None
        await self.ws.send(json.dumps(msg))
        return await fut

    async def drain_events(self) -> None:
        while not self.events.empty():
            try:
                self.events.get_nowait()
            except asyncio.QueueEmpty:
                break


async def attach_page(cdp: CDP) -> tuple[str, str]:
    targets = (await cdp.send("Target.getTargets")).get("targetInfos", [])
    page_targets = [target for target in targets if target.get("type") == "page"]
    if page_targets:
        target_id = page_targets[0]["targetId"]
    else:
        target_id = (await cdp.send("Target.createTarget", {"url": "about:blank"}))["targetId"]
    attached = await cdp.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
    return target_id, attached["sessionId"]


async def wait_for_ready(cdp: CDP, session_id: str, wait_secs: int) -> dict[str, Any]:
    deadline = time.monotonic() + wait_secs
    last_state = "unknown"
    while time.monotonic() < deadline:
        try:
            res = await cdp.send(
                "Runtime.evaluate",
                {"expression": "document.readyState", "returnByValue": True},
                session_id=session_id,
            )
            last_state = res.get("result", {}).get("value", "unknown")
        except Exception:
            pass
        if last_state == "complete" and time.monotonic() + 3 < deadline:
            await asyncio.sleep(min(3, max(0, deadline - time.monotonic())))
        else:
            await asyncio.sleep(1)
    info: dict[str, Any] = {"readyState": last_state}
    try:
        title = await cdp.send(
            "Runtime.evaluate",
            {"expression": "document.title", "returnByValue": True},
            session_id=session_id,
        )
        info["title"] = redact_value(title.get("result", {}).get("value"))
    except Exception as exc:
        info["title_error"] = redact_text(str(exc))
    try:
        url_after = await cdp.send(
            "Runtime.evaluate",
            {"expression": "location.href", "returnByValue": True},
            session_id=session_id,
        )
        info["url_after"] = redact_value(url_after.get("result", {}).get("value"))
    except Exception as exc:
        info["url_error"] = redact_text(str(exc))
    try:
        text = await cdp.send(
            "Runtime.evaluate",
            {"expression": "document.body ? document.body.innerText : ''", "returnByValue": True},
            session_id=session_id,
        )
        info["body_text_sample"] = redact_text(str(text.get("result", {}).get("value") or ""))[:3000]
    except Exception as exc:
        info["text_error"] = redact_text(str(exc))
    return info


async def capture_png(cdp: CDP, session_id: str, out_path: Path, *, max_height: int) -> dict[str, Any]:
    metrics = await cdp.send("Page.getLayoutMetrics", session_id=session_id)
    content = metrics.get("contentSize") or {}
    width = max(800, min(int(content.get("width") or 1440), 2200))
    height = max(800, int(content.get("height") or 1000))
    clipped_height = min(height, max_height)
    await cdp.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": clipped_height, "deviceScaleFactor": 1, "mobile": False},
        session_id=session_id,
    )
    await asyncio.sleep(0.4)
    params: dict[str, Any] = {
        "format": "png",
        "fromSurface": True,
        "captureBeyondViewport": True,
        "clip": {"x": 0, "y": 0, "width": width, "height": clipped_height, "scale": 1},
    }
    result = await cdp.send("Page.captureScreenshot", params, session_id=session_id)
    png = base64.b64decode(result["data"])
    out_path.write_bytes(png)
    return {
        "path": str(out_path),
        "width": width,
        "content_height": height,
        "captured_height": clipped_height,
        "size_bytes": len(png),
    }


async def capture_detector_results(args: argparse.Namespace) -> list[dict[str, Any]]:
    assert args.session_json is not None
    session = json.loads(args.session_json.read_text(encoding="utf-8"))
    ws_url = session.get("cdp_ws_url") if isinstance(session, dict) else None
    if not isinstance(ws_url, str) or not ws_url:
        raise SystemExit("--session-json must contain a cdp_ws_url string")
    out_dir = args.out_dir
    screenshots_dir = out_dir / "screenshots"
    raw_dir = out_dir / "raw"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    async with CDP(ws_url) as cdp:
        _target_id, session_id = await attach_page(cdp)
        await cdp.send("Page.enable", session_id=session_id)
        await cdp.send("Runtime.enable", session_id=session_id)
        await cdp.send("Network.enable", session_id=session_id)
        await cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": args.viewport_width,
                "height": args.viewport_height,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
            session_id=session_id,
        )
        await cdp.send("Page.bringToFront", session_id=session_id)
        for index, test in enumerate(DEFAULT_TESTS, start=1):
            slug = test["slug"]
            url = test["url"]
            print(f"[{index:02d}/{len(DEFAULT_TESTS)}] {slug}: {url}", flush=True)
            record: dict[str, Any] = {
                "slug": slug,
                "title": test["title"],
                "url": url,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            try:
                await cdp.drain_events()
                await cdp.send("Page.navigate", {"url": url}, session_id=session_id)
                info = await wait_for_ready(cdp, session_id, int(test["wait_secs"]))
                png_path = screenshots_dir / f"{index:02d}-{slug}.png"
                shot = await capture_png(cdp, session_id, png_path, max_height=args.max_height)
                record.update(
                    {
                        "ok": True,
                        "page": info,
                        "page_title": info.get("title"),
                        "url_after": info.get("url_after"),
                        "screenshot": shot,
                    }
                )
            except Exception as exc:
                record.update({"ok": False, "error": redact_text(str(exc))[:2000]})
                try:
                    png_path = screenshots_dir / f"{index:02d}-{slug}-error.png"
                    record["screenshot"] = await capture_png(cdp, session_id, png_path, max_height=args.max_height)
                except Exception as shot_exc:
                    record["screenshot_error"] = redact_text(str(shot_exc))[:1000]
            results.append(record)
            (raw_dir / f"{index:02d}-{slug}.json").write_text(
                json.dumps(redact_value(record), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        await cdp.send("Page.navigate", {"url": "about:blank"}, session_id=session_id)
    (out_dir / "capture-summary.json").write_text(
        json.dumps(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "results": redact_value(results),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return results


def load_results_json(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("results"), list):
        raw = raw["results"]
    if not isinstance(raw, list):
        raise SystemExit("--results-json must contain a list or an object with a results list")
    return [item for item in raw if isinstance(item, dict)]


def safe_config(args: argparse.Namespace, *, source: str) -> dict[str, Any]:
    return {
        "max_height": args.max_height,
        "source": source,
        "strict_nonblank": bool(args.strict_nonblank),
        "viewport_height": args.viewport_height,
        "viewport_width": args.viewport_width,
    }


def strict_nonblank_error(manifest: dict[str, Any]) -> str | None:
    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    attempted = int(counts.get("attempted", 0) or 0)
    nonblank = int(counts.get("nonblank", 0) or 0)
    if nonblank < attempted:
        return f"--strict-nonblank expected {attempted} nonblank screenshots, got {nonblank}"
    return None


def main() -> int:
    args = parse_args()
    if args.results_json is not None:
        results = load_results_json(args.results_json)
        source = "results_json"
    else:
        results = asyncio.run(capture_detector_results(args))
        source = "session_json"
    manifest = build_manifest(args.out_dir, results, config=safe_config(args, source=source))
    out = args.manifest or args.out_dir / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": relative_or_name(out, args.out_dir), "counts": manifest["counts"]}, indent=2, sort_keys=True))
    if args.strict_nonblank:
        error = strict_nonblank_error(manifest)
        if error is not None:
            raise SystemExit(error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
