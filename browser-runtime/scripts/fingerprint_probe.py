#!/usr/bin/env python3
"""Deterministic sanitized fingerprint probe for hermes-browser-runtime.

The script treats live CDP and takeover URLs as capability secrets. It may read a
session-create JSON containing `cdp_ws_url`, but the output is a shareable,
sanitized summary only: no usable CDP URL, takeover token, cookies/auth markers,
raw IPs/hostnames, private profile paths, or raw fingerprint dumps.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import ipaddress
import json
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "hbr.p4.fingerprint_probe.v1"
MEASUREMENT_CONTRACT_VERSION = "hbr.p5.direct_probe.v1"
CONTEXT_NAMES = ("top", "iframe", "worker", "popup")
CANDIDATE_CLASS_ORDER = ["mdns_host", "private_literal", "public_host", "public_srflx", "relay", "none", "unknown"]

CDP_WS_RE = re.compile(r"wss?://[^\s\"'<>]+/devtools/browser/[^\s\"'<>]+", re.IGNORECASE)
TAKEOVER_TOKEN_RE = re.compile(r"https?://[^\s\"'<>]+/takeover/[^?\s\"'<>]+\?[^\s\"'<>]*token=[^&\s\"'<>]+", re.IGNORECASE)
HOSTNAME_RE = re.compile(r"\b[a-zA-Z0-9][a-zA-Z0-9-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9-]*)+\b")
AUTH_MARKER_RE = re.compile(r"(?i)\b(authorization|cookie|set-cookie|password|passwd|token|secret|form[_-]?body|request[_-]?body)\b")
CHROME_VERSION_RE = re.compile(r"\b(\d{2,3}(?:\.\d+){1,3})\b")
CHROME_TOKEN_RE = re.compile(r"(?:Chrome|Chromium)/(\d+(?:\.\d+)+)")

INDEX_HTML = """<!doctype html>
<html><head><meta charset=\"utf-8\"><title>HBR P4 local probe</title></head>
<body><iframe id=\"frame\" src=\"/frame\"></iframe></body></html>"""

FRAME_HTML = "<!doctype html><html><body>frame probe</body></html>"

WORKER_JS = """
self.onmessage = async () => {
  const uaData = navigator.userAgentData
    ? await navigator.userAgentData.getHighEntropyValues(['brands', 'fullVersionList', 'platform', 'platformVersion', 'architecture', 'bitness', 'mobile', 'formFactors'])
    : null;
  self.postMessage({
    language: navigator.language,
    languages: Array.from(navigator.languages || []),
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    uaData,
    hardware: {
      hardwareConcurrency: navigator.hardwareConcurrency,
      deviceMemory: navigator.deviceMemory,
      maxTouchPoints: navigator.maxTouchPoints,
    },
    automation: {
      webdriverType: typeof navigator.webdriver,
      webdriverInNavigator: 'webdriver' in navigator,
      ownHasWebdriver: Object.prototype.hasOwnProperty.call(navigator, 'webdriver'),
      protoHasWebdriver: !!Object.getOwnPropertyDescriptor(Object.getPrototypeOf(navigator), 'webdriver'),
    },
  });
};
"""

