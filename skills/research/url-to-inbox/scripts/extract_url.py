#!/usr/bin/env python3
"""
Extract a URL into plain text + best-effort metadata, ready for
``append_inbox.py``.

Dispatch by source type:

  youtube     → reuse the youtube-content skill's transcript fetcher
                (youtube_transcript_api). Falls back to urllib HTML if the
                package isn't installed.
  twitter / x → fetch the HTML and extract <meta name="description">
                + visible text. (X/Twitter renders threads client-side
                so this is best-effort; for full threads, run this
                through Hermes's xitter skill upstream and pipe the
                resulting text into ``append_inbox.py --text-file -``.)
  blog/other  → urllib + a small HTML→text reducer (stdlib only, no
                BeautifulSoup dep). Strips <script>/<style>, collapses
                whitespace, keeps reasonable line breaks.
  pdf         → not extracted here — feed the text to ``append_inbox.py``
                via the ocr-and-documents skill. This script will print
                a hint and exit 2 if asked.
  email-body  → already-extracted text; pass via ``append_inbox.py
                --text-file <body.txt>`` directly.

Usage:
    python extract_url.py --url <URL> [--source-type auto|...]
                          [--out-json /tmp/x.json]

Output JSON:
    {
      "url": "...",
      "source_type": "youtube"|"blog"|"twitter"|"pdf"|"other",
      "title": "...",
      "author": "...",
      "extracted_text": "..."
    }

Exit codes: 0 success, 1 network/parse error, 2 unsupported source type.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


USER_AGENT = (
    "Mozilla/5.0 (Hermes url-to-inbox skill; +https://github.com/wjlgatech/neuro-os)"
)
HTTP_TIMEOUT = 20


# --------------------------------------------------------------------------
# Source-type detection
# --------------------------------------------------------------------------


_YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "m.youtube.com", "www.youtube.com")
_TWITTER_HOSTS = ("twitter.com", "x.com", "mobile.twitter.com")


def detect_source_type(url: str) -> str:
    host = ""
    m = re.match(r"https?://([^/]+)", url)
    if m:
        host = m.group(1).lower()
    if any(host == h or host.endswith("." + h) for h in _YOUTUBE_HOSTS):
        return "youtube"
    if any(host == h or host.endswith("." + h) for h in _TWITTER_HOSTS):
        return "twitter"
    if url.lower().split("?", 1)[0].endswith(".pdf"):
        return "pdf"
    return "blog"


# --------------------------------------------------------------------------
# HTML reducer (stdlib only)
# --------------------------------------------------------------------------


_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_AUTHOR_RE = re.compile(
    r"<meta[^>]+(?:name|property)=[\"'](?:author|article:author)[\"'][^>]*content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_META_DESC_RE = re.compile(
    r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description|twitter:description)[\"'][^>]*content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_OG_TITLE_RE = re.compile(
    r"<meta[^>]+property=[\"']og:title[\"'][^>]*content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
    "&#39;": "'", "&nbsp;": " ", "&apos;": "'",
}


def _decode_entities(s: str) -> str:
    for k, v in _HTML_ENTITIES.items():
        s = s.replace(k, v)
    # Numeric entities like &#1234; or &#xABCD;
    def _num(match: re.Match) -> str:
        code = match.group(1)
        try:
            if code.lower().startswith("x"):
                return chr(int(code[1:], 16))
            return chr(int(code))
        except ValueError:
            return match.group(0)
    return re.sub(r"&#(x?[0-9a-fA-F]+);", _num, s)


def html_to_text(html: str) -> str:
    cleaned = _SCRIPT_RE.sub(" ", html)
    cleaned = _STYLE_RE.sub(" ", cleaned)
    # Keep paragraph + line breaks visible:
    cleaned = re.sub(r"</(p|div|li|h[1-6]|br)\s*>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = _decode_entities(cleaned)
    # Collapse 3+ blank lines → 2, trim trailing space per line.
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def html_title(html: str) -> Optional[str]:
    m = _OG_TITLE_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    m = _TITLE_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    return None


def html_author(html: str) -> Optional[str]:
    m = _META_AUTHOR_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    return None


def html_description(html: str) -> Optional[str]:
    m = _META_DESC_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    return None


# --------------------------------------------------------------------------
# Fetchers
# --------------------------------------------------------------------------


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read()
    return raw.decode(charset, errors="replace")


def extract_youtube(url: str) -> dict:
    """Fetch a YouTube transcript using youtube_transcript_api when
    available; fall back to the page's <title> + description when not."""
    try:
        # Lazy import — only required for the YouTube branch.
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except ImportError:
        YouTubeTranscriptApi = None  # type: ignore[assignment]

    video_id = _youtube_video_id(url) or url
    title: Optional[str] = None
    author: Optional[str] = None

    # Page metadata first — title/author are useful even when transcript fetch fails.
    try:
        html = fetch_html(f"https://www.youtube.com/watch?v={video_id}")
        title = html_title(html)
        # YouTube exposes channel name via various og: tags; cheap heuristic:
        m = re.search(r'"author":"([^"]+)"', html)
        if m:
            author = m.group(1)
    except Exception:
        pass

    if YouTubeTranscriptApi is None:
        # No transcript library — best we can do is description + title.
        try:
            desc = html_description(html or "") if html else None  # type: ignore[has-type]
        except Exception:
            desc = None
        return {
            "title": title or f"YouTube video {video_id}",
            "author": author or "unknown",
            "extracted_text": (desc or "")
                + "\n\n(youtube-transcript-api not installed; install via "
                  "`pip install youtube-transcript-api` for full transcript)",
        }

    try:
        # Try a small set of common languages; first hit wins.
        for lang in ("en", "en-US", "en-GB"):
            try:
                segs = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                text = "\n".join(s["text"] for s in segs if s.get("text"))
                return {
                    "title": title or f"YouTube video {video_id}",
                    "author": author or "unknown",
                    "extracted_text": text or "(empty transcript)",
                }
            except Exception:
                continue
        # Last resort: any available language.
        segs = YouTubeTranscriptApi.get_transcript(video_id)
        text = "\n".join(s["text"] for s in segs if s.get("text"))
        return {
            "title": title or f"YouTube video {video_id}",
            "author": author or "unknown",
            "extracted_text": text or "(empty transcript)",
        }
    except Exception as e:
        return {
            "title": title or f"YouTube video {video_id}",
            "author": author or "unknown",
            "extracted_text": (
                f"(transcript fetch failed: {e}; description fallback follows)\n\n"
                + (html_description(html) if html else "")  # type: ignore[has-type]
            ),
        }


