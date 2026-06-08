#!/usr/bin/env python3
"""
Fetch a YouTube video transcript and output it as structured JSON.

Usage:
    python fetch_transcript.py <url_or_video_id> [--language en,tr] [--timestamps]

Output (JSON):
    {
        "video_id": "...",
        "language": "en",
        "segments": [{"text": "...", "start": 0.0, "duration": 2.5}, ...],
        "full_text": "complete transcript as plain text",
        "timestamped_text": "00:00 first line\n00:05 second line\n..."
    }

Install dependency:  pip install youtube-transcript-api
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def extract_video_id(url_or_id: str) -> str:
    """Extract the 11-character video ID from various YouTube URL formats."""
    url_or_id = url_or_id.strip()
    patterns = [
        r'(?:v=|youtu\.be/|shorts/|embed/|live/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fetch_transcript(video_id: str, languages: list = None):
    """Fetch transcript segments from YouTube.

    Returns a list of dicts with 'text', 'start', and 'duration' keys.
    Compatible with youtube-transcript-api v1.x.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("Error: youtube-transcript-api not installed. Run: pip install youtube-transcript-api",
              file=sys.stderr)
        sys.exit(1)

    api = YouTubeTranscriptApi()
    if languages:
        result = api.fetch(video_id, languages=languages)
    else:
        result = api.fetch(video_id)

    # v1.x returns FetchedTranscriptSnippet objects; normalize to dicts
    return [
        {"text": seg.text, "start": seg.start, "duration": seg.duration}
        for seg in result
    ]


def fetch_via_local_asr(url_or_id: str, args) -> dict:
    """Fallback to local yt-dlp audio download + faster-whisper ASR."""
    script = Path(__file__).with_name("youtube_local_asr.py")
    cmd = [sys.executable, str(script), url_or_id, "--model", args.asr_model,
           "--device", args.asr_device, "--compute-type", args.asr_compute_type]
    if args.language:
        # faster-whisper accepts one language at a time; use the first requested language.
        cmd += ["--language", args.language.split(",")[0].strip()]
    if args.keep_audio:
        cmd.append("--keep-audio")
    if args.use_firefox_cookies:
        cmd.append("--use-firefox-cookies")
        cmd += ["--firefox-profile", args.firefox_profile]
    completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        try:
            payload = json.loads(completed.stdout)
        except Exception:
            payload = {"error": completed.stderr.strip() or completed.stdout.strip() or "local ASR failed"}
        raise RuntimeError(f"Local ASR fallback failed: {payload.get('error', payload)}")
    return json.loads(completed.stdout)


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube transcript as JSON")
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--language", "-l", default=None,
                        help="Comma-separated language codes (e.g. en,tr). Default: auto")
    parser.add_argument("--timestamps", "-t", action="store_true",
                        help="Include timestamped text in output")
    parser.add_argument("--text-only", action="store_true",
                        help="Output plain text instead of JSON")
    parser.add_argument("--fallback-local-asr", action="store_true",
                        help="If public transcript fetch fails, download public audio with yt-dlp and transcribe locally via faster-whisper")
    parser.add_argument("--asr-model", default="small", help="faster-whisper model for --fallback-local-asr")
    parser.add_argument("--asr-device", default="auto", help="faster-whisper device for --fallback-local-asr: auto/cuda/cpu")
    parser.add_argument("--asr-compute-type", default="auto", help="faster-whisper compute type for --fallback-local-asr")
    parser.add_argument("--keep-audio", action="store_true", help="Keep raw audio after local ASR; default deletes it after success")
    parser.add_argument("--use-firefox-cookies", action="store_true", help="Let yt-dlp use Filip's native Firefox profile cookies for target-site identity/access during local ASR fallback")
    parser.add_argument("--firefox-profile", default="/mnt/c/Users/filip/AppData/Roaming/Mozilla/Firefox/Profiles/a7nm83ps.default-release", help="Firefox profile path for --use-firefox-cookies")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    languages = [l.strip() for l in args.language.split(",")] if args.language else None

    try:
        segments = fetch_transcript(video_id, languages)
    except Exception as e:
        if args.fallback_local_asr:
            try:
                asr_payload = fetch_via_local_asr(args.url, args)
            except Exception as asr_e:
                print(json.dumps({"error": str(asr_e)}, ensure_ascii=False))
                sys.exit(1)
            if args.text_only:
                print(asr_payload.get("timestamped_text") if args.timestamps else asr_payload.get("full_text", ""))
                return
            print(json.dumps(asr_payload, ensure_ascii=False, indent=2))
            return
        error_msg = str(e)
        if "disabled" in error_msg.lower():
            print(json.dumps({"error": "Transcripts are disabled for this video."}))
        elif "no transcript" in error_msg.lower():
            print(json.dumps({"error": f"No transcript found. Try specifying a language with --language."}))
        else:
            print(json.dumps({"error": error_msg}))
        sys.exit(1)

    full_text = " ".join(seg["text"] for seg in segments)
    timestamped = "\n".join(
        f"{format_timestamp(seg['start'])} {seg['text']}" for seg in segments
    )

    if args.text_only:
        print(timestamped if args.timestamps else full_text)
        return

    result = {
        "video_id": video_id,
        "segment_count": len(segments),
        "duration": format_timestamp(segments[-1]["start"] + segments[-1]["duration"]) if segments else "0:00",
        "full_text": full_text,
    }
    if args.timestamps:
        result["timestamped_text"] = timestamped

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