PROBE_EXPRESSION = r"""
(async () => {
  const automationProbe = (win) => {
    const nav = win.navigator;
    const proto = win.Object.getPrototypeOf(nav);
    const protoDescriptor = win.Object.getOwnPropertyDescriptor(proto, 'webdriver');
    const ownDescriptor = win.Object.getOwnPropertyDescriptor(nav, 'webdriver');
    return {
      webdriverType: typeof nav.webdriver,
      webdriverInNavigator: 'webdriver' in nav,
      ownHasWebdriver: !!ownDescriptor,
      protoHasWebdriver: !!protoDescriptor,
    };
  };
  const getUaData = async (nav) => nav.userAgentData
    ? await nav.userAgentData.getHighEntropyValues(['brands', 'fullVersionList', 'platform', 'platformVersion', 'architecture', 'bitness', 'mobile', 'formFactors'])
    : null;
  const screenProbe = (win) => ({
    width: win.screen.width,
    height: win.screen.height,
    availWidth: win.screen.availWidth,
    availHeight: win.screen.availHeight,
  });
  const viewportProbe = (win) => ({ innerWidth: win.innerWidth, innerHeight: win.innerHeight });
  const hardwareProbe = (nav) => ({
    hardwareConcurrency: nav.hardwareConcurrency,
    deviceMemory: nav.deviceMemory,
    maxTouchPoints: nav.maxTouchPoints,
  });
  const visualViewportProbe = (win) => win.visualViewport ? {
    width: win.visualViewport.width,
    height: win.visualViewport.height,
    scale: win.visualViewport.scale,
  } : null;
  const matchMediaProbe = (win) => {
    const screenWidth = win.screen.width;
    const screenHeight = win.screen.height;
    return {
      screenExact: win.matchMedia(`(width: ${screenWidth}px) and (height: ${screenHeight}px)`).matches,
      minWidth: win.matchMedia(`(min-width: ${screenWidth}px)`).matches,
      maxWidth: win.matchMedia(`(max-width: ${screenWidth}px)`).matches,
      pointerFine: win.matchMedia('(pointer: fine)').matches,
      hoverHover: win.matchMedia('(hover: hover)').matches,
    };
  };
  const probe = async (win) => ({
    language: win.navigator.language,
    languages: Array.from(win.navigator.languages || []),
    userAgent: win.navigator.userAgent,
    platform: win.navigator.platform,
    timezone: win.Intl.DateTimeFormat().resolvedOptions().timeZone,
    uaData: await getUaData(win.navigator),
    viewport: viewportProbe(win),
    screen: screenProbe(win),
    window: { outerWidth: win.outerWidth, outerHeight: win.outerHeight },
    visualViewport: visualViewportProbe(win),
    matchMedia: matchMediaProbe(win),
    hardware: hardwareProbe(win.navigator),
    devicePixelRatio: win.devicePixelRatio,
    automation: automationProbe(win),
  });
  const webglProbe = () => {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!gl) return { available: false };
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    return {
      available: true,
      vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : 'unavailable',
      renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'unavailable',
    };
  };
  const webgpuProbe = () => ({ available: !!navigator.gpu });
  const webrtcProbe = async () => {
    if (!window.RTCPeerConnection) return { candidates: [], status: 'unavailable' };
    const pc = new RTCPeerConnection({ iceServers: [] });
    const candidates = [];
    pc.onicecandidate = (event) => {
      if (event.candidate && event.candidate.candidate) candidates.push(event.candidate.candidate);
    };
    try {
      pc.createDataChannel('hbr-probe');
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await new Promise((resolve) => setTimeout(resolve, 1500));
      return { candidates, status: 'ok' };
    } catch (error) {
      return { candidates, status: 'error', errorName: error && error.name ? error.name : 'unknown' };
    } finally {
      pc.close();
    }
  };

  const deadline = Date.now() + 5000;
  let iframe = document.getElementById('frame');
  while (!iframe && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    iframe = document.getElementById('frame');
  }
  if (!iframe) { throw new Error('iframe probe element missing after navigation'); }
  if (!iframe.contentWindow || iframe.contentDocument.readyState !== 'complete') {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('iframe probe load timeout')), 5000);
      iframe.addEventListener('load', () => { clearTimeout(timer); resolve(); }, { once: true });
    });
  }
  const contextAvailability = {
    top: {status: 'measured'},
    iframe: {status: 'measured'},
    worker: {status: 'measured'},
    popup: {
      status: 'unavailable',
      reason: 'not_attempted',
      open_method: 'window.open_about_blank',
      cdp_runtime_evaluate_user_gesture: true,
    },
  };
  let popupResult = null;
  let popup = null;
  try {
    popup = window.open('about:blank', '_blank', 'width=320,height=240');
    if (popup) {
      popup.document.open();
      popup.document.write('<!doctype html><html><body>popup probe</body></html>');
      popup.document.close();
      await new Promise((resolve) => setTimeout(resolve, 250));
      popupResult = await probe(popup);
      contextAvailability.popup = {
        status: 'measured',
        open_method: 'window.open_about_blank',
        cdp_runtime_evaluate_user_gesture: true,
      };
    } else {
      contextAvailability.popup = {
        status: 'unavailable',
        reason: 'window_open_returned_null',
        open_method: 'window.open_about_blank',
        cdp_runtime_evaluate_user_gesture: true,
      };
    }
  } catch (error) {
    contextAvailability.popup = {
      status: 'unavailable',
      reason: 'popup_probe_exception',
      error_name: error && error.name ? String(error.name) : 'unknown',
      open_method: 'window.open_about_blank',
      cdp_runtime_evaluate_user_gesture: true,
    };
    popupResult = null;
  } finally {
    try {
      if (popup && !popup.closed) popup.close();
    } catch (_) {}
  }
  const worker = new Worker('/worker.js');
  const workerResult = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('worker probe timeout')), 5000);
    worker.onmessage = (event) => { clearTimeout(timer); resolve(event.data); };
    worker.onerror = (event) => { clearTimeout(timer); reject(new Error(event.message || 'worker probe failed')); };
    worker.postMessage('probe');
  });
  worker.terminate();
  const uaData = navigator.userAgentData
    ? await navigator.userAgentData.getHighEntropyValues(['brands', 'fullVersionList', 'platform', 'platformVersion', 'architecture', 'bitness', 'mobile', 'formFactors'])
    : null;
  return {
    contexts: { top: await probe(window), iframe: iframe ? await probe(iframe.contentWindow) : null, popup: popupResult, worker: workerResult },
    context_availability: contextAvailability,
    uaData,
    webrtc: await webrtcProbe(),
    rendering: { webgl: webglProbe(), webgpu: webgpuProbe() },
  };
})()
"""


