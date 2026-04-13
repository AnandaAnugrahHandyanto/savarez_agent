"""``hermes debug`` — debug tools for Hermes Agent.

Currently supports:
    hermes debug share    Upload debug report (system info + logs) to a
                          paste service and print a shareable URL.
"""

import io
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from hermes_constants import get_hermes_home, display_hermes_home


# ---------------------------------------------------------------------------
# Paste services — try paste.rs first, dpaste.com as fallback.
# ---------------------------------------------------------------------------

_PASTE_RS_URL = "https://paste.rs/"
_DPASTE_COM_URL = "https://dpaste.com/api/"

# Map user-facing "expire days" to dpaste.com's expiry_days parameter.
# paste.rs doesn't support expiry — pastes persist indefinitely.


def _upload_paste_rs(content: str) -> str:
    """Upload to paste.rs.  Returns the paste URL.

    paste.rs accepts a plain POST body and returns the URL directly.
    """
    data = content.encode("utf-8")
    req = urllib.request.Request(
        _PASTE_RS_URL, data=data, method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "User-Agent": "hermes-agent/debug-share",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        url = resp.read().decode("utf-8").strip()
    if not url.startswith("http"):
        raise ValueError(f"Unexpected response from paste.rs: {url[:200]}")
    return url


def _upload_dpaste_com(content: str, expiry_days: int = 7) -> str:
    """Upload to dpaste.com.  Returns the paste URL.

    dpaste.com uses multipart form data.
    """
    boundary = "----HermesDebugBoundary9f3c"

    def _field(name: str, value: str) -> str:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"\r\n"
            f"{value}\r\n"
        )

    body = (
        _field("content", content)
        + _field("syntax", "text")
        + _field("expiry_days", str(expiry_days))
        + f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        _DPASTE_COM_URL, data=body, method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "hermes-agent/debug-share",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        url = resp.read().decode("utf-8").strip()
    if not url.startswith("http"):
        raise ValueError(f"Unexpected response from dpaste.com: {url[:200]}")
    return url


def upload_to_pastebin(content: str, expiry_days: int = 7) -> str:
    """Upload *content* to a paste service, trying paste.rs then dpaste.com.

    Returns the paste URL on success, raises on total failure.
    """
    errors: list[str] = []

    # Try paste.rs first (simple, fast)
    try:
        return _upload_paste_rs(content)
    except Exception as exc:
        errors.append(f"paste.rs: {exc}")

    # Fallback: dpaste.com (supports expiry)
    try:
        return _upload_dpaste_com(content, expiry_days=expiry_days)
    except Exception as exc:
        errors.append(f"dpaste.com: {exc}")

    raise RuntimeError(
        "Failed to upload to any paste service:\n  " + "\n  ".join(errors)
    )


# ---------------------------------------------------------------------------
# Debug report collection
# ---------------------------------------------------------------------------

def _read_log_tail(log_name: str, num_lines: int) -> str:
    """Read the last *num_lines* from a log file, or return a placeholder."""
    from hermes_cli.logs import LOG_FILES, _read_last_n_lines

    filename = LOG_FILES.get(log_name)
    if not filename:
        return f"(unknown log: {log_name})"

    log_path = get_hermes_home() / "logs" / filename
    if not log_path.exists():
        return "(file not found)"

    try:
        lines = _read_last_n_lines(log_path, num_lines)
        return "".join(lines).rstrip("\n")
    except Exception as exc:
        return f"(error reading: {exc})"


def collect_debug_report(*, log_lines: int = 200) -> str:
    """Build a full debug report: system dump + recent logs.

    Returns the report as a plain-text string ready for upload.
    """
    buf = io.StringIO()

    # ── System dump ──────────────────────────────────────────────────────
    # Re-use the dump module's logic by capturing its output.
    from hermes_cli.dump import run_dump

    class _FakeArgs:
        show_keys = False

    old_stdout = sys.stdout
    sys.stdout = capture = io.StringIO()
    try:
        run_dump(_FakeArgs())
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    buf.write(capture.getvalue())

    # ── Recent logs ──────────────────────────────────────────────────────
    buf.write("\n\n")
    buf.write(f"--- agent.log (last {log_lines} lines) ---\n")
    buf.write(_read_log_tail("agent", log_lines))
    buf.write("\n\n")

    errors_lines = min(log_lines, 100)
    buf.write(f"--- errors.log (last {errors_lines} lines) ---\n")
    buf.write(_read_log_tail("errors", errors_lines))
    buf.write("\n\n")

    buf.write(f"--- gateway.log (last {errors_lines} lines) ---\n")
    buf.write(_read_log_tail("gateway", errors_lines))
    buf.write("\n")

    return buf.getvalue()


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def run_debug_share(args):
    """Collect debug report, upload to paste service, print URL."""
    log_lines = getattr(args, "lines", 200)
    expiry = getattr(args, "expire", 7)
    local_only = getattr(args, "local", False)

    print("Collecting debug report...")
    report = collect_debug_report(log_lines=log_lines)

    if local_only:
        print(report)
        return

    print("Uploading...")
    try:
        url = upload_to_pastebin(report, expiry_days=expiry)
        print(f"\nDebug report uploaded:")
        print(f"  {url}")
        print(f"\nShare this link with the Hermes team for support.")
    except RuntimeError as exc:
        print(f"\nUpload failed: {exc}", file=sys.stderr)
        print("\nFull report printed below — copy-paste it manually:\n")
        print(report)
        sys.exit(1)


def run_debug(args):
    """Route debug subcommands."""
    subcmd = getattr(args, "debug_command", None)
    if subcmd == "share":
        run_debug_share(args)
    else:
        # Default: show help
        print("Usage: hermes debug share [--lines N] [--expire N] [--local]")
        print()
        print("Commands:")
        print("  share    Upload debug report to a paste service and print URL")
        print()
        print("Options:")
        print("  --lines N    Number of log lines to include (default: 200)")
        print("  --expire N   Paste expiry in days (default: 7)")
        print("  --local      Print report locally instead of uploading")
