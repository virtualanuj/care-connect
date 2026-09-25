import uuid
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.domain.models import Availability, AvailabilityException, DayOfWeek, ExceptionType
from app.domain.slots import generate_day_slots

DOCTOR = uuid.uuid4()
MONDAY = date(2026, 3, 2)
UTC_ZONE = ZoneInfo("UTC")


def rule(day: DayOfWeek, start: str, end: str) -> Availability:
    return Availability(
        uuid.uuid4(), DOCTOR, day, time.fromisoformat(start), time.fromisoformat(end)
    )


def exception(
    on: date, kind: ExceptionType, start: str | None = None, end: str | None = None
) -> AvailabilityException:
    return AvailabilityException(
        uuid.uuid4(),
        DOCTOR,
        on,
        kind,
        time.fromisoformat(start) if start else None,
        time.fromisoformat(end) if end else None,
    )


def starts(slots) -> list[str]:  # type: ignore[no-untyped-def]
    return [s.start_time.strftime("%H:%M") for s in slots]


def test_a_one_hour_window_with_20_minute_slots_yields_exactly_three_slots() -> None:
    slots = generate_day_slots([rule(DayOfWeek.MONDAY, "09:00", "10:00")], [], MONDAY, 20, UTC_ZONE)

    assert starts(slots) == ["09:00", "09:20", "09:40"]
    assert slots[-1].end_time == datetime(2026, 3, 2, 10, 0, tzinfo=UTC)


def test_a_remainder_shorter_than_a_slot_is_dropped() -> None:
    slots = generate_day_slots([rule(DayOfWeek.MONDAY, "09:00", "09:50")], [], MONDAY, 20, UTC_ZONE)

    assert starts(slots) == ["09:00", "09:20"]


def test_the_slot_grid_starts_at_the_window_start_not_on_the_hour() -> None:
    slots = generate_day_slots([rule(DayOfWeek.MONDAY, "09:10", "10:10")], [], MONDAY, 20, UTC_ZONE)

    assert starts(slots) == ["09:10", "09:30", "09:50"]


def test_slots_are_sorted_and_each_window_gets_its_own_grid() -> None:
    rules = [rule(DayOfWeek.MONDAY, "14:00", "15:00"), rule(DayOfWeek.MONDAY, "09:00", "10:00")]

    slots = generate_day_slots(rules, [], MONDAY, 30, UTC_ZONE)

    assert starts(slots) == ["09:00", "09:30", "14:00", "14:30"]


def test_no_slots_on_days_without_a_rule() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]

    assert generate_day_slots(rules, [], date(2026, 3, 3), 20, UTC_ZONE) == []


def test_a_whole_day_unavailable_exception_removes_every_slot() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]

    slots = generate_day_slots(
        rules, [exception(MONDAY, ExceptionType.UNAVAILABLE)], MONDAY, 20, UTC_ZONE
    )

    assert slots == []


def test_a_partial_unavailable_exception_removes_only_the_covered_slots() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]
    exceptions = [exception(MONDAY, ExceptionType.UNAVAILABLE, "10:00", "11:00")]

    slots = generate_day_slots(rules, exceptions, MONDAY, 20, UTC_ZONE)

    assert starts(slots) == ["09:00", "09:20", "09:40", "11:00", "11:20", "11:40"]


def test_extra_hours_create_slots_on_a_day_without_a_rule() -> None:
    exceptions = [exception(date(2026, 3, 7), ExceptionType.EXTRA_HOURS, "10:00", "11:00")]

    slots = generate_day_slots([], exceptions, date(2026, 3, 7), 20, UTC_ZONE)

    assert starts(slots) == ["10:00", "10:20", "10:40"]


def test_window_times_are_clinic_local_and_slots_are_returned_in_utc() -> None:
    kolkata = ZoneInfo("Asia/Kolkata")  # UTC+05:30, no DST

    slots = generate_day_slots([rule(DayOfWeek.MONDAY, "09:00", "10:00")], [], MONDAY, 30, kolkata)

    assert [s.start_time for s in slots] == [
        datetime(2026, 3, 2, 3, 30, tzinfo=UTC),
        datetime(2026, 3, 2, 4, 0, tzinfo=UTC),
    ]
    assert all(s.start_time.tzinfo is not None for s in slots)


def test_spring_forward_day_has_only_the_real_hours_of_the_window() -> None:
    # New York 2026-03-08: clocks jump 02:00 -> 03:00, so 01:00-04:00 local is 2 real hours.
    ny = ZoneInfo("America/New_York")
    sunday = date(2026, 3, 8)

    slots = generate_day_slots([rule(DayOfWeek.SUNDAY, "01:00", "04:00")], [], sunday, 30, ny)

    assert len(slots) == 4
    assert slots[0].start_time == datetime(2026, 3, 8, 6, 0, tzinfo=UTC)  # 01:00 EST
    assert slots[-1].end_time == datetime(2026, 3, 8, 8, 0, tzinfo=UTC)  # 04:00 EDT
    local_hours = {s.start_time.astimezone(ny).hour for s in slots}
    assert 2 not in local_hours  # the skipped hour never appears


def test_fall_back_day_has_the_extra_real_hour_of_the_window() -> None:
    # New York 2026-11-01: clocks repeat 01:00-02:00, so 00:00-03:00 local is 4 real hours.
    ny = ZoneInfo("America/New_York")
    sunday = date(2026, 11, 1)

    slots = generate_day_slots([rule(DayOfWeek.SUNDAY, "00:00", "03:00")], [], sunday, 30, ny)

    assert len(slots) == 8
    assert slots[0].start_time == datetime(2026, 11, 1, 4, 0, tzinfo=UTC)  # 00:00 EDT
    assert slots[-1].end_time == datetime(2026, 11, 1, 8, 0, tzinfo=UTC)  # 03:00 EST
    assert len({s.start_time for s in slots}) == 8  # no duplicated instants


def test_slots_never_overlap_and_are_contiguous_within_a_window() -> None:
    slots = generate_day_slots([rule(DayOfWeek.MONDAY, "08:00", "17:00")], [], MONDAY, 25, UTC_ZONE)

    for earlier, later in zip(slots, slots[1:], strict=False):
        assert earlier.end_time <= later.start_time
    assert all((s.end_time - s.start_time).total_seconds() == 25 * 60 for s in slots)


@pytest.mark.parametrize("bad", [0, -5])
def test_a_non_positive_slot_length_is_rejected(bad: int) -> None:
    with pytest.raises(ValueError):
        generate_day_slots([rule(DayOfWeek.MONDAY, "09:00", "10:00")], [], MONDAY, bad, UTC_ZONE)