class ProbeHttpServer:
    def __init__(self) -> None:
        self.headers_seen: dict[str, str] = {}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url = ""

    def start(self) -> None:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:  # noqa: A002 - stdlib signature
                return

            def do_GET(self) -> None:  # noqa: N802 - stdlib signature
                realm = {
                    "/": "top_request",
                    "/frame": "frame_request",
                    "/worker.js": "worker_script",
                }.get(self.path.split("?", 1)[0], "other_request")
                outer.headers_seen[realm] = self.headers.get("accept-language", "")
                path = self.path.split("?", 1)[0]
                if path == "/":
                    self._send("text/html; charset=utf-8", INDEX_HTML)
                elif path == "/frame":
                    self._send("text/html; charset=utf-8", FRAME_HTML)
                elif path == "/worker.js":
                    self._send("application/javascript; charset=utf-8", WORKER_JS)
                else:
                    self.send_response(404)
                    self.end_headers()

            def _send(self, content_type: str, body: str) -> None:
                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", content_type)
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        host, port = self._server.server_address[:2]
        self.base_url = f"http://{host}:{port}/"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    def __enter__(self) -> "ProbeHttpServer":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()


class CdpClient:
    def __init__(self, websocket: Any) -> None:
        self.websocket = websocket
        self._next_id = 1

    async def send(self, method: str, params: dict[str, Any] | None = None, session_id: str | None = None) -> dict[str, Any]:
        message: dict[str, Any] = {"id": self._next_id, "method": method}
        if params is not None:
            message["params"] = params
        if session_id is not None:
            message["sessionId"] = session_id
        current_id = self._next_id
        self._next_id += 1
        await self.websocket.send(json.dumps(message))
        while True:
            incoming = json.loads(await self.websocket.recv())
            if incoming.get("id") != current_id:
                continue
            if "error" in incoming:
                raise RuntimeError(f"CDP {method} failed: {incoming['error']}")
            return incoming.get("result", {})


