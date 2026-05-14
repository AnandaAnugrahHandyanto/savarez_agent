#!/usr/bin/env python3
"""Audit an HBR stealth/fingerprint-hygiene profile against public detectors.

Evidence collection only: this does not bypass CAPTCHA/auth/payment/rate limits and
must not be presented as universal anti-bot stealth.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import websockets

TESTS = [
    {"slug": "browserleaks-ip", "title": "BrowserLeaks IP", "url": "https://browserleaks.com/ip", "wait": 12},
    {"slug": "browserleaks-dns", "title": "BrowserLeaks DNS", "url": "https://browserleaks.com/dns", "wait": 18},
    {"slug": "browserleaks-webrtc", "title": "BrowserLeaks WebRTC", "url": "https://browserleaks.com/webrtc", "wait": 14},
    {"slug": "browserleaks-canvas", "title": "BrowserLeaks Canvas", "url": "https://browserleaks.com/canvas", "wait": 10},
    {"slug": "browserleaks-webgl", "title": "BrowserLeaks WebGL", "url": "https://browserleaks.com/webgl", "wait": 12},
    {"slug": "browserleaks-fonts", "title": "BrowserLeaks Fonts", "url": "https://browserleaks.com/fonts", "wait": 12},
    {"slug": "browserleaks-javascript", "title": "BrowserLeaks JavaScript", "url": "https://browserleaks.com/javascript", "wait": 12},
    {"slug": "browserleaks-tls", "title": "BrowserLeaks TLS", "url": "https://browserleaks.com/tls", "wait": 12},
    {"slug": "creepjs", "title": "CreepJS", "url": "https://abrahamjuliot.github.io/creepjs/", "wait": 36},
    {"slug": "sannysoft", "title": "bot.sannysoft.com", "url": "https://bot.sannysoft.com/", "wait": 18},
    {"slug": "pixelscan-fingerprint", "title": "Pixelscan fingerprint check", "url": "https://pixelscan.net/fingerprint-check", "wait": 28},
    {"slug": "pixelscan-bot", "title": "Pixelscan bot check", "url": "https://pixelscan.net/bot-check", "wait": 28},
]

SENSITIVE_URL_RE = re.compile(r"wss?://127\.0\.0\.1:[0-9]+/devtools/[^\s\"'<>]+", re.I)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\b")
LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{20,}\b")


def redact_text_for_chat(text: str, limit: int | None = None) -> str:
    text = SENSITIVE_URL_RE.sub("[REDACTED_CDP_WS]", text)
    text = IPV4_RE.sub("[REDACTED_IPV4]", text)
    text = IPV6_RE.sub("[REDACTED_IPV6]", text)
    text = LONG_HEX_RE.sub("[REDACTED_HEX]", text)
    if limit is not None:
        return text[:limit]
    return text


class CDP:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self.next_id = 0
        self.pending: dict[int, asyncio.Future] = {}
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.reader_task: asyncio.Task | None = None

    async def __aenter__(self):
        self.ws = await websockets.connect(self.ws_url, max_size=96 * 1024 * 1024)
        self.reader_task = asyncio.create_task(self._reader())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()

    async def _reader(self):
        assert self.ws is not None
        async for message in self.ws:
            data = json.loads(message)
            if "id" in data and data["id"] in self.pending:
                fut = self.pending.pop(data["id"])
                if "error" in data:
                    fut.set_exception(RuntimeError(json.dumps(data["error"], ensure_ascii=False)))
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


async def attach_page(cdp: CDP) -> tuple[str, str]:
    targets = (await cdp.send("Target.getTargets")).get("targetInfos", [])
    pages = [t for t in targets if t.get("type") == "page"]
    target_id = pages[0]["targetId"] if pages else (await cdp.send("Target.createTarget", {"url": "about:blank"}))["targetId"]
    attached = await cdp.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
    return target_id, attached["sessionId"]


async def eval_js(cdp: CDP, session_id: str, expression: str, *, timeout_ms: int = 60000) -> Any:
    result = await cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "awaitPromise": True, "returnByValue": True, "timeout": timeout_ms},
        session_id=session_id,
    )
    if "exceptionDetails" in result:
        raise RuntimeError(json.dumps(result["exceptionDetails"], ensure_ascii=False)[:2000])
    return result.get("result", {}).get("value")


async def navigate_and_wait(cdp: CDP, session_id: str, url: str, wait_secs: int) -> dict[str, Any]:
    await cdp.send("Page.navigate", {"url": url}, session_id=session_id)
    deadline = time.monotonic() + wait_secs
    last_state = "unknown"
    while time.monotonic() < deadline:
        try:
            last_state = await eval_js(cdp, session_id, "document.readyState", timeout_ms=5000)
        except Exception:
            pass
        await asyncio.sleep(1)
    title = ""
    text = ""
    url_now = ""
    try:
        title = await eval_js(cdp, session_id, "document.title", timeout_ms=5000) or ""
    except Exception:
        pass
    try:
        url_now = await eval_js(cdp, session_id, "location.href", timeout_ms=5000) or ""
    except Exception:
        pass
    try:
        text = await eval_js(cdp, session_id, "document.body ? document.body.innerText : ''", timeout_ms=10000) or ""
    except Exception as exc:
        text = f"[TEXT_EXTRACTION_ERROR] {exc}"
    return {"readyState": last_state, "title": title, "url_after": url_now, "body_text": text}


async def capture_screenshot(cdp: CDP, session_id: str, out_path: Path, *, max_height: int) -> dict[str, Any]:
    metrics = await cdp.send("Page.getLayoutMetrics", session_id=session_id)
    content = metrics.get("contentSize") or {}
    width = max(800, min(int(content.get("width") or 1440), 2400))
    height = max(800, int(content.get("height") or 1000))
    capture_height = min(height, max_height)
    await cdp.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": min(capture_height, max_height), "deviceScaleFactor": 1, "mobile": False},
        session_id=session_id,
    )
    await asyncio.sleep(0.3)
    result = await cdp.send(
        "Page.captureScreenshot",
        {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": width, "height": capture_height, "scale": 1},
        },
        session_id=session_id,
    )
    png = base64.b64decode(result["data"])
    out_path.write_bytes(png)
    return {
        "path": str(out_path),
        "width": width,
        "content_height": height,
        "captured_height": capture_height,
        "full_page_captured": capture_height >= height,
        "size_bytes": len(png),
    }


TABLE_EXTRACT_JS = r"""
(() => {
  const rows = [];
  for (const tr of Array.from(document.querySelectorAll('tr'))) {
    const cells = Array.from(tr.querySelectorAll('th,td')).map(c => c.innerText.trim().replace(/\s+/g, ' ')).filter(Boolean);
    if (cells.length) rows.push(cells);
  }
  const kv = [];
  for (const row of rows) {
    if (row.length >= 2) kv.push({key: row[0], value: row.slice(1).join(' | ')});
  }
  return {rows, kv};
})()
"""

DIRECT_PROBE_JS = r"""
(async () => {
  const hashString = async (s) => {
    try {
      const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
      return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
    } catch (_) {
      let h = 0; for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0; return String(h);
    }
  };
  const getWebgl = () => {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
    if (!gl) return {available: false};
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    const p = (x) => { try { return gl.getParameter(x); } catch(e) { return null; } };
    return {
      available: true,
      vendor: dbg ? p(dbg.UNMASKED_VENDOR_WEBGL) : null,
      renderer: dbg ? p(dbg.UNMASKED_RENDERER_WEBGL) : null,
      version: p(gl.VERSION),
      shadingLanguageVersion: p(gl.SHADING_LANGUAGE_VERSION),
      maxTextureSize: p(gl.MAX_TEXTURE_SIZE),
      maxViewportDims: p(gl.MAX_VIEWPORT_DIMS),
    };
  };
  const getCanvas = async () => {
    const c = document.createElement('canvas'); c.width = 240; c.height = 80;
    const ctx = c.getContext('2d');
    ctx.textBaseline = 'top'; ctx.font = '16px Arial';
    ctx.fillStyle = '#f60'; ctx.fillRect(0, 0, 240, 80);
    ctx.fillStyle = '#069'; ctx.fillText('HBR canvas audit 🔒 Ω', 4, 8);
    ctx.strokeStyle = 'rgba(120,80,200,.75)'; ctx.beginPath(); ctx.arc(60, 50, 18, 0, Math.PI * 2); ctx.stroke();
    return {sha256: await hashString(c.toDataURL())};
  };
  const getAudio = async () => {
    try {
      const AC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      if (!AC) return {available: false};
      const ctx = new AC(1, 5000, 44100);
      const osc = ctx.createOscillator(); osc.type = 'triangle'; osc.frequency.value = 10000;
      const comp = ctx.createDynamicsCompressor();
      osc.connect(comp); comp.connect(ctx.destination); osc.start(0);
      const buf = await ctx.startRendering();
      const data = Array.from(buf.getChannelData(0).slice(0, 512)).map(x => x.toFixed(8)).join(',');
      return {available: true, sha256: await hashString(data)};
    } catch (e) { return {available: false, error: e && e.name || String(e)}; }
  };
  const permissionNames = ['geolocation','notifications','camera','microphone','clipboard-read'];
  const permissions = {};
  for (const name of permissionNames) {
    try { permissions[name] = (await navigator.permissions.query({name})).state; }
    catch (e) { permissions[name] = 'error:' + (e && e.name || 'unknown'); }
  }
  const webdriverDescriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(navigator), 'webdriver');
  const ownWebdriverDescriptor = Object.getOwnPropertyDescriptor(navigator, 'webdriver');
  const uaData = navigator.userAgentData ? await navigator.userAgentData.getHighEntropyValues(['brands','fullVersionList','platform','platformVersion','architecture','bitness','mobile','formFactors']) : null;
  const webrtc = await new Promise((resolve) => {
    if (!window.RTCPeerConnection) return resolve({available: false, candidates: []});
    const pc = new RTCPeerConnection({iceServers: [{urls: 'stun:stun.l.google.com:19302'}]});
    const candidates = [];
    const done = () => { try { pc.close(); } catch(_){} resolve({available: true, candidates}); };
    pc.onicecandidate = e => { if (e.candidate && e.candidate.candidate) candidates.push(e.candidate.candidate); };
    try {
      pc.createDataChannel('audit');
      pc.createOffer().then(o => pc.setLocalDescription(o));
    } catch (e) { candidates.push('ERROR:' + (e && e.name || 'unknown')); }
    setTimeout(done, 4000);
  });
  return {
    location: location.href,
    userAgent: navigator.userAgent,
    appVersion: navigator.appVersion,
    platform: navigator.platform,
    vendor: navigator.vendor,
    productSub: navigator.productSub,
    language: navigator.language,
    languages: Array.from(navigator.languages || []),
    webdriver: {
      value: navigator.webdriver,
      type: typeof navigator.webdriver,
      inNavigator: 'webdriver' in navigator,
      ownDescriptor: ownWebdriverDescriptor ? {enumerable: ownWebdriverDescriptor.enumerable, configurable: ownWebdriverDescriptor.configurable, hasGetter: !!ownWebdriverDescriptor.get, valueType: typeof ownWebdriverDescriptor.value} : null,
      protoDescriptor: webdriverDescriptor ? {enumerable: webdriverDescriptor.enumerable, configurable: webdriverDescriptor.configurable, hasGetter: !!webdriverDescriptor.get, valueType: typeof webdriverDescriptor.value} : null,
    },
    uaData,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    timezoneOffset: new Date().getTimezoneOffset(),
    screen: {width: screen.width, height: screen.height, availWidth: screen.availWidth, availHeight: screen.availHeight, colorDepth: screen.colorDepth, pixelDepth: screen.pixelDepth, devicePixelRatio: devicePixelRatio, innerWidth, innerHeight, outerWidth, outerHeight},
    hardware: {hardwareConcurrency: navigator.hardwareConcurrency, deviceMemory: navigator.deviceMemory, maxTouchPoints: navigator.maxTouchPoints, pdfViewerEnabled: navigator.pdfViewerEnabled},
    plugins: Array.from(navigator.plugins || []).map(p => ({name: p.name, filename: p.filename, description: p.description, length: p.length})),
    mimeTypes: Array.from(navigator.mimeTypes || []).map(m => ({type: m.type, suffixes: m.suffixes, description: m.description, enabledPlugin: m.enabledPlugin && m.enabledPlugin.name})),
    permissions,
    rendering: {webgl: getWebgl(), canvas: await getCanvas(), audio: await getAudio(), webgpuAvailable: !!navigator.gpu},
    webrtc,
  };
})()
"""


def classify_webrtc(candidates: list[str]) -> dict[str, Any]:
    classes = []
    private = []
    public_lit = []
    mdns = []
    for c in candidates:
        if ".local" in c:
            mdns.append(c)
            classes.append("mdns_host")
        for ip in IPV4_RE.findall(c):
            parts = [int(x) for x in ip.split('.')]
            is_private = parts[0] == 10 or (parts[0] == 172 and 16 <= parts[1] <= 31) or (parts[0] == 192 and parts[1] == 168) or parts[0] == 127 or (parts[0] == 169 and parts[1] == 254)
            if is_private:
                private.append(ip)
                classes.append("private_literal")
            else:
                public_lit.append(ip)
                classes.append("public_literal")
        if " typ srflx" in c:
            classes.append("srflx")
        if " typ relay" in c:
            classes.append("relay")
        if " typ host" in c:
            classes.append("host")
    return {
        "candidate_count": len(candidates),
        "classes": sorted(set(classes)) or ["none"],
        "private_literal_count": len(private),
        "public_literal_count": len(public_lit),
        "mdns_host_count": len(mdns),
    }


def summarize_detector(slug: str, text: str, tables: dict[str, Any]) -> dict[str, Any]:
    lower = text.lower()
    summary: dict[str, Any] = {"signals": {}}
    if slug == "sannysoft":
        kv = {str(x.get("key", "")).strip().lower(): str(x.get("value", "")).strip() for x in tables.get("kv", []) if isinstance(x, dict)}
        summary["sannysoft_kv"] = kv
        for key in ["webdriver (new)", "webdriver advanced", "user agent (old)", "chrome (new)", "permissions (new)", "plugins length (old)", "plugins is of type pluginnarray", "languages"]:
            for k, v in kv.items():
                if key in k:
                    summary["signals"][k] = v
    elif slug == "creepjs":
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        interesting = [ln for ln in lines if re.search(r"headless|stealth|lies|trust|bot|webgl|canvas|audio|worker|webdriver|fingerprint", ln, re.I)]
        summary["interesting_lines"] = interesting[:80]
    elif slug.startswith("pixelscan"):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        interesting = [ln for ln in lines if re.search(r"bot|fingerprint|proxy|vpn|check|risk|trust|passed|failed|inconsistent|consistent", ln, re.I)]
        summary["interesting_lines"] = interesting[:80]
    else:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        interesting = [ln for ln in lines if re.search(r"webdriver|headless|webrtc|local|public|timezone|language|webgl|renderer|vendor|canvas|audio|font|tls|ja3|http2", ln, re.I)]
        summary["interesting_lines"] = interesting[:80]
    return summary


async def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    (out_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    (out_dir / "text").mkdir(parents=True, exist_ok=True)
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)
    session = json.loads(Path(args.session_json).read_text())
    ws_url = session["cdp_ws_url"]
    results = []
    async with CDP(ws_url) as cdp:
        _target_id, sid = await attach_page(cdp)
        await cdp.send("Page.enable", session_id=sid)
        await cdp.send("Runtime.enable", session_id=sid)
        await cdp.send("Network.enable", session_id=sid)
        await cdp.send("Page.bringToFront", session_id=sid)

        # Run deterministic JS probe on a fresh document before public detectors alter state.
        data_url = "data:text/html," + quote("<!doctype html><title>HBR stealth audit direct probe</title><body>probe</body>")
        await navigate_and_wait(cdp, sid, data_url, 3)
        direct_probe = await eval_js(cdp, sid, DIRECT_PROBE_JS, timeout_ms=90000)
        direct_probe["webrtc_classification"] = classify_webrtc((direct_probe.get("webrtc") or {}).get("candidates") or [])
        (out_dir / "reports" / "direct-js-probe.json").write_text(json.dumps(direct_probe, ensure_ascii=False, indent=2), encoding="utf-8")

        for idx, test in enumerate(TESTS, start=1):
            slug = test["slug"]
            print(f"[{idx:02d}/{len(TESTS)}] {slug} {test['url']}", flush=True)
            record: dict[str, Any] = {"slug": slug, "title": test["title"], "url": test["url"], "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            try:
                page = await navigate_and_wait(cdp, sid, test["url"], int(test["wait"]))
                png_path = out_dir / "screenshots" / f"{idx:02d}-{slug}.png"
                shot = await capture_screenshot(cdp, sid, png_path, max_height=args.max_height)
                text_path = out_dir / "text" / f"{idx:02d}-{slug}.txt"
                text_path.write_text(page.get("body_text") or "", encoding="utf-8")
                tables = await eval_js(cdp, sid, TABLE_EXTRACT_JS, timeout_ms=15000)
                report = {
                    "slug": slug,
                    "title": test["title"],
                    "url": test["url"],
                    "page_title": page.get("title"),
                    "url_after": page.get("url_after"),
                    "readyState": page.get("readyState"),
                    "text_path": str(text_path),
                    "screenshot": shot,
                    "tables": tables,
                    "detector_summary": summarize_detector(slug, page.get("body_text") or "", tables or {}),
                    "redacted_text_sample": redact_text_for_chat(page.get("body_text") or "", 3000),
                }
                (out_dir / "reports" / f"{idx:02d}-{slug}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                record.update({"ok": True, "page_title": page.get("title"), "url_after": page.get("url_after"), "text_path": str(text_path), "report_path": str(out_dir / "reports" / f"{idx:02d}-{slug}.json"), "screenshot": shot})
            except Exception as exc:
                record.update({"ok": False, "error": redact_text_for_chat(str(exc), 2000)})
                try:
                    png_path = out_dir / "screenshots" / f"{idx:02d}-{slug}-error.png"
                    record["screenshot"] = await capture_screenshot(cdp, sid, png_path, max_height=args.max_height)
                except Exception as exc2:
                    record["screenshot_error"] = redact_text_for_chat(str(exc2), 1000)
            results.append(record)
        await cdp.send("Page.navigate", {"url": "about:blank"}, session_id=sid)

    summary = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "session": {k: ("[REDACTED]" if "url" in k else v) for k, v in session.items()}, "direct_probe_path": str(out_dir / "reports" / "direct-js-probe.json"), "results": results}
    (out_dir / "capture-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-height", type=int, default=20000)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
