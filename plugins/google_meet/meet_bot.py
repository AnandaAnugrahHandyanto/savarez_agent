"""Headless Google Meet bot — Playwright + live-caption scraping.

Runs as a standalone subprocess spawned by ``process_manager.py``. Reads config
from env vars, writes status + transcript to files under
``$HERMES_HOME/workspace/meetings/<meeting-id>/``. The main hermes process
reads those files via the ``meet_*`` tools — no IPC beyond filesystem.

The scraping strategy mirrors OpenUtter (sumansid/openutter): we don't parse
WebRTC audio, we enable Google Meet's built-in live captions and observe the
captions container in the DOM via a MutationObserver. This is lossy and
English-biased but it is:

* deterministic (no API keys, no STT billing),
* works behind Meet's normal login / admission,
* survives Meet UI rewrites fairly well because the caption container has a
  stable ARIA role.

Run standalone for debugging::

    HERMES_MEET_URL=https://meet.google.com/abc-defg-hij \\
    HERMES_MEET_OUT_DIR=/tmp/meet-debug \\
    HERMES_MEET_HEADED=1 \\
    python -m plugins.google_meet.meet_bot

No meet.google.com URL → exits non-zero. Any URL that doesn't start with
``https://meet.google.com/`` is rejected (explicit-by-design).
"""

from __future__ import annotations

import json
import os
import re
import signal
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional

from hermes_constants import get_hermes_home

# Match ``https://meet.google.com/abc-defg-hij`` or ``.../lookup/...`` — the
# short three-segment code or a lookup URL. Anything else is rejected.
MEET_URL_RE = re.compile(
    r"^https://meet\.google\.com/("
    r"[a-z0-9]{3,}-[a-z0-9]{3,}-[a-z0-9]{3,}"
    r"|lookup/[^/?#]+"
    r"|new"
    r")(?:[/?#].*)?$"
)


# Filenames the bot reads/writes in ``HERMES_MEET_OUT_DIR``.
SAY_QUEUE_FILENAME = "say_queue.jsonl"
SAY_PCM_FILENAME = "speaker.pcm"


def _probe_cdp_url(cdp_url: str) -> bool:
    """Return True when *cdp_url* looks like a live Chrome DevTools endpoint."""
    if not cdp_url:
        return False
    try:
        with urllib.request.urlopen(f"{cdp_url.rstrip('/')}/json/version", timeout=2) as resp:
            json.load(resp)
        return True
    except Exception:
        return False


