import time
import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class RateLimiter:
    \"\"\"
    A simple thread-safe rate limiter to prevent IP bans and respect API limits.
    \"\"\"
    _instances: Dict[str, 'RateLimiter'] = {}
    _lock = threading.Lock()

    def __init__(self, name: str, requests_per_second: float):
        self.name = name
        self.interval = 1.0 / requests_per_second
        self.last_call = 0.0
        self.call_lock = threading.Lock()

    @classmethod
    def get_limiter(cls, name: str, requests_per_second: float) -> 'RateLimiter':
        with cls._lock:
            if name not in cls._instances:
                cls._instances[name] = cls(name, requests_per_second)
            return cls._instances[name]

    def wait(self):
        \"\"\"Wait for the required interval before the next call.\"\"\"
        with self.call_lock:
            elapsed = time.monotonic() - self.last_call
            if elapsed < self.interval:
                sleep_time = self.interval - elapsed
                logger.debug(\"Rate limiting %s: sleeping for %.2f seconds\", self.name, sleep_time)
                time.sleep(sleep_time)
            self.last_call = time.monotonic()

def rate_limit(name: str, requests_per_second: float):
    \"\"\"
    Decorator to apply rate limiting to a function.
    Usage:
        @rate_limit(\"arxiv\", 0.33)  # ~1 req / 3 seconds
        def fetch_arxiv(query):
            ...
    \"\"\"
    limiter = RateLimiter.get_limiter(name, requests_per_second)
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            limiter.wait()
            return func(*args, **kwargs)
        return wrapper
    return decorator
