from datetime import timedelta

from app.domain.ports import Clock


class InMemoryRateLimiter:
    """Sliding-window failure counter. Per-process; sufficient for a single-instance deployment."""

    def __init__(self, clock: Clock, max_failures: int, window: timedelta) -> None:
        self._clock = clock
        self._max_failures = max_failures
        self._window = window
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        cutoff = (self._clock.now() - self._window).timestamp()
        recent = [t for t in self._failures.get(key, []) if t > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self._max_failures

    def record_failure(self, key: str) -> None:
        recent = self._recent(key)
        recent.append(self._clock.now().timestamp())
        self._failures[key] = recent

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
