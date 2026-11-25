"""In-process token-bucket rate limiter.

Per gateway replica. In AWS the same protection is layered at the edge with an AWS WAF rate-based
rule on the ALB/CloudFront, so a fleet of replicas does not multiply the effective limit for abusers.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    def __init__(
        self,
        per_minute: int,
        *,
        burst: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 50_000,
    ) -> None:
        self.capacity = float(burst or per_minute)
        self.rate = per_minute / 60.0
        self._clock = clock
        self._buckets: dict[str, Bucket] = {}
        self._max_keys = max_keys

    def check(self, key: str) -> tuple[bool, int, float]:
        """Consume one token → (allowed, remaining, retry_after_seconds)."""
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max_keys:
                self._evict(now)
            bucket = self._buckets[key] = Bucket(self.capacity, now)
        bucket.tokens = min(self.capacity, bucket.tokens + (now - bucket.updated) * self.rate)
        bucket.updated = now
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return True, int(bucket.tokens), 0.0
        return False, 0, (1 - bucket.tokens) / self.rate

    def _evict(self, now: float) -> None:
        full_after = self.capacity / self.rate
        stale = [k for k, b in self._buckets.items() if now - b.updated > full_after]
        for key in stale or list(self._buckets)[: len(self._buckets) // 10]:
            self._buckets.pop(key, None)
