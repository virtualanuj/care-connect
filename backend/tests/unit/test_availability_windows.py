import uuid
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.domain.availability import covers, windows_for_date
from app.domain.models import Availability, AvailabilityException, DayOfWeek, ExceptionType

DOCTOR = uuid.uuid4()
MONDAY = date(2026, 3, 2)
TUESDAY = date(2026, 3, 3)


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


def hm(*pairs: tuple[str, str]) -> list[tuple[time, time]]:
    return [(time.fromisoformat(a), time.fromisoformat(b)) for a, b in pairs]


def test_a_weekly_rule_applies_only_on_its_weekday() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]

    assert windows_for_date(rules, [], MONDAY) == hm(("09:00", "12:00"))
    assert windows_for_date(rules, [], TUESDAY) == []


def test_several_rules_on_one_day_are_sorted_and_adjacent_windows_merge() -> None:
    rules = [
        rule(DayOfWeek.MONDAY, "14:00", "16:00"),
        rule(DayOfWeek.MONDAY, "09:00", "12:00"),
        rule(DayOfWeek.MONDAY, "12:00", "13:00"),
    ]

    assert windows_for_date(rules, [], MONDAY) == hm(("09:00", "13:00"), ("14:00", "16:00"))


def test_a_whole_day_unavailable_exception_removes_everything_even_extra_hours() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]
    exceptions = [
        exception(MONDAY, ExceptionType.EXTRA_HOURS, "13:00", "14:00"),
        exception(MONDAY, ExceptionType.UNAVAILABLE),
    ]

    assert windows_for_date(rules, exceptions, MONDAY) == []


def test_a_partial_unavailable_exception_cuts_a_hole_in_the_window() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]
    exceptions = [exception(MONDAY, ExceptionType.UNAVAILABLE, "10:00", "11:00")]

    assert windows_for_date(rules, exceptions, MONDAY) == hm(("09:00", "10:00"), ("11:00", "12:00"))


def test_extra_hours_add_a_window_even_on_a_day_without_a_rule_and_merge_when_overlapping() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]

    assert windows_for_date(
        [], [exception(TUESDAY, ExceptionType.EXTRA_HOURS, "10:00", "13:00")], TUESDAY
    ) == hm(("10:00", "13:00"))
    assert windows_for_date(
        rules, [exception(MONDAY, ExceptionType.EXTRA_HOURS, "11:00", "14:00")], MONDAY
    ) == hm(("09:00", "14:00"))


def test_exceptions_on_other_dates_are_ignored() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]
    exceptions = [exception(date(2026, 3, 9), ExceptionType.UNAVAILABLE)]

    assert windows_for_date(rules, exceptions, MONDAY) == hm(("09:00", "12:00"))


UTC_ZONE = ZoneInfo("UTC")
KOLKATA = ZoneInfo("Asia/Kolkata")
RULES = [rule(DayOfWeek.MONDAY, "09:00", "12:00")]


def at(hour: int, minute: int = 0, day: int = 2) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def test_an_appointment_inside_a_window_is_covered_including_touching_the_window_end() -> None:
    assert covers(RULES, [], UTC_ZONE, at(9, 30), at(9, 50))
    assert covers(RULES, [], UTC_ZONE, at(11, 40), at(12, 0))
    assert covers(RULES, [], UTC_ZONE, at(9, 0), at(9, 20))


def test_an_appointment_outside_or_straddling_a_window_edge_is_not_covered() -> None:
    assert not covers(RULES, [], UTC_ZONE, at(8, 50), at(9, 10))
    assert not covers(RULES, [], UTC_ZONE, at(11, 50), at(12, 10))
    assert not covers(RULES, [], UTC_ZONE, at(9, 30, day=3), at(9, 50, day=3))


def test_an_appointment_spanning_a_gap_between_two_windows_is_not_covered() -> None:
    rules = [rule(DayOfWeek.MONDAY, "09:00", "10:00"), rule(DayOfWeek.MONDAY, "11:00", "12:00")]

    assert not covers(rules, [], UTC_ZONE, at(9, 50), at(11, 10))


def test_coverage_uses_the_clinic_time_zone_not_utc() -> None:
    # 04:00-04:20 UTC is 09:30-09:50 in Kolkata (UTC+5:30), inside the 09:00-12:00 window.
    assert covers(RULES, [], KOLKATA, at(4, 0), at(4, 20))
    assert not covers(RULES, [], UTC_ZONE, at(4, 0), at(4, 20))


def test_an_appointment_crossing_local_midnight_is_never_covered() -> None:
    rules = [rule(DayOfWeek.MONDAY, "23:00", "23:59")]

    assert not covers(rules, [], UTC_ZONE, at(23, 50), at(0, 10, day=3))


def test_a_whole_day_exception_uncovers_the_appointment() -> None:
    exceptions = [exception(MONDAY, ExceptionType.UNAVAILABLE)]

    assert not covers(RULES, exceptions, UTC_ZONE, at(9, 30), at(9, 50))