async def wait_for_page_ready(
    client: CdpClient,
    session_id: str,
    timeout_seconds: float = 5.0,
    expected_title: str = "HBR P4 local probe",
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        result = await client.send(
            "Runtime.evaluate",
            {
                "expression": "({ readyState: document.readyState, title: document.title })",
                "returnByValue": True,
            },
            session_id=session_id,
        )
        value = result.get("result", {}).get("value") or {}
        state = value.get("readyState") if isinstance(value, dict) else None
        title = value.get("title") if isinstance(value, dict) else None
        if state == "complete" and title == expected_title:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("timed out waiting for local probe page to load")
        await asyncio.sleep(0.1)


async def collect_live_probe(session: dict[str, Any]) -> dict[str, Any]:
    ws_url = session.get("cdp_ws_url") or session.get("browser_ws_url")
    if not ws_url:
        raise SystemExit("session JSON must include cdp_ws_url or browser_ws_url for live probe mode")
    try:
        import websockets  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on host deps
        raise SystemExit("live probe mode requires the Python 'websockets' package") from exc

    async with websockets.connect(ws_url, open_timeout=10, close_timeout=2) as websocket:
        client = CdpClient(websocket)
        version = await client.send("Browser.getVersion")
        with ProbeHttpServer() as probe_server:
            target = await client.send("Target.createTarget", {"url": "about:blank"})
            target_id = target["targetId"]
            attached = await client.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
            session_id = attached["sessionId"]
            try:
                await client.send("Page.enable", session_id=session_id)
                await client.send("Runtime.enable", session_id=session_id)
                await client.send("Page.navigate", {"url": probe_server.base_url}, session_id=session_id)
                await wait_for_page_ready(client, session_id)
                evaluated = await client.send(
                    "Runtime.evaluate",
                    {"expression": PROBE_EXPRESSION, "awaitPromise": True, "returnByValue": True, "userGesture": True},
                    session_id=session_id,
                )
                if "exceptionDetails" in evaluated:
                    raise RuntimeError(f"probe expression failed: {evaluated['exceptionDetails']}")
                value = evaluated.get("result", {}).get("value") or {}
                return {
                    "browser": version,
                    "contexts": value.get("contexts", {}),
                    "context_availability": value.get("context_availability", {}),
                    "uaData": value.get("uaData"),
                    "headers": dict(probe_server.headers_seen),
                    "webrtc": value.get("webrtc", {}),
                    "rendering": value.get("rendering", {}),
                }
            finally:
                with contextlib.suppress(Exception):
                    await client.send("Target.closeTarget", {"targetId": target_id})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-json", type=Path, required=True, help="session create JSON with runtime policy/persona and live cdp_ws_url")
    parser.add_argument("--out", type=Path, required=True, help="write sanitized fingerprint probe JSON here")
    parser.add_argument("--mode", default="local-deterministic", choices=["local-deterministic"], help="probe mode")
    parser.add_argument("--fixture-json", type=Path, help="offline raw probe fixture for deterministic script tests")
    parser.add_argument("--strict", action="store_true", help="fail if sanitized output still contains capability/private markers")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def chrome_full_version(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token_match = CHROME_TOKEN_RE.search(value)
    if token_match:
        return token_match.group(1)
    match = CHROME_VERSION_RE.search(value)
    if not match:
        return None
    return match.group(1)


def chrome_major(value: Any) -> str | None:
    full = chrome_full_version(value)
    if not full:
        return None
    return full.split(".", 1)[0]


def ua_data_major(ua_data: Any) -> str | None:
    if not isinstance(ua_data, dict):
        return None
    for key in ("fullVersionList", "brands"):
        values = ua_data.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            brand = str(item.get("brand", ""))
            version = str(item.get("version", ""))
            if "Chrome" in brand or "Chromium" in brand:
                return version.split(".", 1)[0]
    return None


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def normalize_context_availability(availability: Any, *, measured: bool) -> dict[str, Any]:
    if measured:
        normalized: dict[str, Any] = {"status": "measured"}
        if isinstance(availability, dict):
            for key in ("open_method", "cdp_runtime_evaluate_user_gesture"):
                if key in availability:
                    normalized[key] = availability[key]
        return normalized

    if isinstance(availability, dict):
        reason = availability.get("reason") or "not_measured"
        normalized = {
            "status": str(availability.get("status") or "unavailable"),
            "reason": str(reason),
        }
        for key in ("open_method", "cdp_runtime_evaluate_user_gesture", "error_name"):
            if key in availability:
                normalized[key] = availability[key]
        return normalized

    return {
        "status": "legacy_unknown",
        "reason": "context_absent_without_availability_metadata_not_p5_signoff",
    }


def summarize_context(context: Any, availability: Any = None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {"measured": False, "availability": normalize_context_availability(availability, measured=False)}
    ua = context.get("userAgent")
    ua_data = context.get("uaData")
    summary: dict[str, Any] = {
        "measured": True,
        "availability": normalize_context_availability(availability, measured=True),
        "language": context.get("language"),
        "languages": context.get("languages") if isinstance(context.get("languages"), list) else [],
        "platform": context.get("platform"),
        "timezone": context.get("timezone"),
        "ua_major": chrome_major(ua),
        "ua_ch_major": ua_data_major(ua_data),
        "viewport": context.get("viewport"),
        "screen": context.get("screen"),
        "device_pixel_ratio": context.get("devicePixelRatio"),
    }
    hardware = context.get("hardware") if isinstance(context.get("hardware"), dict) else None
    if hardware is not None:
        summary["hardware"] = {
            "hardware_concurrency": hardware.get("hardwareConcurrency"),
            "device_memory_gb": hardware.get("deviceMemory"),
            "max_touch_points": hardware.get("maxTouchPoints"),
        }
    window = context.get("window") if isinstance(context.get("window"), dict) else None
    if window is not None:
        summary["window"] = {"outer_width": window.get("outerWidth"), "outer_height": window.get("outerHeight")}
    visual_viewport = context.get("visualViewport") if isinstance(context.get("visualViewport"), dict) else None
    if visual_viewport is not None:
        summary["visual_viewport"] = {
            "width": visual_viewport.get("width"),
            "height": visual_viewport.get("height"),
            "scale": visual_viewport.get("scale"),
        }
    match_media = context.get("matchMedia") if isinstance(context.get("matchMedia"), dict) else None
    if match_media is not None:
        summary["match_media"] = {
            "screen_exact": bool(match_media.get("screenExact")),
            "min_width": bool(match_media.get("minWidth")),
            "max_width": bool(match_media.get("maxWidth")),
            "pointer_fine": bool(match_media.get("pointerFine")),
            "hover_hover": bool(match_media.get("hoverHover")),
        }
    automation = context.get("automation")
    if isinstance(automation, dict):
        summary["automation"] = {
            "webdriver_type": automation.get("webdriverType"),
            "webdriver_in_navigator": bool(automation.get("webdriverInNavigator")),
            "own_has_webdriver": bool(automation.get("ownHasWebdriver")),
            "proto_has_webdriver": bool(automation.get("protoHasWebdriver")),
        }
    else:
        summary["automation"] = {"measured": False}
    return summary


def build_measurement_completeness(contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    context_statuses: dict[str, dict[str, Any]] = {}
    unavailable_contexts: dict[str, dict[str, Any]] = {}
    for name in CONTEXT_NAMES:
        summary = contexts.get(name) if isinstance(contexts.get(name), dict) else {}
        measured = bool(summary.get("measured")) if isinstance(summary, dict) else False
        availability = summary.get("availability") if isinstance(summary, dict) and isinstance(summary.get("availability"), dict) else {}
        status = "measured" if measured else str(availability.get("status") or "legacy_unknown")
        entry: dict[str, Any] = {"measured": measured, "status": status}
        if not measured:
            reason = str(availability.get("reason") or "context_not_measured")
            entry["reason"] = reason
            unavailable_contexts[name] = dict(availability) if availability else {"status": status, "reason": reason}
        context_statuses[name] = entry
    return {
        "complete": not unavailable_contexts,
        "required_contexts": list(CONTEXT_NAMES),
        "contexts": context_statuses,
        "unavailable_contexts": unavailable_contexts,
    }


def context_surface_value(context: dict[str, Any], *path: str) -> Any:
    current: Any = context
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def comparable_surface_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def compare_surface(
    contexts: dict[str, dict[str, Any]],
    label: str,
    touched_surfaces: list[str],
    mismatches: list[str],
    *path: str,
) -> None:
    touched_surfaces.append(label)
    values: dict[str, Any] = {}
    for name in CONTEXT_NAMES:
        context = contexts.get(name)
        if not isinstance(context, dict) or not context.get("measured"):
            continue
        value = context_surface_value(context, *path)
        if value is None:
            continue
        values[name] = value
    if len(values) < 2:
        return
    distinct = {comparable_surface_value(value) for value in values.values()}
    if len(distinct) > 1:
        mismatches.append(f"{label} differs across measured contexts")


def sanitize_short_reason(value: Any) -> str:
    text = str(value or "not_measured")
    text = CDP_WS_RE.sub("[REDACTED_CDP_URL]", text)
    text = TAKEOVER_TOKEN_RE.sub("[REDACTED_TAKEOVER_URL]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]", text)
    text = re.sub(r"\b[a-fA-F0-9]{32,128}\b", "[REDACTED_HASH]", text)
    text = re.sub(r"(?i)\btoken=[^\s&\"'<>]+", "[REDACTED_TOKEN]", text)
    text = re.sub(r"(?i)\bcookie=[^\s&\"'<>]+", "[REDACTED_COOKIE]", text)
    return text[:200]


def normalize_service_worker(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {
            "status": "residual",
            "reason": "service_worker_probe_not_attempted_by_local_probe",
            "raw_values_redacted": True,
        }
    status = str(raw.get("status") or "residual")
    service_worker: dict[str, Any] = {"status": status, "raw_values_redacted": True}
    if raw.get("reason"):
        service_worker["reason"] = sanitize_short_reason(raw.get("reason"))
    return service_worker


def build_surface_coherence(contexts: dict[str, dict[str, Any]], service_worker: dict[str, Any]) -> dict[str, Any]:
    touched_surfaces: list[str] = []
    mismatches: list[str] = []
    for label, path in (
        ("navigator.hardwareConcurrency", ("hardware", "hardware_concurrency")),
        ("navigator.deviceMemory", ("hardware", "device_memory_gb")),
        ("navigator.maxTouchPoints", ("hardware", "max_touch_points")),
        ("window.innerWidth", ("viewport", "innerWidth")),
        ("window.innerHeight", ("viewport", "innerHeight")),
        ("screen.width", ("screen", "width")),
        ("screen.height", ("screen", "height")),
        ("window.outerWidth", ("window", "outer_width")),
        ("window.outerHeight", ("window", "outer_height")),
        ("window.visualViewport", ("visual_viewport",)),
        ("window.matchMedia", ("match_media",)),
    ):
        compare_surface(contexts, label, touched_surfaces, mismatches, *path)
    touched_surfaces.append("serviceWorker.status")
    return {
        "coherent": not mismatches,
        "mismatches": mismatches,
        "touched_surfaces": touched_surfaces,
        "service_worker_status": service_worker.get("status"),
        "raw_values_redacted": True,
    }


def build_identity(raw: dict[str, Any]) -> dict[str, Any]:
    contexts = raw.get("contexts") if isinstance(raw.get("contexts"), dict) else {}
    browser = raw.get("browser") if isinstance(raw.get("browser"), dict) else {}
    ua_majors: list[str] = []
    ua_ch_majors: list[str] = []
    headless_markers: list[str] = []

    for source in (browser.get("userAgent"), browser.get("product")):
        major = chrome_major(source)
        if major:
            ua_majors.append(major)
        if isinstance(source, str) and "HeadlessChrome/" in source:
            headless_markers.append("browser")

    for name in CONTEXT_NAMES:
        context = contexts.get(name)
        if not isinstance(context, dict):
            continue
        ua = context.get("userAgent")
        major = chrome_major(ua)
        if major:
            ua_majors.append(major)
        if isinstance(ua, str) and "HeadlessChrome/" in ua:
            headless_markers.append(name)
        ch_major = ua_data_major(context.get("uaData"))
        if ch_major:
            ua_ch_majors.append(ch_major)

    raw_ua_data_major = ua_data_major(raw.get("uaData"))
    if raw_ua_data_major:
        ua_ch_majors.append(raw_ua_data_major)

    unique_ua = ordered_unique(ua_majors)
    unique_ch = ordered_unique(ua_ch_majors)
    mismatches: list[str] = []
    if len(unique_ua) > 1:
        mismatches.append(f"multiple UA Chrome majors observed: {unique_ua}")
    if len(unique_ch) > 1:
        mismatches.append(f"multiple UA-CH Chrome majors observed: {unique_ch}")
    if unique_ua and unique_ch and unique_ua[0] != unique_ch[0]:
        mismatches.append(f"ua_major {unique_ua[0]} != ua_ch_major {unique_ch[0]}")
    if headless_markers:
        mismatches.append(f"HeadlessChrome marker present in {ordered_unique(headless_markers)}")
    if not unique_ua:
        mismatches.append("ua_major not measured")
    if not unique_ch:
        mismatches.append("ua_ch_major not measured")

    return {
        "ua_major": unique_ua[0] if unique_ua else None,
        "ua_ch_major": unique_ch[0] if unique_ch else None,
        "coherent": not mismatches,
        "mismatches": mismatches,
    }


def classify_ip(value: str) -> str | None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None
    if ip.is_private or ip.is_link_local or ip.is_loopback or getattr(ip, "is_unique_local", False):
        return "private_literal"
    return "public_host"


def classify_candidate(candidate: str) -> str:
    lower = candidate.lower()
    if " typ relay" in lower:
        return "relay"
    if ".local" in lower:
        return "mdns_host"
    tokens = re.split(r"\s+", candidate)
    ip_class = None
    for token in tokens:
        ip_class = classify_ip(token)
        if ip_class:
            break
    if " typ srflx" in lower:
        return "private_literal" if ip_class == "private_literal" else "public_srflx"
    if ip_class:
        return ip_class
    return "unknown"


def classify_webrtc(raw_webrtc: Any) -> dict[str, Any]:
    candidates: list[str] = []
    if isinstance(raw_webrtc, dict):
        value = raw_webrtc.get("candidates", [])
        if isinstance(value, list):
            candidates = [str(item) for item in value if item]
    classes = [classify_candidate(candidate) for candidate in candidates]
    if not classes:
        classes = ["none"]
    ordered = sorted(set(classes), key=lambda item: CANDIDATE_CLASS_ORDER.index(item) if item in CANDIDATE_CLASS_ORDER else 999)
    return {"candidate_classes": ordered, "raw_values_redacted": True}


def classify_rendering(raw_rendering: Any) -> dict[str, Any]:
    rendering = raw_rendering if isinstance(raw_rendering, dict) else {}
    webgl_raw = rendering.get("webgl") if isinstance(rendering.get("webgl"), dict) else {}
    available = bool(webgl_raw.get("available"))
    vendor_renderer = f"{webgl_raw.get('vendor', '')} {webgl_raw.get('renderer', '')}".lower()
    if not available:
        renderer_class = "blocked"
    elif "swiftshader" in vendor_renderer:
        renderer_class = "swiftshader"
    elif any(marker in vendor_renderer for marker in ("llvmpipe", "software", "mesa offscreen")):
        renderer_class = "software"
    elif vendor_renderer.strip():
        renderer_class = "hardware_like"
    else:
        renderer_class = "unknown"
    webgpu_raw = rendering.get("webgpu") if isinstance(rendering.get("webgpu"), dict) else {}
    return {
        "webgl": {
            "available": available,
            "renderer_class": renderer_class,
        },
        "webgpu": {"available": bool(webgpu_raw.get("available"))},
    }


def session_persona(session: dict[str, Any]) -> dict[str, Any]:
    persona = session.get("persona") if isinstance(session.get("persona"), dict) else {}
    viewport = persona.get("viewport") if isinstance(persona.get("viewport"), dict) else {}
    return {
        "locale": persona.get("locale") or session.get("locale"),
        "timezone_id": persona.get("timezone_id") or session.get("timezone_id"),
        "platform": persona.get("platform") or session.get("platform"),
        "viewport": {
            "width": viewport.get("width") or session.get("viewport_width"),
            "height": viewport.get("height") or session.get("viewport_height"),
        },
    }


def build_sanitized_report(
    raw: dict[str, Any],
    session: dict[str, Any],
    *,
    mode: str = "local-deterministic",
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated_at_utc = generated_at_utc or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    browser = raw.get("browser") if isinstance(raw.get("browser"), dict) else {}
    identity = build_identity(raw)
    webrtc = classify_webrtc(raw.get("webrtc"))
    rendering = classify_rendering(raw.get("rendering"))
    red_flags: list[str] = []
    if not identity["coherent"]:
        red_flags.append("identity_incoherent")
    if any("HeadlessChrome" in mismatch for mismatch in identity.get("mismatches", [])):
        red_flags.append("headless_user_agent")
    if rendering["webgl"]["renderer_class"] == "swiftshader":
        red_flags.append("webgl_swiftshader")
    elif rendering["webgl"]["renderer_class"] == "software":
        red_flags.append("webgl_software")
    elif rendering["webgl"]["renderer_class"] == "blocked":
        red_flags.append("webgl_blocked")

    contexts = raw.get("contexts") if isinstance(raw.get("contexts"), dict) else {}
    context_availability = raw.get("context_availability") if isinstance(raw.get("context_availability"), dict) else {}
    context_summaries = {
        name: summarize_context(contexts.get(name), context_availability.get(name)) for name in CONTEXT_NAMES
    }
    measurement_completeness = build_measurement_completeness(context_summaries)
    service_worker = normalize_service_worker(raw.get("service_worker_status"))
    surface_coherence = build_surface_coherence(context_summaries, service_worker)
    if not surface_coherence["coherent"]:
        red_flags.append("surface_incoherent")

    residual_risks = [
        "Public detector pages are evidence only and were not measured by this deterministic local probe.",
        "Network reputation, TLS/JA4, CAPTCHA/challenge behavior, account history, and site access controls are out of scope.",
    ]
    if rendering["webgl"]["renderer_class"] in {"swiftshader", "software", "blocked"}:
        residual_risks.append("Consumer-like GPU/WebGL behavior is not proven in this environment.")
    if "private_literal" in webrtc["candidate_classes"]:
        residual_risks.append("WebRTC private-literal candidate class was observed locally; raw candidate values were redacted.")
    if service_worker.get("status") != "measured":
        residual_risks.append(
            "Service-worker coherence remains residual; status is recorded without raw service-worker state."
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "mode": mode,
        "runtime": {
            "headless": bool(session.get("headless", False)),
            "launch_mode": session.get("launch_mode") or ("headless" if session.get("headless") else "unknown"),
            "chrome_product_major": chrome_major(browser.get("product") or browser.get("userAgent")),
        },
        "policy": {
            "webrtc_ip_policy": session.get("webrtc_ip_policy") or "unknown",
            "gpu_policy": session.get("gpu_policy") or "unknown",
        },
        "persona": session_persona(session),
        "identity": identity,
        "surface_coherence": surface_coherence,
        "service_worker": service_worker,
        "measurement_completeness": measurement_completeness,
        "contexts": context_summaries,
        "headers": {key: "present" for key in sorted(raw.get("headers", {}).keys())} if isinstance(raw.get("headers"), dict) else {},
        "webrtc": webrtc,
        "rendering": rendering,
        "red_flags": sorted(red_flags),
        "residual_risks": residual_risks,
    }
    return report


def text_has_ip_literal(text: str) -> bool:
    for token in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
        try:
            ipaddress.ip_address(token)
        except ValueError:
            continue
        return True
    return False


def sanitized_findings(report: dict[str, Any]) -> list[str]:
    text = json.dumps(report, sort_keys=True)
    findings: list[str] = []
    if CDP_WS_RE.search(text):
        findings.append("cdp_websocket_url")
    if TAKEOVER_TOKEN_RE.search(text):
        findings.append("takeover_token_url")
    if text_has_ip_literal(text):
        findings.append("ip_literal")
    if "runtime-data/profiles" in text or "runtime-data/tmp" in text:
        findings.append("private_runtime_path")
    if AUTH_MARKER_RE.search(text):
        findings.append("auth_cookie_form_marker")
    # Hostname guard intentionally focuses on raw local/candidate hostnames. Chrome
    # user-agent strings and timezone IDs are allowed; public detector URLs are not emitted.
    for forbidden in (".local", "relay.example", "devtools/browser"):
        if forbidden in text:
            findings.append("raw_hostname_or_capability")
            break
    return sorted(set(findings))


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    session = load_json(args.session_json)
    if args.fixture_json:
        raw = load_json(args.fixture_json)
    else:
        raw = asyncio.run(collect_live_probe(session))
    report = build_sanitized_report(raw, session, mode=args.mode)
    findings = sanitized_findings(report)
    write_report(args.out, report)
    measurement = report.get("measurement_completeness", {}) if isinstance(report.get("measurement_completeness"), dict) else {}
    measurement_complete = bool(measurement.get("complete"))
    unavailable_contexts = measurement.get("unavailable_contexts") if isinstance(measurement.get("unavailable_contexts"), dict) else {}
    strict_failures: list[str] = []
    if findings:
        strict_failures.append("sanitized_output_findings")
    if not measurement_complete:
        strict_failures.append("measurement_incomplete")
    output = {
        "out": str(args.out),
        "findings": findings,
        "identity_coherent": report["identity"]["coherent"],
        "measurement_complete": measurement_complete,
        "unavailable_contexts": unavailable_contexts,
    }
    if strict_failures:
        output["strict_failures"] = strict_failures
    print(json.dumps(output, indent=2))
    if args.strict and strict_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
