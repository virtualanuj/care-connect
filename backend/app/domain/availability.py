"""Pure availability logic: which clinic-local windows is a doctor working on a given date?

Reused by slot generation (M3). Times are clinic-local wall times; callers pass the clinic zone
when converting appointment instants.
"""

from collections.abc import Sequence
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.domain.models import (
    Availability,
    AvailabilityException,
    DayOfWeek,
    ExceptionType,
)

Window = tuple[time, time]


def _merge(windows: list[Window]) -> list[Window]:
    merged: list[Window] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _subtract(windows: list[Window], cut_start: time, cut_end: time) -> list[Window]:
    result: list[Window] = []
    for start, end in windows:
        if cut_end <= start or cut_start >= end:
            result.append((start, end))
            continue
        if start < cut_start:
            result.append((start, cut_start))
        if cut_end < end:
            result.append((cut_end, end))
    return result


def windows_for_date(
    rules: Sequence[Availability], exceptions: Sequence[AvailabilityException], day: date
) -> list[Window]:
    """Working windows for `day`: weekly rules plus extra hours, minus unavailable time."""
    todays = [e for e in exceptions if e.date == day]
    if any(e.type == ExceptionType.UNAVAILABLE and e.start_time is None for e in todays):
        return []

    weekday = DayOfWeek.from_date(day)
    windows = [(r.start_time, r.end_time) for r in rules if r.day_of_week == weekday]
    for e in todays:
        if e.type == ExceptionType.EXTRA_HOURS and e.start_time and e.end_time:
            windows.append((e.start_time, e.end_time))
    windows = _merge(windows)
    for e in todays:
        if e.type == ExceptionType.UNAVAILABLE and e.start_time and e.end_time:
            windows = _subtract(windows, e.start_time, e.end_time)
    return windows


def covers(
    rules: Sequence[Availability],
    exceptions: Sequence[AvailabilityException],
    zone: ZoneInfo,
    start: datetime,
    end: datetime,
) -> bool:
    """True if [start, end] lies entirely inside one working window on a single local day."""
    local_start = start.astimezone(zone)
    local_end = end.astimezone(zone)
    if local_start.date() != local_end.date():
        return False
    return any(
        window_start <= local_start.time() and local_end.time() <= window_end
        for window_start, window_end in windows_for_date(rules, exceptions, local_start.date())
    )