def _resolve_browser_cdp_url() -> Optional[str]:
    """Return the browser CDP endpoint to attach to, if one is available.

    Preference order:
      1. explicit environment overrides
      2. ``browser.cdp_url`` in the active Hermes config
      3. the live Hermes Chrome profile at ``http://127.0.0.1:18800`` if it is reachable
    """
    for key in ("HERMES_MEET_CDP_URL", "HERMES_BROWSER_CDP_URL"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw

    cfg_path = Path(get_hermes_home()) / "config.yaml"
    if cfg_path.is_file():
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            browser_cfg = data.get("browser") or {}
            raw = str(browser_cfg.get("cdp_url", "")).strip()
            if raw:
                return raw
        except Exception:
            pass

    live_url = "http://127.0.0.1:18800"
    if _probe_cdp_url(live_url):
        return live_url
    return None


def _is_safe_meet_url(url: str) -> bool:
    """Return True if *url* is a Google Meet URL we're willing to navigate to."""
    if not isinstance(url, str):
        return False
    return bool(MEET_URL_RE.match(url.strip()))


def _meeting_id_from_url(url: str) -> str:
    """Extract the 3-segment meeting code from a Meet URL.

    For ``https://meet.google.com/abc-defg-hij`` → ``abc-defg-hij``.
    For ``.../lookup/<id>`` or ``/new`` we fall back to a timestamped id — the
    bot won't know the real code until after redirect, and callers pass this
    through to filename anyway.
    """
    m = re.search(
        r"meet\.google\.com/([a-z0-9]{3,}-[a-z0-9]{3,}-[a-z0-9]{3,})",
        url or "",
    )
    if m:
        return m.group(1)
    return f"meet-{int(time.time())}"


# ---------------------------------------------------------------------------
# Status + transcript file writers
# ---------------------------------------------------------------------------

class _BotState:
    """Single-process mutable state, flushed to ``status.json`` on each change."""

    def __init__(self, out_dir: Path, meeting_id: str, url: str):
        self.out_dir = out_dir
        self.meeting_id = meeting_id
        self.url = url
        self.in_call = False
        self.captioning = False
        self.captions_enabled_attempted = False
        self.lobby_waiting = False
        self.join_attempted_at: Optional[float] = None
        self.joined_at: Optional[float] = None
        self.last_caption_at: Optional[float] = None
        self.transcript_lines = 0
        self.error: Optional[str] = None
        self.exited = False
        # v2 realtime fields.
        self.realtime = False
        self.realtime_ready = False
        self.realtime_device: Optional[str] = None
        self.audio_bytes_out: int = 0
        self.last_audio_out_at: Optional[float] = None
        self.last_barge_in_at: Optional[float] = None
        self.leave_reason: Optional[str] = None
        # Scraped captions, in order, deduped. Each entry is a dict of
        # {"ts": <epoch>, "speaker": str, "text": str}.
        self._seen: set = set()
        out_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_path = out_dir / "transcript.txt"
        self.status_path = out_dir / "status.json"
        self._flush()

    # -------- transcript ------------------------------------------------

    @staticmethod
    def _normalize_caption_parts(speaker: str, text: str) -> tuple[str, str]:
        """Normalize speaker/text pairs before dedupe + persistence.

        Meet's live caption DOM sometimes delivers the speaker in a separate
        node, and sometimes only as the first line of the raw caption block.
        This helper preserves the dedicated speaker when present, but also
        recovers a leading speaker line from raw block text so transcripts keep
        the attribution even when the DOM shifts.
        """
        speaker = (speaker or "").strip()
        text = (text or "").strip()
        if not text:
            return speaker, text

        if not speaker:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if len(lines) >= 2:
                maybe_speaker = lines[0]
                maybe_text = " ".join(lines[1:]).strip()
                if maybe_text:
                    return maybe_speaker, maybe_text
            if ":" in text:
                maybe_speaker, maybe_text = text.split(":", 1)
                maybe_speaker = maybe_speaker.strip()
                maybe_text = maybe_text.strip()
                if maybe_speaker and maybe_text and len(maybe_speaker) <= 80:
                    return maybe_speaker, maybe_text

        return speaker, text

    def record_caption(self, speaker: str, text: str) -> None:
        """Append a caption line if we haven't seen this exact (speaker, text)."""
        speaker, text = self._normalize_caption_parts(speaker, text)
        speaker = speaker or "Unknown"
        if not text:
            return
        key = f"{speaker}|{text}"
        if key in self._seen:
            return
        self._seen.add(key)
        self.transcript_lines += 1
        self.last_caption_at = time.time()
        ts = time.strftime("%H:%M:%S", time.localtime(self.last_caption_at))
        line = f"[{ts}] {speaker}: {text}\n"
        # Atomic-ish append — good enough for a single-writer.
        with self.transcript_path.open("a", encoding="utf-8") as f:
            f.write(line)
        self._flush()

    # -------- status file ----------------------------------------------

    def _flush(self) -> None:
        data = {
            "meetingId": self.meeting_id,
            "url": self.url,
            "inCall": self.in_call,
            "captioning": self.captioning,
            "captionsEnabledAttempted": self.captions_enabled_attempted,
            "lobbyWaiting": self.lobby_waiting,
            "joinAttemptedAt": self.join_attempted_at,
            "joinedAt": self.joined_at,
            "lastCaptionAt": self.last_caption_at,
            "transcriptLines": self.transcript_lines,
            "transcriptPath": str(self.transcript_path),
            "error": self.error,
            "exited": self.exited,
            "pid": os.getpid(),
            # v2 realtime telemetry.
            "realtime": self.realtime,
            "realtimeReady": self.realtime_ready,
            "realtimeDevice": self.realtime_device,
            "audioBytesOut": self.audio_bytes_out,
            "lastAudioOutAt": self.last_audio_out_at,
            "lastBargeInAt": self.last_barge_in_at,
            "leaveReason": self.leave_reason,
        }
        tmp = self.status_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.status_path)

    def set(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._flush()


# ---------------------------------------------------------------------------
# Playwright bot entry point
# ---------------------------------------------------------------------------

# JavaScript injected into the Meet tab to observe captions. Captures
# {speaker, text} tuples via a MutationObserver on the caption container,
# and exposes ``window.__hermesMeetDrain()`` to pull new entries. This
# mirrors the OpenUtter caption scraping approach.
_CAPTION_OBSERVER_JS = r"""
(() => {
  if (window.__hermesMeetInstalled) return;
  window.__hermesMeetInstalled = true;
  window.__hermesMeetQueue = [];

  const captionSelector = '[role="region"][aria-label*="aption" i], ' +
                          'div[jsname="YSxPC"], ' +  // legacy
                          'div[jsname="tgaKEf"]';    // current (Apr 2026)

  function pushEntry(speaker, text) {
    if (!text || !text.trim()) return;
    window.__hermesMeetQueue.push({
      ts: Date.now(),
      speaker: (speaker || '').trim(),
      text: text.trim(),
    });
  }

  function scan(root) {
    // Meet captions render as a list of rows; each row contains a speaker
    // label and a text block. Selectors vary across Meet rewrites; we try
    // a few shapes and fall back to raw text.
    const rows = root.querySelectorAll('div[jsname="dsyhDe"], div.CNusmb, div.TBMuR');
    if (rows.length) {
      rows.forEach((row) => {
        const spkEl = row.querySelector('div.KcIKyf, div.zs7s8d, span[jsname="YSxPC"]');
        const txtEl = row.querySelector('div.bh44bd, span[jsname="tgaKEf"], div.iTTPOb');
        const speaker = spkEl ? spkEl.innerText : '';
        const text = txtEl ? txtEl.innerText : row.innerText;
        pushEntry(speaker, text);
      });
      return;
    }
    // Fallback: keep the full caption block so Python can recover the
    // speaker name from the first line when Meet's DOM shape changes.
    pushEntry('', root.innerText || '');
  }

  function attach() {
    const el = document.querySelector(captionSelector);
    if (!el) return false;
    const obs = new MutationObserver(() => scan(el));
    obs.observe(el, { childList: true, subtree: true, characterData: true });
    scan(el);
    return true;
  }

  // Try now and retry on interval — the caption region only appears after
  // captions are enabled and someone speaks.
  if (!attach()) {
    const iv = setInterval(() => { if (attach()) clearInterval(iv); }, 1500);
  }

  window.__hermesMeetDrain = () => {
    const out = window.__hermesMeetQueue.slice();
    window.__hermesMeetQueue = [];
    return out;
  };
})();
"""


def _enable_captions_js() -> str:
    """Return a JS snippet that clicks Meet's captions toggle if present.

    This is click-first on purpose: the DOM text/ARIA labels are more stable
    than the keyboard shortcut, and we only use the shortcut as a fallback in
    Python if the click doesn't take.
    """
    return r"""
    (() => {
      const selectors = [
        'button[aria-label*="Turn on captions" i]',
        'button[aria-label*="Show captions" i]',
        'button[aria-label*="Captions" i]',
        '[role="button"][aria-label*="Turn on captions" i]',
        '[role="button"][aria-label*="Show captions" i]',
        '[role="button"][aria-label*="Captions" i]',
        'button:has-text("Turn on captions")',
        '[role="button"]:has-text("Turn on captions")',
      ];
      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          try {
            el.click();
            return true;
          } catch (e) {}
        }
      }
      return false;
    })();
    """


def _turn_on_captions(page, timeout_s: float = 10.0) -> bool:
    """Best-effort: enable Meet captions immediately after join.

    Returns True if we observe the toggle flip to "Turn off captions" or the
    caption region appear. False means we fell back to best-effort dispatches
    but didn't get a positive confirmation.
    """
    deadline = time.time() + max(1.0, timeout_s)
    last_error = None
    while time.time() < deadline:
        try:
            if _detect_captioning_enabled(page) is True:
                return True
        except Exception as e:
            last_error = e
        try:
            page.evaluate(_enable_captions_js())
        except Exception as e:
            last_error = e
        try:
            if _detect_captioning_enabled(page) is True:
                return True
        except Exception as e:
            last_error = e
        try:
            page.keyboard.press("c")
        except Exception as e:
            last_error = e
        try:
            if _detect_captioning_enabled(page) is True:
                return True
        except Exception as e:
            last_error = e
        time.sleep(0.8)
    if last_error:
        return False
    return False


def _detect_captioning_enabled(page) -> Optional[bool]:
    """Probe Meet's live UI to see whether captions are actually enabled.

    Returns:
      * True  — the UI indicates captions are on (toggle says "Turn off")
      * False — the UI indicates captions are off (toggle says "Turn on")
      * None  — the page is mid-transition or we couldn't tell confidently
    """
    probe = r"""
    (() => {
      const on = document.querySelector(
        'button[aria-label*="Turn off captions" i], ' +
        '[role="button"][aria-label*="Turn off captions" i], ' +
        'button[aria-label*="Hide captions" i], ' +
        '[role="button"][aria-label*="Hide captions" i], ' +
        'button[aria-label*="Live captions" i], ' +
        '[role="button"][aria-label*="Live captions" i]'
      );
      if (on) return true;

      const region = document.querySelector(
        '[role="region"][aria-label*="aption" i], ' +
        'div[jsname="YSxPC"], ' +
        'div[jsname="tgaKEf"]'
      );
      if (region) return true;

      const off = document.querySelector(
        'button[aria-label*="Turn on captions" i], ' +
        '[role="button"][aria-label*="Turn on captions" i], ' +
        'button[aria-label*="Show captions" i], ' +
        '[role="button"][aria-label*="Show captions" i]'
      );
      if (off) return false;

      return null;
    })();
    """
    try:
        val = page.evaluate(probe)
    except Exception:
        return None
    if val is True:
        return True
    if val is False:
        return False
    return None


def _sync_captioning_state(page, state: _BotState) -> None:
    """Fold the live Meet UI caption state into ``status.json``.

    This keeps the file-backed status aligned with what the browser is actually
    showing, without flipping the flag off during transient DOM gaps.
    """
    detected = _detect_captioning_enabled(page)
    if detected is None:
        return
    if detected != state.captioning:
        state.set(captioning=detected)


def _start_realtime_speaker(
    *,
    rt: dict,
    out_dir: Path,
    bridge_info: dict,
    api_key: str,
    model: str,
    voice: str,
    instructions: str,
    stop_flag: dict,
    state: "_BotState",
) -> None:
    """Wire up the OpenAI Realtime session + speaker thread + PCM pump.

    The speaker thread reads text lines from ``say_queue.jsonl``, sends each
    to OpenAI Realtime, and writes PCM audio into ``speaker.pcm``. A
    separate *pump* thread forwards that PCM into the OS audio sink so
    Chrome's fake mic picks it up. On Linux we pipe to ``paplay`` against
    the null-sink; on macOS the caller is expected to have the BlackHole
    device selected as default input.
    """
    try:
        from plugins.google_meet.realtime.openai_client import (
            RealtimeSession,
            RealtimeSpeaker,
        )
    except Exception as e:
        state.set(error=f"realtime import failed: {e}")
        return

    pcm_path = out_dir / SAY_PCM_FILENAME
    queue_path = out_dir / SAY_QUEUE_FILENAME
    processed_path = out_dir / "say_processed.jsonl"
    audio_log_path = out_dir / "realtime-audio.log"
    # Reset the sink file so we start clean each session.
    pcm_path.write_bytes(b"")
    # Make sure the queue exists so the speaker poller doesn't error on
    # first iteration.
    queue_path.touch()

    try:
        session = RealtimeSession(
            api_key=api_key,
            model=model,
            voice=voice,
            instructions=instructions,
            audio_sink_path=pcm_path,
            sample_rate=24000,
        )
        sys.stderr.write(
            f"[google_meet realtime] init session model={model} voice={voice} pcm={pcm_path} queue={queue_path} audio_log={audio_log_path}\n"
        )
        session.connect()
    except Exception as e:
        state.set(error=f"realtime connect failed: {e}")
        return

    rt["session"] = session

    def _stop_fn():
        return stop_flag.get("stop", False)

    rt["speaker_stop"] = lambda: stop_flag.__setitem__("stop", stop_flag.get("stop", False))

    speaker = RealtimeSpeaker(
        session=session,
        queue_path=queue_path,
        processed_path=processed_path,
    )

    def _speaker_loop():
        try:
            speaker.run_until_stopped(_stop_fn)
        except Exception as e:
            state.set(error=f"realtime speaker crashed: {e}")

    t_speaker = threading.Thread(target=_speaker_loop, name="meet-speaker", daemon=True)
    t_speaker.start()
    rt["speaker_thread"] = t_speaker

    # PCM pump: feeds speaker.pcm (24kHz s16le mono) into the OS audio
    # device that Chrome's fake mic reads from. The sink needs a *live*
    # stream, so we tail the growing PCM file and pipe only the newly
    # appended bytes into the playback process.
    platform_tag = (bridge_info or {}).get("platform")
    if platform_tag == "linux":
        import shutil as _shutil
        import subprocess as _sp
        import threading as _threading

        sink = (bridge_info or {}).get("write_target") or "hermes_meet_sink"
        try:
            player = "pacat" if _shutil.which("pacat") else "paplay"
            cmd = [
                player,
                "--playback" if player == "pacat" else "--raw",
                f"--device={sink}",
                "--rate=24000",
                "--format=s16le",
                "--channels=1",
            ]
            if player != "pacat":
                cmd.append("-")
            sys.stderr.write(f"[google_meet audio] starting player={player} sink={sink} cmd={' '.join(cmd)}\n")
            log_fp = open(audio_log_path, "a", buffering=1, encoding="utf-8")
            proc = _sp.Popen(
                cmd,
                stdin=_sp.PIPE,
                stdout=_sp.DEVNULL,
                stderr=log_fp,
                bufsize=0,
            )

            def _pump_pcm_tail() -> None:
                pos = 0
                try:
                    with open(pcm_path, "rb") as fp:
                        while not stop_flag.get("stop", False):
                            fp.seek(pos)
                            chunk = fp.read(4096)
                            if chunk:
                                pos = fp.tell()
                                if proc.stdin:
                                    try:
                                        proc.stdin.write(chunk)
                                        proc.stdin.flush()
                                    except Exception as exc:
                                        sys.stderr.write(f"[google_meet audio] write failed: {exc}\n")
                                        break
                            else:
                                time.sleep(0.05)
                finally:
                    try:
                        if proc.stdin:
                            proc.stdin.close()
                    except Exception:
                        pass

            def _monitor_player() -> None:
                while not stop_flag.get("stop", False):
                    rc = proc.poll()
                    if rc is not None:
                        sys.stderr.write(f"[google_meet audio] player exited rc={rc}\n")
                        state.set(error=f"audio player exited rc={rc}")
                        break
                    time.sleep(1.0)

            pump_thread = _threading.Thread(target=_pump_pcm_tail, name="meet-pcm-pump", daemon=True)
            pump_thread.start()
            monitor_thread = _threading.Thread(target=_monitor_player, name="meet-pcm-monitor", daemon=True)
            monitor_thread.start()
            rt["pcm_pump"] = proc
            rt["pcm_pump_thread"] = pump_thread
            rt["pcm_pump_monitor_thread"] = monitor_thread
            rt["pcm_pump_log_fp"] = log_fp
        except FileNotFoundError:
            state.set(error="pacat/paplay not found — install pulseaudio-utils for realtime on Linux")
    elif platform_tag == "darwin":
        # macOS: use ffmpeg to read speaker.pcm as it grows and write it to
        # BlackHole. The user must have BlackHole selected as the default
        # input in System Settings → Sound for Chrome to pick it up.
        import shutil as _shutil
        import subprocess as _sp
        import threading as _threading

        device_name = (bridge_info or {}).get("write_target") or "BlackHole 2ch"
        if _shutil.which("ffmpeg"):
            try:
                proc = _sp.Popen(
                    [
                        "ffmpeg",
                        "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-f", "s16le", "-ar", "24000", "-ac", "1",
                        "-i", "pipe:0",
                        "-f", "audiotoolbox",
                        "-audio_device_index", _mac_audio_device_index(device_name),
                        "-",
                    ],
                    stdin=_sp.PIPE,
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                    bufsize=0,
                )

                def _pump_pcm_tail() -> None:
                    pos = 0
                    try:
                        with open(pcm_path, "rb") as fp:
                            while not stop_flag.get("stop", False):
                                fp.seek(pos)
                                chunk = fp.read(4096)
                                if chunk:
                                    pos = fp.tell()
                                    if proc.stdin:
                                        try:
                                            proc.stdin.write(chunk)
                                            proc.stdin.flush()
                                        except Exception:
                                            break
                                else:
                                    time.sleep(0.05)
                    finally:
                        try:
                            if proc.stdin:
                                proc.stdin.close()
                        except Exception:
                            pass

                pump_thread = _threading.Thread(target=_pump_pcm_tail, name="meet-pcm-pump", daemon=True)
                pump_thread.start()
                rt["pcm_pump"] = proc
                rt["pcm_pump_thread"] = pump_thread
            except FileNotFoundError:
                state.set(error="ffmpeg not found — install via `brew install ffmpeg` for realtime on macOS")
            except Exception as e:
                state.set(error=f"macOS pcm pump failed to start: {e}")
        else:
            state.set(error="ffmpeg not found — install via `brew install ffmpeg` for realtime on macOS")


def _mac_audio_device_index(device_name: str) -> str:
    """Return the ffmpeg ``-audio_device_index`` for *device_name*, as a string.

    Probes ``ffmpeg -f avfoundation -list_devices true -i ''`` (which prints
    the device table on stderr) and matches *device_name* case-insensitively.
    Defaults to ``"0"`` if the device can't be found — caller will get a
    misrouted stream but not a crash, and the error will be obvious.
    """
    import subprocess as _sp

    try:
        out = _sp.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return "0"
    # ffmpeg prints the table on stderr. Lines look like:
    #   [AVFoundation indev @ 0x...] [0] BlackHole 2ch
    import re as _re

    needle = device_name.strip().lower()
    for line in (out.stderr or "").splitlines():
        m = _re.search(r"\[(\d+)\]\s+(.+)$", line)
        if not m:
            continue
        if m.group(2).strip().lower() == needle:
            return m.group(1)
    return "0"


def _open_browser_session(
    pw,
    *,
    headed: bool,
    auth_state: str,
    chrome_env: dict,
    chrome_args: list[str],
):
    """Open Meet in the live Hermes CDP browser if available, else locally.

    Returns ``(browser, context, page, using_cdp)``.
    """
    for key, value in chrome_env.items():
        os.environ[key] = value

    cdp_url = _resolve_browser_cdp_url()
    if cdp_url:
        try:
            browser = pw.chromium.connect_over_cdp(cdp_url)
            if not browser.contexts:
                raise RuntimeError(f"connected to {cdp_url} but no browser contexts were available")
            context = browser.contexts[0]
            try:
                context.grant_permissions(["microphone", "camera"], origin="https://meet.google.com")
            except Exception:
                pass
            page = context.new_page()
            return browser, context, page, True
        except Exception:
            pass

    browser = pw.chromium.launch(
        headless=not headed,
        args=chrome_args,
    )
    context_args = {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "permissions": ["microphone", "camera"],
    }
    if auth_state and Path(auth_state).is_file():
        context_args["storage_state"] = auth_state
    context = browser.new_context(**context_args)
    page = context.new_page()
    return browser, context, page, False


def run_bot() -> int:  # noqa: C901 — orchestration, explicit branches
    url = os.environ.get("HERMES_MEET_URL", "").strip()
    out_dir_env = os.environ.get("HERMES_MEET_OUT_DIR", "").strip()
    headed = os.environ.get("HERMES_MEET_HEADED", "").lower() in {"1", "true", "yes"}
    auth_state = os.environ.get("HERMES_MEET_AUTH_STATE", "").strip()
    guest_name = os.environ.get("HERMES_MEET_GUEST_NAME", "Hermes Agent")
    duration_s = _parse_duration(os.environ.get("HERMES_MEET_DURATION", ""))
    # v2: optional realtime mode. Enabled when HERMES_MEET_MODE=realtime.
    mode = os.environ.get("HERMES_MEET_MODE", "transcribe").strip().lower()
    realtime_model = os.environ.get("HERMES_MEET_REALTIME_MODEL", "gpt-realtime")
    realtime_voice = os.environ.get("HERMES_MEET_REALTIME_VOICE", "alloy")
    realtime_instructions = os.environ.get("HERMES_MEET_REALTIME_INSTRUCTIONS", "")
    realtime_api_key = os.environ.get("HERMES_MEET_REALTIME_KEY") or os.environ.get("OPENAI_API_KEY", "")

    if not url or not _is_safe_meet_url(url):
        sys.stderr.write(
            "google_meet bot: refusing to launch — HERMES_MEET_URL must be a "
            "meet.google.com URL. got: %r\n" % url
        )
        return 2
    if not out_dir_env:
        sys.stderr.write("google_meet bot: HERMES_MEET_OUT_DIR is required\n")
        return 2

    out_dir = Path(out_dir_env)
    meeting_id = _meeting_id_from_url(url)
    state = _BotState(out_dir=out_dir, meeting_id=meeting_id, url=url)

    # SIGTERM → exit cleanly so the parent ``meet_leave`` gets a finalized
    # transcript. We set a flag instead of raising so the Playwright context
    # teardown runs in the finally block below.
    stop_flag = {"stop": False}

    def _on_signal(_sig, _frame):
        stop_flag["stop"] = True

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # v2 realtime: provision virtual audio device + start speaker thread.
    # We track these in a dict so the finally block can tear them down
    # regardless of how we exit. If anything in the realtime setup fails we
    # fall back to transcribe mode with a status flag.
    rt = {
        "enabled": mode == "realtime",
        "bridge": None,            # AudioBridge | None
        "bridge_info": None,       # dict | None
        "session": None,           # RealtimeSession | None
        "speaker_thread": None,    # threading.Thread | None
        "speaker_stop": None,      # callable | None
        "pcm_pump": None,          # subprocess.Popen | None
        "pcm_pump_thread": None,   # threading.Thread | None
        "pcm_pump_monitor_thread": None,   # threading.Thread | None
        "pcm_pump_log_fp": None,   # file handle for playback stderr
    }
    if rt["enabled"]:
        if not realtime_api_key:
            state.set(error="realtime mode requested but no API key in HERMES_MEET_REALTIME_KEY/OPENAI_API_KEY — falling back to transcribe")
            rt["enabled"] = False
        else:
            try:
                from plugins.google_meet.audio_bridge import AudioBridge
                bridge = AudioBridge()
                rt["bridge_info"] = bridge.setup()
                rt["bridge"] = bridge
                state.set(realtime=True, realtime_device=rt["bridge_info"].get("device_name"))
            except Exception as e:
                state.set(error=f"audio bridge setup failed: {e} — falling back to transcribe")
                rt["enabled"] = False

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        state.set(error=f"playwright not installed: {e}", exited=True)
        sys.stderr.write(
            "google_meet bot: playwright is not installed. Run "
            "`pip install playwright && python -m playwright install chromium`\n"
        )
        if rt["bridge"]:
            rt["bridge"].teardown()
        return 3

    # Chrome env: if realtime is live on Linux, point PULSE_SOURCE at the
    # virtual source so Chrome's fake mic reads the audio we generate.
    chrome_env = os.environ.copy()
    chrome_args = [
        "--use-fake-ui-for-media-stream",
        "--disable-blink-features=AutomationControlled",
    ]
    if not rt["enabled"]:
        # v1-style fake device (silence) — we don't care about mic content
        # when we're not speaking.
        chrome_args.insert(1, "--use-fake-device-for-media-stream")
    elif rt["bridge_info"] and rt["bridge_info"].get("platform") == "linux":
        chrome_env["PULSE_SOURCE"] = rt["bridge_info"].get("device_name", "")

    try:
        with sync_playwright() as pw:
            browser, context, page, using_cdp = _open_browser_session(
                pw,
                headed=headed,
                auth_state=auth_state,
                chrome_env=chrome_env,
                chrome_args=chrome_args,
            )

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception as e:
                state.set(error=f"navigate failed: {e}", exited=True)
                return 4

            # Guest-mode: Meet shows a name field before "Ask to join". When
            # we're authed, we instead see "Join now".
            _try_guest_name(page, guest_name)
            _click_join(page, state)

            # Install caption observer and enable captions immediately after join.
            captions_enabled = False
            try:
                captions_enabled = _turn_on_captions(page)
            except Exception:
                pass
            state.set(captions_enabled_attempted=True)
            try:
                page.evaluate(_CAPTION_OBSERVER_JS)
            except Exception as e:
                state.set(error=f"caption observer install failed: {e}")

            # Note: in_call=False until admission is confirmed (we detect
            # either the Leave button or the caption region, signalling we
            # made it past the lobby).
            captioning = _detect_captioning_enabled(page)
            if captioning is None:
                captioning = bool(captions_enabled)
            state.set(captioning=bool(captioning), join_attempted_at=time.time())

            # v2 realtime: start the speaker thread reading from the
            # plugin-side say queue. The thread reads JSONL lines written by
            # meet_say, calls OpenAI Realtime, and streams the audio PCM to
            # the virtual sink that Chrome's fake-mic is pointed at.
            if rt["enabled"]:
                _start_realtime_speaker(
                    rt=rt,
                    out_dir=out_dir,
                    bridge_info=rt["bridge_info"],
                    api_key=realtime_api_key,
                    model=realtime_model,
                    voice=realtime_voice,
                    instructions=realtime_instructions,
                    stop_flag=stop_flag,
                    state=state,
                )
                if rt["session"] is not None:
                    state.set(realtime_ready=True)

            # Admission + drain loop. Runs until SIGTERM, duration expiry,
            # or the page detects "You were removed / you left the
            # meeting". Responsible for:
            #   * detecting admission (Leave button visible → in_call=True)
            #   * timing out stuck-in-lobby (default 5 minutes)
            #   * draining scraped captions into the transcript
            #   * triggering realtime barge-in when a human speaks while
            #     the bot is generating audio
            #   * periodically flushing realtime counters into status.json
            deadline = (time.time() + duration_s) if duration_s else None
            lobby_deadline = time.time() + float(
                os.environ.get("HERMES_MEET_LOBBY_TIMEOUT", "300")
            )
            last_admission_check = 0.0
            last_caption_attempt = 0.0
            while not stop_flag["stop"]:
                now = time.time()
                if deadline and now > deadline:
                    state.set(leave_reason="duration_expired")
                    break

                # Admission detection every ~3s until admitted.
                if not state.in_call and (now - last_admission_check) > 3.0:
                    last_admission_check = now
                    admitted = _detect_admission(page)
                    if admitted:
                        state.set(
                            in_call=True,
                            lobby_waiting=False,
                            joined_at=now,
                        )
                    elif now > lobby_deadline:
                        state.set(
                            error=(
                                "lobby timeout — host never admitted the bot "
                                f"within {int(lobby_deadline - state.join_attempted_at) if state.join_attempted_at else 0}s"
                            ),
                            leave_reason="lobby_timeout",
                        )
                        break
                    elif _detect_denied(page):
                        state.set(
                            error="host denied admission",
                            leave_reason="denied",
                        )
                        break

                try:
                    queued = page.evaluate("window.__hermesMeetDrain && window.__hermesMeetDrain()")
                    if isinstance(queued, list):
                        for entry in queued:
                            if not isinstance(entry, dict):
                                continue
                            speaker = str(entry.get("speaker", ""))
                            text = str(entry.get("text", ""))
                            state.record_caption(speaker=speaker, text=text)
                            # Barge-in: if the bot is currently generating
                            # audio AND a real human just spoke, cancel the
                            # in-flight response so we don't talk over them.
                            if rt["enabled"] and rt["session"] is not None:
                                if _looks_like_human_speaker(speaker, guest_name):
                                    try:
                                        cancelled = rt["session"].cancel_response()
                                        if cancelled:
                                            state.set(last_barge_in_at=now)
                                    except Exception:
                                        pass
                except Exception:
                    # Meet reloaded or we got booted — try to detect and
                    # exit gracefully rather than spinning.
                    if page.is_closed():
                        state.set(leave_reason="page_closed")
                        break

                # Keep captioning status in sync with the live Meet UI so the
                # file-backed status doesn't lag or get stuck when the DOM
                # changes or Meet silently toggles the control.
                _sync_captioning_state(page, state)
                if state.in_call and not state.captioning and (now - last_caption_attempt) > 5.0:
                    last_caption_attempt = now
                    try:
                        if _turn_on_captions(page, timeout_s=3.0):
                            state.set(captioning=True, captions_enabled_attempted=True)
                    except Exception:
                        pass

                # Fold the realtime session's byte/timestamp counters into
                # the status file so meet_status can surface them.
                if rt["session"] is not None:
                    state.set(
                        audio_bytes_out=getattr(rt["session"], "audio_bytes_out", 0),
                        last_audio_out_at=getattr(rt["session"], "last_audio_out_at", None),
                    )

                time.sleep(1.0)

            # Try to leave cleanly — click "Leave call" button if present.
            try:
                page.evaluate(
                    "() => { const b = document.querySelector('button[aria-label*=\"eave call\"]');"
                    " if (b) b.click(); }"
                )
            except Exception:
                pass

            if using_cdp:
                try:
                    page.close()
                except Exception:
                    pass
            else:
                context.close()
                browser.close()
            # v2: teardown realtime speaker + audio bridge.
            if rt["speaker_stop"]:
                try:
                    rt["speaker_stop"]()
                except Exception:
                    pass
            if rt["speaker_thread"] is not None:
                try:
                    rt["speaker_thread"].join(timeout=5.0)
                except Exception:
                    pass
            if rt.get("pcm_pump_thread") is not None:
                try:
                    rt["pcm_pump_thread"].join(timeout=5.0)
                except Exception:
                    pass
            if rt.get("pcm_pump_monitor_thread") is not None:
                try:
                    rt["pcm_pump_monitor_thread"].join(timeout=5.0)
                except Exception:
                    pass
            if rt.get("pcm_pump") is not None:
                try:
                    rt["pcm_pump"].terminate()
                    rt["pcm_pump"].wait(timeout=5.0)
                except Exception:
                    try:
                        rt["pcm_pump"].kill()
                    except Exception:
                        pass
            if rt.get("pcm_pump_log_fp") is not None:
                try:
                    rt["pcm_pump_log_fp"].close()
                except Exception:
                    pass
            if rt["session"]:
                try:
                    rt["session"].close()
                except Exception:
                    pass
            if rt["bridge"]:
                try:
                    rt["bridge"].teardown()
                except Exception:
                    pass
            state.set(in_call=False, captioning=False, exited=True)
            return 0

    except Exception as e:
        state.set(error=f"unhandled: {e}", exited=True)
        return 1


def _try_guest_name(page, guest_name: str) -> None:
    """If Meet is showing a guest-name input, type *guest_name* into it."""
    try:
        # Meet's guest name input has placeholder "Your name".
        locator = page.locator('input[aria-label*="name" i]').first
        if locator.count() and locator.is_visible():
            locator.fill(guest_name, timeout=2_000)
    except Exception:
        pass


def _detect_admission(page) -> bool:
    """True if we're clearly past the lobby and in the call itself.

    Uses a JS-side probe because Meet's DOM structure varies by client
    version. We check several high-signal indicators and declare admission
    on the first hit:

      1. Leave-call button is present (``aria-label`` contains "eave call").
      2. Caption region has appeared (we installed the observer and it attached).
      3. The participant list container is visible.

    Conservative by default — returns False on any error.
    """
    probe = r"""
    (() => {
      const leave = document.querySelector('button[aria-label*="eave call" i], [role="button"][aria-label*="eave call" i], button[aria-label*="end call" i], [role="button"][aria-label*="end call" i], button[aria-label*="leave meeting" i], [role="button"][aria-label*="leave meeting" i]');
      if (leave) return true;
      if (window.__hermesMeetInstalled) {
        const caps = document.querySelector(
          '[role="region"][aria-label*="aption" i], ' +
          'div[jsname="YSxPC"], div[jsname="tgaKEf"]'
        );
        if (caps) return true;
      }
      const parts = document.querySelector('[aria-label*="articipants" i], [role="button"][aria-label*="articipants" i]');
      if (parts) return true;
      return false;
    })();
    """
    try:
        return bool(page.evaluate(probe))
    except Exception:
        return False


def _detect_denied(page) -> bool:
    """True when Meet is showing a 'you were denied' / 'no one admitted' page."""
    probe = r"""
    (() => {
      const text = document.body ? document.body.innerText || '' : '';
      // English only — matches what shows up when the host denies or
      // removes a guest.
      if (/You can't join this video call/i.test(text)) return true;
      if (/You were removed from the meeting/i.test(text)) return true;
      if (/No one responded to your request to join/i.test(text)) return true;
      return false;
    })();
    """
    try:
        return bool(page.evaluate(probe))
    except Exception:
        return False


def _looks_like_human_speaker(speaker: str, bot_guest_name: str) -> bool:
    """Whether a caption line's speaker is probably a human, not our bot echo.

    Meet attributes captions to the speaker's display name. When Chrome is
    reading our fake mic, Meet still attributes captions to *our* bot name
    (because the bot is the one "speaking"). We don't want those to trigger
    barge-in. Anything else — real participant names — does.

    Conservative: unknown / blank speakers (common when caption scraping
    falls back to raw text) do NOT trigger barge-in, because we can't tell
    whether it was a human or us.
    """
    if not speaker or not speaker.strip():
        return False
    spk = speaker.strip().lower()
    if spk in {"unknown", "you", bot_guest_name.strip().lower()}:
        return False
    return True


def _click_mic_prompt(page) -> bool:
    """Dismiss Meet's pre-join audio prompt when it appears.

    Meet sometimes inserts a modal asking whether people should hear you.
    For this bot we want the no-mic path so the join flow can continue
    without waiting for device permissions or a stale overlay.
    """
    for label in ("Continue without microphone", "Use microphone"):
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.count() and btn.is_visible():
                try:
                    btn.scroll_into_view_if_needed(timeout=1_000)
                except Exception:
                    pass
                try:
                    btn.click(timeout=2_000)
                except Exception:
                    btn.click(timeout=2_000, force=True)
                return True
        except Exception:
            continue
    return False


def _click_join(page, state: _BotState, retries: int = 3) -> None:
    """Click 'Join now' or 'Ask to join' if either button is visible.

    The Meet lobby is a little slippery: a click may be intercepted by the
    microphone prompt, the target may re-render, or the button may appear one
    beat later than the first DOM probe. We therefore:

    1. dismiss the mic prompt if present,
    2. try both join labels,
    3. verify admission, and
    4. retry a couple of times if the page still looks like the lobby.

    Flags ``lobby_waiting`` when we hit the "waiting for host to admit you"
    state so the agent can surface that in status.
    """
    join_labels = ("Join now", "Ask to join")
    for _ in range(max(1, retries)):
        _click_mic_prompt(page)

        clicked_label = None
        for label in join_labels:
            try:
                btn = page.get_by_role("button", name=label, exact=False).first
                if not (btn.count() and btn.is_visible()):
                    continue
                try:
                    btn.scroll_into_view_if_needed(timeout=1_000)
                except Exception:
                    pass
                try:
                    btn.click(timeout=3_000)
                except Exception:
                    btn.click(timeout=3_000, force=True)
                clicked_label = label
                if label == "Ask to join":
                    state.set(lobby_waiting=True)
                break
            except Exception:
                continue

        if _detect_admission(page):
            return

        if clicked_label == "Ask to join":
            # If Meet actually accepted the request, the lobby button should
            # disappear and admission will be detected on the next poll. If the
            # button is still there, keep retrying a couple of times in case the
            # first click was swallowed by a rerender or overlay.
            try:
                still_visible = bool(
                    page.get_by_role("button", name="Ask to join", exact=False).first.count()
                    and page.get_by_role("button", name="Ask to join", exact=False).first.is_visible()
                )
            except Exception:
                still_visible = False
            if not still_visible:
                return
        elif clicked_label == "Join now":
            try:
                still_visible = bool(
                    page.get_by_role("button", name="Join now", exact=False).first.count()
                    and page.get_by_role("button", name="Join now", exact=False).first.is_visible()
                )
            except Exception:
                still_visible = False
            if not still_visible:
                # We clicked the button but Meet is still re-rendering or
                # switching states; give it another beat before the next loop.
                pass

        try:
            page.wait_for_timeout(800)
        except Exception:
            time.sleep(0.8)


def _parse_duration(raw: str) -> Optional[float]:
    """Parse ``30m`` / ``2h`` / ``90`` (seconds) → float seconds, or None."""
    if not raw:
        return None
    raw = raw.strip().lower()
    try:
        if raw.endswith("h"):
            return float(raw[:-1]) * 3600
        if raw.endswith("m"):
            return float(raw[:-1]) * 60
        if raw.endswith("s"):
            return float(raw[:-1])
        return float(raw)
    except ValueError:
        return None


if __name__ == "__main__":  # pragma: no cover — subprocess entry point
    sys.exit(run_bot())
