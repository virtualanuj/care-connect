from datetime import UTC, datetime, timedelta

from app.adapters.rate_limiter import InMemoryRateLimiter
from tests.fakes.fixed_clock import FixedClock

START = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def make() -> tuple[InMemoryRateLimiter, FixedClock]:
    clock = FixedClock(START)
    return InMemoryRateLimiter(clock, max_failures=5, window=timedelta(minutes=15)), clock


def test_key_is_blocked_after_five_failures_within_the_window() -> None:
    limiter, _ = make()

    for _ in range(4):
        limiter.record_failure("k")
    assert not limiter.is_blocked("k")

    limiter.record_failure("k")
    assert limiter.is_blocked("k")


def test_keys_are_independent() -> None:
    limiter, _ = make()
    for _ in range(5):
        limiter.record_failure("a")

    assert limiter.is_blocked("a")
    assert not limiter.is_blocked("b")


def test_block_lifts_once_the_failures_age_out_of_the_window() -> None:
    limiter, clock = make()
    for _ in range(5):
        limiter.record_failure("k")

    clock.advance(timedelta(minutes=15, seconds=1))

    assert not limiter.is_blocked("k")


def test_reset_clears_failures() -> None:
    limiter, _ = make()
    for _ in range(5):
        limiter.record_failure("k")

    limiter.reset("k")

    assert not limiter.is_blocked("k")
