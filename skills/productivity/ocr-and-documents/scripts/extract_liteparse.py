#!/usr/bin/env python3
"""Extract text from PDFs with LiteParse when the ``lit`` CLI is installed.

LiteParse is optional. This helper uses ``lit parse`` for fast local PDF text
extraction, and falls back to the existing pymupdf helper for plain text when
``lit`` is unavailable.

Usage:
    python extract_liteparse.py document.pdf
    python extract_liteparse.py document.pdf --json
    python extract_liteparse.py document.pdf --pages 1-5,10
    python extract_liteparse.py document.pdf --output output.txt
    python extract_liteparse.py document.pdf --screenshots screenshots/
    python extract_liteparse.py --check
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from shutil import which


def find_liteparse_cli() -> str | None:
    """Return the installed LiteParse CLI path, if available."""
    return which("lit")


def build_parse_command(
    lit_path: str,
    pdf_path: str,
    *,
    output_format: str = "text",
    target_pages: str | None = None,
    output: str | None = None,
    ocr: bool = False,
    ocr_language: str | None = None,
    tessdata_path: str | None = None,
    max_pages: int | None = None,
    dpi: int | None = None,
    password: str | None = None,
) -> list[str]:
    """Build a ``lit parse`` command without executing it."""
    cmd = [
        lit_path,
        "parse",
        pdf_path,
        "--format",
        output_format,
        "--quiet",
    ]

    if not ocr:
        cmd.append("--no-ocr")
    if target_pages:
        cmd.extend(["--target-pages", target_pages])
    if output:
        cmd.extend(["-o", output])
    if ocr_language:
        cmd.extend(["--ocr-language", ocr_language])
    if tessdata_path:
        cmd.extend(["--tessdata-path", tessdata_path])
    if max_pages is not None:
        cmd.extend(["--max-pages", str(max_pages)])
    if dpi is not None:
        cmd.extend(["--dpi", str(dpi)])
    if password:
        cmd.extend(["--password", password])

    return cmd


def build_screenshot_command(
    lit_path: str,
    pdf_path: str,
    output_dir: str,
    *,
    target_pages: str | None = None,
    dpi: int | None = None,
    password: str | None = None,
) -> list[str]:
    """Build a ``lit screenshot`` command without executing it."""
    cmd = [lit_path, "screenshot", pdf_path, "-o", output_dir, "--quiet"]
    if target_pages:
        cmd.extend(["--target-pages", target_pages])
    if dpi is not None:
        cmd.extend(["--dpi", str(dpi)])
    if password:
        cmd.extend(["--password", password])
    return cmd


def _one_based_pages_to_zero_based(page_spec: str) -> str:
    """Translate LiteParse's 1-based page selectors for extract_pymupdf.py."""
    translated: list[str] = []
    for part in page_spec.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start, end = token.split("-", 1)
            translated.append(f"{_page_to_zero_based(start)}-{_page_to_zero_based(end)}")
        else:
            translated.append(_page_to_zero_based(token))
    return ",".join(translated)


def _page_to_zero_based(value: str) -> str:
    page = int(value)
    return str(page - 1 if page > 0 else page)


def run_pymupdf_fallback(pdf_path: str, *, target_pages: str | None, output: str | None) -> int:
    """Run the existing pymupdf helper for plain-text fallback."""
    fallback_script = Path(__file__).with_name("extract_pymupdf.py")
    cmd = [sys.executable, str(fallback_script), pdf_path]
    if target_pages:
        cmd.extend(["--pages", _one_based_pages_to_zero_based(target_pages)])

    print(
        "LiteParse CLI 'lit' was not found; falling back to extract_pymupdf.py.",
        file=sys.stderr,
    )
    if output:
        result = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if result.stdout:
            Path(output).write_text(result.stdout, encoding="utf-8")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        return result.returncode

    return subprocess.run(cmd, check=False).returncode


def run(args: argparse.Namespace) -> int:
    lit_path = find_liteparse_cli()

    if args.check:
        if lit_path:
            print(f"LiteParse CLI available: {lit_path}")
            return 0
        print("LiteParse CLI not found. Install optional package 'liteparse' to enable it.")
        return 1

    if not args.pdf:
        print(__doc__)
        return 2

    if lit_path:
        if args.screenshots:
            Path(args.screenshots).mkdir(parents=True, exist_ok=True)
            cmd = build_screenshot_command(
                lit_path,
                args.pdf,
                args.screenshots,
                target_pages=args.pages,
                dpi=args.dpi,
                password=args.password,
            )
        else:
            cmd = build_parse_command(
                lit_path,
                args.pdf,
                output_format="json" if args.json else "text",
                target_pages=args.pages,
                output=args.output,
                ocr=args.ocr,
                ocr_language=args.ocr_language,
                tessdata_path=args.tessdata_path,
                max_pages=args.max_pages,
                dpi=args.dpi,
                password=args.password,
            )
        return subprocess.run(cmd, check=False).returncode

    if args.screenshots:
        print(
            "LiteParse CLI 'lit' is required for screenshot generation; no fallback was run.",
            file=sys.stderr,
        )
        return 127
    if args.json:
        print(
            "LiteParse CLI 'lit' is required for structured JSON output; no fallback was run.",
            file=sys.stderr,
        )
        return 127

    return run_pymupdf_fallback(args.pdf, target_pages=args.pages, output=args.output)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract PDF text with optional LiteParse fast path.")
    parser.add_argument("pdf", nargs="?", help="PDF path to parse.")
    parser.add_argument("--check", action="store_true", help="Check whether the LiteParse 'lit' CLI is available.")
    parser.add_argument("--json", action="store_true", help="Return LiteParse structured JSON instead of text.")
    parser.add_argument("--pages", help='1-based LiteParse page selector, e.g. "1-5,10,15-20".')
    parser.add_argument("--output", "-o", help="Write parse output to this file.")
    parser.add_argument("--screenshots", metavar="DIR", help="Generate page screenshots into DIR using LiteParse.")
    parser.add_argument("--ocr", action="store_true", help="Enable LiteParse OCR. Default is disabled for speed.")
    parser.add_argument("--ocr-language", help="Tesseract OCR language code, e.g. eng or fra.")
    parser.add_argument("--tessdata-path", help="Directory containing Tesseract .traineddata files.")
    parser.add_argument("--max-pages", type=int, help="Maximum pages to parse.")
    parser.add_argument("--dpi", type=int, help="Rendering DPI for OCR or screenshots.")
    parser.add_argument("--password", help="Password for encrypted PDFs.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run(parse_args(sys.argv[1:])))
