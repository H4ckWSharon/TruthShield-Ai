import time
import threading
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse

class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter per client IP."""

    def __init__(self, max_requests: int = 180, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_key: str) -> Tuple[bool, int, int]:
        """Returns (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            q = self._buckets[client_key]
            while q and q[0] <= cutoff:
                q.popleft()

            if len(q) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - q[0])))
                return False, 0, retry_after

            q.append(now)
            remaining = max(0, self.max_requests - len(q))
            return True, remaining, 0

    def reset(self):
        with self._lock:
            self._buckets.clear()

rate_limiter = SlidingWindowRateLimiter()

def extract_client_ip(request: Request) -> str:
    """Extract client IP respecting X-Forwarded-For / X-Real-IP headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

def build_rate_limit_response(limit: int, retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down requests."},
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
        },
    )
