from __future__ import annotations

import os
from pathlib import Path

# --- paths ---
BASE_DIR = Path(__file__).parent.parent
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "data" / "deepparser.db"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))

# --- dp_cli ---
DPCLI_BIN = os.environ.get("DPCLI_BIN", "dp")
DPCLI_FOLDER_ID = os.environ.get("DPCLI_FOLDER_ID", "")  # required for upload
DPCLI_BASE_URL = os.environ.get("DPCLI_BASE_URL", "")
DPCLI_APP_KEY = os.environ.get("DPCLI_APP_KEY", "")

# --- API ---
VERSION = "1.0.0"
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))  # 50 MB
DISK_RESERVE_BYTES = int(os.environ.get("DISK_RESERVE_BYTES", str(100 * 1024 * 1024)))  # 100 MB
PARSE_TIMEOUT_SECS = int(os.environ.get("PARSE_TIMEOUT_SECS", "120"))
SYNC_WAIT_SECS = float(os.environ.get("SYNC_WAIT_SECS", "10"))
SEMAPHORE_SIZE = int(os.environ.get("DP_MAX_CONCURRENT_PARSE", "4"))
SEMAPHORE_TIMEOUT_SECS = float(os.environ.get("SEMAPHORE_TIMEOUT_SECS", "30"))

# --- auth / rate limiting ---
AUTH_FAIL_WINDOW_SECS = 60
AUTH_FAIL_MAX = 10
KEYS_PER_IP_WINDOW_SECS = 3600
KEYS_PER_IP_MAX = 5

# --- admin ---
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# --- trusted proxies ---
# Space-separated list of trusted reverse-proxy CIDRs/IPs whose X-Forwarded-For header
# will be trusted for rate-limiting. Empty by default (trust only client.host).
# Set to the Fly.io private network range when deploying behind Fly.io:
#   TRUSTED_PROXY_CIDRS="fdaa::/16"
# Or for a local nginx: TRUSTED_PROXY_CIDRS="127.0.0.1"
_raw_proxy_cidrs = os.environ.get("TRUSTED_PROXY_CIDRS", "")
TRUSTED_PROXY_CIDRS: frozenset[str] = frozenset(
    c.strip() for c in _raw_proxy_cidrs.split() if c.strip()
)

# --- supported formats ---
SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "doc", "ppt", "pptx",
    "xls", "xlsx", "csv", "txt", "md",
    "jpg", "jpeg", "png",
    "dwg", "dxf",
}
