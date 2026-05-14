#!/usr/bin/env python3
"""
RSA CSV Generator

Generates properly formatted CSV files for Google Ads Editor import.
Validates character limits before generating (fails on errors).

Usage:
    python3 .claude/skills/rsa-maker/scripts/generate-csv.py input.json output.csv
    python3 .claude/skills/rsa-maker/scripts/generate-csv.py input.json output.csv --force

Options:
    --force    Generate CSV even if validation fails

Input JSON format:
{
    "campaign": "Campaign Name",
    "ad_group": "Ad Group Name",
    "headlines": [
        {"text": "Headline 1", "position": "1"},
        {"text": "{KeyWord:Default}", "position": "-"},
        ...
    ],
    "descriptions": [
        {"text": "Description 1", "position": "1"},
        ...
    ],
    "path1": "url-path",
    "path2": "segment",
    "final_url": "https://example.com/"
}

Character limits:
- Headlines: 30 chars max
- Descriptions: 90 chars max
- Paths: 15 chars max

Note: {KeyWord:fallback} and {CUSTOMIZER.name:fallback} syntax only counts
the fallback text toward the character limit.
"""

import csv
import json
import re
import sys
import os
from datetime import datetime
from typing import Union, Tuple

# CSV Header - exactly 45 columns
HEADER = [
    "Campaign", "Ad Group", "Ad type", "Labels",
    "Headline 1", "Headline 1 position",
    "Headline 2", "Headline 2 position",
    "Headline 3", "Headline 3 position",
    "Headline 4", "Headline 4 position",
    "Headline 5", "Headline 5 position",
    "Headline 6", "Headline 6 position",
    "Headline 7", "Headline 7 position",
    "Headline 8", "Headline 8 position",
    "Headline 9", "Headline 9 position",
    "Headline 10", "Headline 10 position",
    "Headline 11", "Headline 11 position",
    "Headline 12", "Headline 12 position",
    "Headline 13", "Headline 13 position",
    "Headline 14", "Headline 14 position",
    "Headline 15", "Headline 15 position",
    "Description 1", "Description 1 position",
    "Description 2", "Description 2 position",
    "Description 3", "Description 3 position",
    "Description 4", "Description 4 position",
    "Path 1", "Path 2", "Final URL"
]

# Patterns for dynamic insertion syntax
# Matches: {KeyWord:fallback}, {keyword:fallback}, {CUSTOMIZER.name:fallback}
INSERTION_PATTERN = re.compile(r'\{(KeyWord|keyword|CUSTOMIZER\.[^:}]+):([^}]*)\}')


def get_effective_length(text: str) -> Tuple[int, str]:
    """
    Calculate effective character length for Google Ads.

    For {KeyWord:fallback} or {CUSTOMIZER.name:fallback} syntax,
    only the fallback text counts toward the limit.

    Returns: (effective_length, display_text_for_counting)
    """
    if not text:
        return 0, ""

    # Find all insertion patterns and extract fallback text
    effective_text = text

    def replace_with_fallback(match):
        return match.group(2)  # Return only the fallback text

    effective_text = INSERTION_PATTERN.sub(replace_with_fallback, text)

    return len(effective_text), effective_text


def validate_rsa(data: dict) -> Tuple[list, list]:
    """
    Validate RSA data.

    Returns: (errors, warnings)
    - errors: Issues that prevent CSV generation
    - warnings: Non-blocking issues
    """
    errors = []
    warnings = []

    headlines = data.get("headlines", [])
    descriptions = data.get("descriptions", [])

    # Check headline count
    if len(headlines) < 3:
        errors.append(f"Only {len(headlines)} headlines (minimum 3 required)")
    if len(headlines) > 15:
        errors.append(f"{len(headlines)} headlines (maximum 15 allowed)")

    # Check description count
    if len(descriptions) < 2:
        errors.append(f"Only {len(descriptions)} descriptions (minimum 2 required)")
    if len(descriptions) > 4:
        errors.append(f"{len(descriptions)} descriptions (maximum 4 allowed)")

    # Check headline lengths
    for i, h in enumerate(headlines):
        text = h.get("text", h) if isinstance(h, dict) else h
        eff_len, eff_text = get_effective_length(text)
        if eff_len > 30:
            errors.append(f"Headline {i+1} is {eff_len} chars (max 30): \"{eff_text[:35]}{'...' if len(eff_text) > 35 else ''}\"")

    # Check description lengths
    for i, d in enumerate(descriptions):
        text = d.get("text", d) if isinstance(d, dict) else d
        eff_len, eff_text = get_effective_length(text)
        if eff_len > 90:
            errors.append(f"Description {i+1} is {eff_len} chars (max 90): \"{eff_text[:50]}...\"")

    # Check paths
    path1 = data.get("path1", "")
    path2 = data.get("path2", "")
    if len(path1) > 15:
        errors.append(f"Path 1 is {len(path1)} chars (max 15): \"{path1}\"")
    if len(path2) > 15:
        errors.append(f"Path 2 is {len(path2)} chars (max 15): \"{path2}\"")

    # Check final URL
    final_url = data.get("final_url", "")
    if not final_url:
        errors.append("Final URL is missing")
    elif not final_url.startswith("https://"):
        warnings.append("Final URL should start with https://")

    return errors, warnings


