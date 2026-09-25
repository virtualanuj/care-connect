import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.adapters.clock import SystemClock
from app.domain.ports import Clock
from tests.fakes.fixed_clock import FixedClock

START = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)


def is_cutoff_closed(clock: Clock, appointment_start: datetime, cutoff_hours: float) -> bool:
    """Toy cutoff-style rule: reads 'now' only through the injected clock."""
    return appointment_start - clock.now() <= timedelta(hours=cutoff_hours)


def test_fixed_clock_result_changes_only_when_the_clock_is_advanced() -> None:
    clock = FixedClock(START)
    appointment = START + timedelta(hours=3)

    assert not is_cutoff_closed(clock, appointment, cutoff_hours=2)
    assert not is_cutoff_closed(clock, appointment, cutoff_hours=2)

    clock.advance(timedelta(hours=1))

    assert is_cutoff_closed(clock, appointment, cutoff_hours=2)


def test_fixed_clock_can_be_set_to_an_absolute_time() -> None:
    clock = FixedClock(START)

    clock.set(START + timedelta(days=2))

    assert clock.now() == START + timedelta(days=2)


def test_fixed_clock_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone"):
        FixedClock(datetime(2026, 3, 1, 10, 0))


def test_system_clock_returns_timezone_aware_utc_now() -> None:
    now = SystemClock().now()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - now) < timedelta(seconds=5)


def test_services_never_read_the_wall_clock_directly() -> None:
    services = Path(__file__).resolve().parents[2] / "app" / "services"
    offenders = [
        f"{path.name}:{number}"
        for path in services.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if re.search(r"datetime\.(now|utcnow|today)\(|time\.time\(", line)
    ]

    assert offenders == []
