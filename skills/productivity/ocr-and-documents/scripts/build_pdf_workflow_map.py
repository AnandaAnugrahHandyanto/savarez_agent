#!/usr/bin/env python3
"""Generate a small PDF workflow map for Hermes document handling."""

from __future__ import annotations

import json
from pathlib import Path


def build_payload() -> dict:
    return {
        "purpose": "Hermes PDF workflow map",
        "entrypoints": [
            {
                "need": "remote_pdf_or_url",
                "tool_or_skill": "web_extract / ocr-and-documents",
                "why": "URL first; avoids local setup when remote extraction works.",
            },
            {
                "need": "local_text_pdf_extract_search_split_merge",
                "tool_or_skill": "ocr-and-documents + pymupdf",
                "why": "Fast default for text-based PDFs and structural operations.",
            },
            {
                "need": "scanned_pdf_ocr_or_complex_layout",
                "tool_or_skill": "ocr-and-documents + marker-pdf",
                "why": "Higher-quality OCR/layout recovery for scanned or complex documents.",
            },
            {
                "need": "targeted_text_edits_on_known_page",
                "tool_or_skill": "nano-pdf",
                "why": "Natural-language edits for specific page-localized PDF changes.",
            },
        ],
        "gaps": [
            "watermarking",
            "forms filling",
            "page rotation cleanup",
            "annotation extraction",
            "signing",
            "batch normalization/compression",
        ],
        "acceptance": [
            "Confirm CLI/runtime presence before claiming a path is usable.",
            "For extraction paths, verify output exists and is non-empty.",
            "For nano-pdf edits, verify edited PDF can be reopened and file size changed or target text changed.",
        ],
    }


def main() -> int:
    output = Path("/tmp/hermes_pdf_workflow_map.json")
    payload = build_payload()
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output), "entrypoint_count": len(payload["entrypoints"]), "gap_count": len(payload["gaps"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
