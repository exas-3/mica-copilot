"""In-process per-IP rate limiter for the public AI endpoints.

`/chat`, `/chat/sync` and `/classify` each spend Anthropic API credits, so they are
throttled per client IP to cap abuse / cost-runaway. The limiter is a sliding-window
log kept in memory — adequate for the single-process uvicorn deployment behind the
Next.js same-origin proxy. Because the backend only ever sees 127.0.0.1 (the proxy /
Cloudflare tunnel terminate there), the real client IP is read from the forwarded
headers (`CF-Connecting-IP` first, then `X-Forwarded-For`).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings


class SlidingWindowLimiter:
    """Per-key sliding-window log. Thread-safe (sync endpoints run in a threadpool)."""

    def __init__(self, limit: int, window_s: float) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_sweep = 0.0

    def check(self, key: str) -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)``; records the hit when allowed."""
        now = time.monotonic()
        cutoff = now - self.window_s
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self.limit:
                # dq is empty only under a degenerate limit<=0 config; fall back to a full window.
                retry_after = (dq[0] + self.window_s - now) if dq else self.window_s
                return False, max(retry_after, 0.0)
            dq.append(now)
            self._sweep(now, cutoff)
            return True, 0.0

    def _sweep(self, now: float, cutoff: float) -> None:
        # Drop idle keys occasionally so memory doesn't grow with unique client IPs.
        if now - self._last_sweep < 300:
            return
        self._last_sweep = now
        stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
        for k in stale:
            del self._hits[k]


_limiter: SlidingWindowLimiter | None = None


def _get_limiter() -> SlidingWindowLimiter:
    global _limiter
    if _limiter is None:
        s = get_settings()
        _limiter = SlidingWindowLimiter(s.rate_limit_max, s.rate_limit_window_s)
    return _limiter


def client_ip(request: Request) -> str:
    """Resolve the real client IP from the forwarded headers (the socket peer is the proxy)."""
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()  # left-most entry is the original client
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """FastAPI dependency: 429 when the caller's IP exceeds the configured window."""
    s = get_settings()
    if not s.rate_limit_enabled:
        return
    allowed, retry_after = _get_limiter().check(client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded — too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(max(1, int(round(retry_after))))},
        )
