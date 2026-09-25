"""Pure slot logic: build a doctor's bookable slots for one clinic-local day.

Two steps, both free of I/O so they are easy to test:

1. `generate_day_slots` - turn availability windows into a fixed-length grid (UTC instants).
2. `plan_day` - hold back the last N slots for emergencies, remove booked and past slots, and
   release unclaimed held slots shortly before they start.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.availability import windows_for_date
from app.domain.models import Availability, AvailabilityException

# An unbooked emergency-held slot becomes regular this long before it starts.
DEFAULT_RELEASE_MINUTES = 60


@dataclass(frozen=True)
class TimeSlot:
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class DaySlot:
    start_time: datetime
    end_time: datetime
    is_emergency: bool


def generate_day_slots(
    rules: Sequence[Availability],
    exceptions: Sequence[AvailabilityException],
    day: date,
    slot_minutes: int,
    zone: ZoneInfo,
) -> list[TimeSlot]:
    """The full slot grid for `day` (a clinic-local date), sorted, in UTC.

    Each working window gets its own grid starting at the window start; only slots that fit
    completely inside the window are kept. Slot length is a real duration, so on a DST-change
    day a window has more or fewer slots than its wall-clock span suggests.
    """
    if slot_minutes <= 0:
        raise ValueError("slot_minutes must be positive")
    length = timedelta(minutes=slot_minutes)
    slots: list[TimeSlot] = []
    for window_start, window_end in windows_for_date(rules, exceptions, day):
        cursor = datetime.combine(day, window_start, tzinfo=zone).astimezone(UTC)
        limit = datetime.combine(day, window_end, tzinfo=zone).astimezone(UTC)
        while cursor + length <= limit:
            slots.append(TimeSlot(cursor, cursor + length))
            cursor += length
    return slots


def plan_day(
    slots: Sequence[TimeSlot],
    held_count: int,
    booked: Sequence[tuple[datetime, datetime]],
    now: datetime,
    release_minutes: int = DEFAULT_RELEASE_MINUTES,
) -> list[DaySlot]:
    """Apply emergency holdback, bookings and the clock to a day's full grid.

    - The *last* `held_count` slots of the full grid are held back (capped at the grid size).
      This is decided before bookings, so booking a regular slot never changes what is held.
    - Slots overlapping a booked interval are removed, held or not.
    - Slots that have started (start <= now) are removed.
    - A held slot that is still free and starts within `release_minutes` becomes regular.
    """
    held_from = max(len(slots) - max(held_count, 0), 0)
    release_window = timedelta(minutes=release_minutes)
    planned: list[DaySlot] = []
    for index, slot in enumerate(slots):
        if any(start < slot.end_time and slot.start_time < end for start, end in booked):
            continue
        if slot.start_time <= now:
            continue
        held = index >= held_from and slot.start_time - now > release_window
        planned.append(DaySlot(slot.start_time, slot.end_time, held))
    return planned
