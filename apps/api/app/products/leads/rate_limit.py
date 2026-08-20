"""Lightweight in-memory rate limiter for the machine intake endpoint.

Prevents an attacker from causing unlimited expensive PBKDF2 checks by
tracking failed authentication attempts per source key in a sliding window.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

_WINDOW_SECONDS = 60
_MAX_ATTEMPTS_PER_WINDOW = 20
_CLEANUP_INTERVAL_SECONDS = 300


@dataclass
class _Window:
    attempts: list[float] = field(default_factory=list)
    blocked_until: float = 0.0


class MachineIntakeRateLimiter:
    """Thread-safe sliding-window rate limiter keyed by source identifier."""

    def __init__(self) -> None:
        self._windows: dict[str, _Window] = defaultdict(_Window)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < _CLEANUP_INTERVAL_SECONDS:
            return
        expired: list[str] = []
        for key, window in self._windows.items():
            window.attempts = [t for t in window.attempts if now - t < _WINDOW_SECONDS]
            if not window.attempts and window.blocked_until < now:
                expired.append(key)
        for key in expired:
            del self._windows[key]
        self._last_cleanup = now

    def is_allowed(self, key: str) -> bool:
        """Return True if the request should be allowed, False if rate-limited."""
        now = time.monotonic()
        with self._lock:
            self._cleanup(now)
            window = self._windows[key]
            if window.blocked_until > now:
                return False
            window.attempts = [t for t in window.attempts if now - t < _WINDOW_SECONDS]
            if len(window.attempts) >= _MAX_ATTEMPTS_PER_WINDOW:
                window.blocked_until = now + _WINDOW_SECONDS
                return False
            window.attempts.append(now)
            return True

    def record_success(self, key: str) -> None:
        """Clear the rate-limit state for a key after a successful auth."""
        with self._lock:
            self._windows.pop(key, None)


_machine_intake_limiter = MachineIntakeRateLimiter()


def check_machine_intake_rate(source_key: str) -> None:
    """Raise HTTPException(429) if the source key is rate-limited."""
    from fastapi import HTTPException

    if not _machine_intake_limiter.is_allowed(source_key):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please retry after a short delay.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )


def record_machine_intake_success(source_key: str) -> None:
    """Clear rate-limit state after a successful authentication."""
    _machine_intake_limiter.record_success(source_key)


# Maximum request body size for machine intake: 64 KiB
MAX_MACHINE_INTAKE_BODY_BYTES = 64 * 1024
