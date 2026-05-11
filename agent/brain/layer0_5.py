"""Layer 0.5: Fingerprint Cache — SHA256 exact-match cache for routing decisions.

Normalizes input (lowercase, collapse whitespace) before hashing so that
"  Hello   World  " matches "hello world".  LRU eviction with TTL expiry.
Thread-safe for concurrent session access.
"""

import hashlib
import re
import threading
import time
from typing import Optional

from agent.brain.types import RouteDecision


def _normalize(text: str) -> str:
    """Normalize text for fingerprinting: lowercase, collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _fingerprint(text: str) -> str:
    """SHA256 fingerprint of normalized text."""
    return hashlib.sha256(_normalize(text).encode('utf-8')).hexdigest()


class FingerprintCache:
    """LRU cache keyed by SHA256 of normalized input.  Thread-safe.

    Attributes:
        max_entries: Maximum cache size before LRU eviction.
        ttl: Time-to-live in seconds. <=0 means no expiry.
    """

    def __init__(self, max_entries: int = 1000, ttl: int = 3600):
        self._max = max_entries
        self._ttl = ttl
        # fp → (RouteDecision, stored_at, last_access)
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, text: str) -> Optional[RouteDecision]:
        """Look up a cached routing decision. Returns None on miss or expiry."""
        fp = _fingerprint(text)
        with self._lock:
            entry = self._data.get(fp)
            if entry is None:
                return None
            decision, stored_at, _ = entry
            # Check TTL: 0 means no expiry. Positive means expire after elapsed > ttl.
            # Use a tiny value (e.g. 0.01) for instant-expiry testing.
            if self._ttl > 0 and time.time() - stored_at > self._ttl:
                del self._data[fp]
                return None
            # Update access time for LRU tracking
            self._data[fp] = (decision, stored_at, time.time())
            return decision

    def set(self, text: str, decision: RouteDecision):
        """Cache a routing decision, evicting LRU entry if at capacity."""
        fp = _fingerprint(text)
        now = time.time()
        with self._lock:
            # Evict oldest-accessed if at capacity and inserting new key
            if len(self._data) >= self._max and fp not in self._data:
                oldest_fp = min(self._data, key=lambda k: self._data[k][2])
                del self._data[oldest_fp]
            self._data[fp] = (decision, now, now)

    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
