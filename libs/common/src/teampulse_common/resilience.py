"""Circuit breaker + retry with exponential backoff and full jitter."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum

logger = logging.getLogger("teampulse.resilience")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    def __init__(self, name: str, retry_after: float) -> None:
        super().__init__(f"circuit '{name}' is open; retry in {retry_after:.1f}s")
        self.name = name
        self.retry_after = retry_after


class CircuitBreaker:
    """CLOSED → (``failure_threshold`` consecutive failures) → OPEN → (``recovery_timeout``) →
    HALF_OPEN → one trial call: success closes the circuit, failure re-opens it."""

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN and self._clock() - self._opened_at >= self.recovery_timeout:
            self._transition(CircuitState.HALF_OPEN)
        return self._state

    def _transition(self, new: CircuitState) -> None:
        if new is self._state:
            return
        logger.warning("circuit.state_changed", extra={"circuit": self.name, "from": self._state, "to": new})
        self._state = new
        if new is CircuitState.OPEN:
            self._opened_at = self._clock()
        if new is CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        if new is CircuitState.CLOSED:
            self._failures = 0

    def before_call(self) -> None:
        state = self.state
        if state is CircuitState.OPEN:
            raise CircuitOpenError(self.name, self.recovery_timeout - (self._clock() - self._opened_at))
        if state is CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitOpenError(self.name, 1.0)
            self._half_open_calls += 1

    def record_success(self) -> None:
        self._failures = 0
        if self._state is not CircuitState.CLOSED:
            self._transition(CircuitState.CLOSED)

    def record_failure(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._transition(CircuitState.OPEN)

    async def call[T](self, fn: Callable[[], Awaitable[T]]) -> T:
        self.before_call()
        try:
            result = await fn()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result


async def retry_async[T](
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except retry_on:
            if attempt == attempts:
                raise
            delay = random.uniform(0, min(max_delay, base_delay * 2 ** (attempt - 1)))  # noqa: S311 - jitter
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