def create_rsa_row(data: dict) -> list:
    """Convert RSA data dict to a properly formatted CSV row."""
    row = [
        data.get("campaign", ""),
        data.get("ad_group", ""),
        "Responsive search ad",
        data.get("labels", ""),
    ]

    # Headlines (15 slots)
    headlines = data.get("headlines", [])
    for i in range(15):
        if i < len(headlines):
            h = headlines[i]
            if isinstance(h, dict):
                row.append(h.get("text", ""))
                row.append(h.get("position", "-"))
            else:
                row.append(h)
                row.append("-")
        else:
            row.append("")
            row.append("")

    # Descriptions (4 slots)
    descriptions = data.get("descriptions", [])
    for i in range(4):
        if i < len(descriptions):
            d = descriptions[i]
            if isinstance(d, dict):
                row.append(d.get("text", ""))
                row.append(d.get("position", "-"))
            else:
                row.append(d)
                row.append("-")
        else:
            row.append("")
            row.append("")

    # Paths and Final URL
    row.append(data.get("path1", ""))
    row.append(data.get("path2", ""))
    row.append(data.get("final_url", ""))

    return row


def generate_csv(data: Union[dict, list], output_path: str = None, force: bool = False) -> Tuple[bool, str]:
    """
    Generate CSV from RSA data (single dict or list of dicts).

    Returns: (success, message_or_path)
    """
    # Normalize to list
    if isinstance(data, dict):
        rsas = [data]
    else:
        rsas = data

    # Validate all RSAs
    all_errors = []
    all_warnings = []

    for i, rsa in enumerate(rsas):
        ad_group = rsa.get("ad_group", f"RSA {i+1}")
        errors, warnings = validate_rsa(rsa)

        if errors:
            all_errors.append(f"\n  {ad_group}:")
            all_errors.extend([f"    - {e}" for e in errors])

        if warnings:
            all_warnings.append(f"\n  {ad_group}:")
            all_warnings.extend([f"    - {w}" for w in warnings])

    # Report warnings
    if all_warnings:
        print("Warnings:", file=sys.stderr)
        print("".join(all_warnings), file=sys.stderr)
        print("", file=sys.stderr)

    # Check for errors
    if all_errors:
        print("VALIDATION FAILED - CSV not generated", file=sys.stderr)
        print("\nErrors:", file=sys.stderr)
        print("".join(all_errors), file=sys.stderr)
        print("", file=sys.stderr)

        if not force:
            print("Fix the errors above or use --force to generate anyway.", file=sys.stderr)
            return False, "Validation failed"
        else:
            print("--force flag used, generating CSV despite errors...", file=sys.stderr)

    # Generate CSV rows
    rows = [HEADER]
    for rsa in rsas:
        rows.append(create_rsa_row(rsa))

    # Output
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"Generated: {output_path} ({len(rsas)} RSA(s))", file=sys.stderr)
        return True, output_path
    else:
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(rows)
        return True, output.getvalue()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse arguments
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv

    input_source = args[0] if args else None
    output_path = args[1] if len(args) > 1 else None

    if not input_source:
        print("Error: Input file required", file=sys.stderr)
        sys.exit(1)

    # Read JSON input
    if input_source == "-":
        data = json.load(sys.stdin)
    else:
        with open(input_source, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # Generate default output path if not specified
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if isinstance(data, dict):
            campaign = data.get("campaign", "rsa")
        else:
            campaign = data[0].get("campaign", "rsa") if data else "rsa"

        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in campaign.lower())
        safe_name = "-".join(filter(None, safe_name.split("-")))[:50]

        output_dir = "created/rsas"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/{timestamp}_{safe_name}.csv"

    success, result = generate_csv(data, output_path, force)

    if not success:
        sys.exit(1)

    if not output_path:
        print(result)


if __name__ == "__main__":
    main()