def _youtube_video_id(url_or_id: str) -> Optional[str]:
    s = url_or_id.strip()
    for pat in (
        r"(?:v=|youtu\.be/|shorts/|embed/|live/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ):
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None


def extract_blog(url: str) -> dict:
    html = fetch_html(url)
    return {
        "title": html_title(html) or url,
        "author": html_author(html) or "unknown",
        "extracted_text": html_to_text(html),
    }


def extract_twitter(url: str) -> dict:
    """X/Twitter is client-rendered, so this scraper is best-effort.
    Returns whatever the static HTML contains plus a hint to the user."""
    try:
        html = fetch_html(url)
    except urllib.error.URLError as e:
        return {
            "title": url,
            "author": "unknown",
            "extracted_text": (
                f"(twitter fetch failed: {e}; the X/Twitter HTML is "
                "client-rendered. For full threads, run the xitter "
                "skill upstream and pipe its output to append_inbox.py.)"
            ),
        }
    desc = html_description(html) or ""
    title = html_title(html) or url
    return {
        "title": title,
        "author": "unknown",
        "extracted_text": desc + (
            "\n\n(X/Twitter renders threads client-side; for full thread "
            "text, prefer Hermes's xitter skill upstream.)"
        ),
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def extract(url: str, *, source_type: str = "auto") -> dict:
    if source_type == "auto":
        source_type = detect_source_type(url)

    if source_type == "youtube":
        payload = extract_youtube(url)
    elif source_type == "twitter":
        payload = extract_twitter(url)
    elif source_type == "blog" or source_type == "other":
        payload = extract_blog(url)
    elif source_type == "pdf":
        raise ValueError(
            "PDF extraction is out of scope for this skill — feed the "
            "text through the ocr-and-documents skill, then pipe the "
            "output to append_inbox.py with --source-type pdf."
        )
    elif source_type == "email-body":
        raise ValueError(
            "email-body inputs are already-extracted text — call "
            "append_inbox.py directly with --source-type email-body."
        )
    else:
        raise ValueError(f"unsupported source_type {source_type!r}")

    payload["url"] = url
    payload["source_type"] = source_type
    return payload


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a URL into plain text + metadata for the neuro-os inbox.",
    )
    parser.add_argument("--url", required=True, help="URL to extract")
    parser.add_argument(
        "--source-type", default="auto",
        choices=["auto", "youtube", "blog", "twitter", "pdf", "email-body", "other"],
        help="Source type; 'auto' (default) detects from URL host",
    )
    parser.add_argument(
        "--out-json", default=None,
        help="If set, write the JSON to this file instead of stdout",
    )
    args = parser.parse_args(argv)

    try:
        payload = extract(args.url, source_type=args.source_type)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print(f"error: fetch failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    out = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out_json:
        Path(args.out_json).expanduser().write_text(out, encoding="utf-8")
        print(args.out_json)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
