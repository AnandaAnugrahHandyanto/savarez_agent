#!/usr/bin/env python3
"""Public YouTube audio fallback: yt-dlp audio-only download + local faster-whisper ASR.

Safety boundary for Spearhead/Hermes:
- public YouTube references; user-authorized target-domain Firefox cookies may be used for identity/access
- no proxy/VPN/IP rotation, CAPTCHA bypass, paid/token adapters, or secret printing
- audio-only by default; optional full public video container acquisition when needed
- no redistribution of downloaded media
- raw audio/video is deleted after successful transcription by default
- evidence keeps non-secret video id / hashes / tool versions, not signed media URLs
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

DEFAULT_FIREFOX_PROFILE = Path("/mnt/c/Users/filip/AppData/Roaming/Mozilla/Firefox/Profiles/a7nm83ps.default-release")

try:
    from acquisition import classify_source, hash_url, redact_acquisition_text
except Exception:  # keep script usable if run outside the skill dir
    classify_source = None

    def hash_url(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()

    def redact_acquisition_text(value: str | None) -> str | None:
        return value


def _which(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], *, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def _tool_version(cmd: list[str]) -> str | None:
    path = _which(cmd[0])
    if not path:
        return None
    try:
        cp = _run(cmd, timeout=30)
    except Exception as exc:
        return f"{path} ({type(exc).__name__}: {exc})"
    first = (cp.stdout or cp.stderr).splitlines()[0] if (cp.stdout or cp.stderr) else ""
    return f"{path} :: {first}".strip()


def _format_ts(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _safe_video_id(url_or_id: str) -> str | None:
    if classify_source is None:
        return None
    try:
        return classify_source(url_or_id).video_id
    except Exception:
        return None


def _build_ytdlp_cmd(
    url: str,
    outtmpl: Path,
    *,
    max_duration: int | None,
    media_kind: str = "audio",
    use_firefox_cookies: bool = False,
    firefox_profile: Path = DEFAULT_FIREFOX_PROFILE,
) -> list[str]:
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-cookies",
        "--no-cache-dir",
        "--ignore-config",
        "--no-write-comments",
        "--no-write-info-json",
        "--no-write-thumbnail",
        "-o", str(outtmpl),
    ]
    if use_firefox_cookies:
        if not (firefox_profile / "cookies.sqlite").exists():
            raise RuntimeError(f"Firefox cookies.sqlite not found at {firefox_profile}")
        cmd += ["--cookies-from-browser", f"firefox:{firefox_profile}"]
    if media_kind == "audio":
        cmd += [
            "--extract-audio",
            "--audio-format", "m4a",
            "--audio-quality", "5",
        ]
    elif media_kind == "video":
        cmd += ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]
    else:
        raise ValueError(f"unsupported media_kind: {media_kind}")
    if max_duration:
        # Requires recent yt-dlp. Kept optional; absence fails loudly in evidence.
        cmd += ["--download-sections", f"*0-{int(max_duration)}"]
    cmd.append(url)
    return cmd


def download_media(
    url: str,
    workdir: Path,
    *,
    max_duration: int | None = None,
    media_kind: str = "audio",
    use_firefox_cookies: bool = False,
    firefox_profile: Path = DEFAULT_FIREFOX_PROFILE,
) -> Path:
    if not _which("yt-dlp"):
        raise RuntimeError("yt-dlp not found in PATH")
    if not _which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")
    outtmpl = workdir / "media.%(ext)s"
    cmd = _build_ytdlp_cmd(
        url,
        outtmpl,
        max_duration=max_duration,
        media_kind=media_kind,
        use_firefox_cookies=use_firefox_cookies,
        firefox_profile=firefox_profile,
    )
    cp = _run(cmd, timeout=3600)
    if cp.returncode != 0:
        raise RuntimeError(redact_acquisition_text(cp.stderr.strip() or cp.stdout.strip() or f"yt-dlp rc={cp.returncode}"))
    candidates = sorted(workdir.glob("media.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("yt-dlp completed but no media artifact was found")
    return candidates[0]


def transcribe(audio_path: Path, *, model_name: str, language: str | None, device: str, compute_type: str) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper not installed/importable") from exc

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    kwargs: dict[str, Any] = {"vad_filter": True}
    if language:
        kwargs["language"] = language
    segments_iter, info = model.transcribe(str(audio_path), **kwargs)
    segments = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append({
            "start": float(seg.start),
            "end": float(seg.end),
            "text": text,
        })
    return {
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "segments": segments,
        "full_text": " ".join(s["text"] for s in segments),
        "timestamped_text": "\n".join(f"{_format_ts(s['start'])} {s['text']}" for s in segments),
    }


def self_test() -> dict[str, Any]:
    checks = {
        "yt_dlp": _tool_version(["yt-dlp", "--version"]),
        "ffmpeg": _tool_version(["ffmpeg", "-version"]),
        "ffprobe": _tool_version(["ffprobe", "-version"]),
        "nvidia_smi": _tool_version(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
    }
    try:
        import faster_whisper  # noqa: F401
        checks["faster_whisper"] = "importable"
    except Exception as exc:
        checks["faster_whisper"] = f"NOT importable: {exc}"

    with tempfile.TemporaryDirectory(prefix="yt-asr-selftest-") as td:
        wav = Path(td) / "tone.wav"
        cp = _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=0.25", str(wav)
        ], timeout=30)
        checks["ffmpeg_generate_wav_rc"] = cp.returncode
        checks["ffmpeg_generate_wav_exists"] = wav.exists() and wav.stat().st_size > 0
    ok = bool(checks["yt_dlp"] and checks["ffmpeg"] and checks["ffprobe"] and checks["faster_whisper"] == "importable" and checks["ffmpeg_generate_wav_exists"])
    return {"ok": ok, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Download public YouTube audio and transcribe locally with faster-whisper")
    parser.add_argument("url", nargs="?", help="Public YouTube URL or video id")
    parser.add_argument("--language", "-l", default=None, help="Optional language code, e.g. en/cs/tr")
    parser.add_argument("--model", default=os.environ.get("YOUTUBE_ASR_MODEL", "small"), help="faster-whisper model name/path (default: small)")
    parser.add_argument("--device", default=os.environ.get("YOUTUBE_ASR_DEVICE", "auto"), help="auto/cuda/cpu (default: auto)")
    parser.add_argument("--compute-type", default=os.environ.get("YOUTUBE_ASR_COMPUTE_TYPE", "auto"), help="auto/float16/int8/etc. (default: auto)")
    parser.add_argument("--cache-dir", default=os.environ.get("YOUTUBE_ASR_CACHE_DIR", "~/spearhead-execution/youtube-local-asr-cache"))
    parser.add_argument("--keep-audio", action="store_true", help="Keep raw audio after successful transcription (default: delete)")
    parser.add_argument("--max-duration", type=int, default=None, help="Optional first N seconds only, for smoke tests")
    parser.add_argument("--media-kind", choices=["audio", "video"], default="audio", help="Download audio-only by default; use video when the fallback needs the full public media container")
    parser.add_argument("--use-firefox-cookies", action="store_true", help="Use Filip's native Firefox profile cookies for target-site identity/access; never prints cookie values")
    parser.add_argument("--firefox-profile", default=str(DEFAULT_FIREFOX_PROFILE), help="Firefox profile path for --use-firefox-cookies")
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--timestamps", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="Check local deps without network/model download")
    args = parser.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if not args.url:
        parser.error("url is required unless --self-test is used")

    cache_root = Path(args.cache_dir).expanduser()
    cache_root.mkdir(parents=True, exist_ok=True)
    request_id = hash_url(args.url).split(":", 1)[1][:12]
    workdir = cache_root / f"yt-asr-{request_id}-{int(time.time())}"
    workdir.mkdir(parents=True, exist_ok=True)

    media_path: Path | None = None
    media_deleted = False
    try:
        media_path = download_media(
            args.url,
            workdir,
            max_duration=args.max_duration,
            media_kind=args.media_kind,
            use_firefox_cookies=args.use_firefox_cookies,
            firefox_profile=Path(args.firefox_profile).expanduser(),
        )
        media_sha256 = hashlib.sha256(media_path.read_bytes()).hexdigest()
        result = transcribe(media_path, model_name=args.model, language=args.language, device=args.device, compute_type=args.compute_type)
        if not args.keep_audio:
            media_path.unlink(missing_ok=True)
            media_deleted = True
        payload = {
            "status": "OK",
            "source": "youtube_audio_local_asr",
            "url_hash": hash_url(args.url),
            "video_id": _safe_video_id(args.url),
            "model": args.model,
            "device": args.device,
            "compute_type": args.compute_type,
            "media_kind": args.media_kind,
            "auth": {"firefox_cookies_used": bool(args.use_firefox_cookies), "cookie_values_logged": False},
            "transcript_provenance": {"kind": "automatic", "is_asr": True, "local": True},
            "media": {"sha256": media_sha256, "kept": bool(args.keep_audio and media_path.exists()), "deleted_after_success": media_deleted},
            "tools": {
                "yt_dlp": _tool_version(["yt-dlp", "--version"]),
                "ffmpeg": _tool_version(["ffmpeg", "-version"]),
                "nvidia_smi": _tool_version(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
            },
            **result,
        }
    except Exception as exc:
        payload = {
            "status": "ERROR",
            "source": "youtube_audio_local_asr",
            "url_hash": hash_url(args.url),
            "video_id": _safe_video_id(args.url),
            "error": redact_acquisition_text(str(exc)),
            "workdir": str(workdir),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    if args.text_only:
        print(payload["timestamped_text"] if args.timestamps else payload["full_text"])
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
