from datetime import datetime, timedelta


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("FixedClock requires a timezone-aware datetime")
    return value


class FixedClock:
    """Test clock: time only moves when the test moves it."""

    def __init__(self, start: datetime) -> None:
        self._now = _require_aware(start)

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        self._now = _require_aware(value)

    def advance(self, delta: timedelta) -> None:
        self._now += delta
