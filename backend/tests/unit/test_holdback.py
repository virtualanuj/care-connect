from datetime import UTC, datetime, timedelta

from app.domain.slots import DaySlot, TimeSlot, plan_day

DAY = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
MORNING_NOW = datetime(2026, 3, 2, 6, 0, tzinfo=UTC)  # before the day starts


def grid(count: int = 6, minutes: int = 20) -> list[TimeSlot]:
    return [
        TimeSlot(DAY + timedelta(minutes=i * minutes), DAY + timedelta(minutes=(i + 1) * minutes))
        for i in range(count)
    ]


def emergency_starts(slots: list[DaySlot]) -> list[int]:
    return [int((s.start_time - DAY).total_seconds() // 60) for s in slots if s.is_emergency]


def regular_starts(slots: list[DaySlot]) -> list[int]:
    return [int((s.start_time - DAY).total_seconds() // 60) for s in slots if not s.is_emergency]


def test_with_no_holdback_every_slot_is_regular() -> None:
    result = plan_day(grid(), 0, [], MORNING_NOW)

    assert len(result) == 6
    assert emergency_starts(result) == []


def test_the_last_slot_of_the_day_is_held_back_when_n_is_one() -> None:
    result = plan_day(grid(), 1, [], MORNING_NOW)

    assert emergency_starts(result) == [100]
    assert regular_starts(result) == [0, 20, 40, 60, 80]


def test_the_last_two_slots_are_held_back_when_n_is_two() -> None:
    assert emergency_starts(plan_day(grid(), 2, [], MORNING_NOW)) == [80, 100]


def test_n_larger_than_the_day_holds_back_every_slot() -> None:
    result = plan_day(grid(3), 10, [], MORNING_NOW)

    assert emergency_starts(result) == [0, 20, 40]
    assert regular_starts(result) == []


def test_booked_slots_are_removed_whether_regular_or_held() -> None:
    booked = [(DAY + timedelta(minutes=20), DAY + timedelta(minutes=40))]  # a regular slot
    held_booked = [(DAY + timedelta(minutes=100), DAY + timedelta(minutes=120))]

    assert [
        int((s.start_time - DAY).total_seconds() // 60)
        for s in plan_day(grid(), 1, booked, MORNING_NOW)
    ] == [0, 40, 60, 80, 100]
    assert 100 not in emergency_starts(plan_day(grid(), 1, held_booked, MORNING_NOW))


def test_booking_a_regular_slot_does_not_change_which_slots_are_held() -> None:
    booked = [(DAY, DAY + timedelta(minutes=20))]

    with_booking = plan_day(grid(), 1, booked, MORNING_NOW)
    without = plan_day(grid(), 1, [], MORNING_NOW)

    assert emergency_starts(with_booking) == emergency_starts(without) == [100]


def test_an_appointment_that_only_partly_overlaps_a_slot_still_removes_it() -> None:
    booked = [(DAY + timedelta(minutes=10), DAY + timedelta(minutes=30))]  # overlaps 0-20 and 20-40

    result = plan_day(grid(), 0, booked, MORNING_NOW)

    assert [int((s.start_time - DAY).total_seconds() // 60) for s in result] == [40, 60, 80, 100]


def test_past_slots_are_dropped_and_a_slot_starting_exactly_now_is_dropped_too() -> None:
    now = DAY + timedelta(minutes=40)

    result = plan_day(grid(), 0, [], now)

    assert regular_starts(result) == [60, 80, 100]


def test_a_held_slot_is_released_when_it_starts_within_sixty_minutes() -> None:
    last = DAY + timedelta(minutes=100)

    exactly_60 = plan_day(grid(), 1, [], last - timedelta(minutes=60))
    just_over_60 = plan_day(grid(), 1, [], last - timedelta(minutes=60, seconds=1))

    assert 100 in regular_starts(exactly_60)  # released at exactly 60 minutes
    assert 100 in emergency_starts(just_over_60)  # still held 61 minutes out


def test_a_released_slot_is_only_regular_for_the_time_left_before_it_starts() -> None:
    last = DAY + timedelta(minutes=100)

    result = plan_day(grid(), 1, [], last - timedelta(minutes=1))

    assert 100 in regular_starts(result)
    assert emergency_starts(result) == []


def test_changing_n_never_affects_appointments_already_booked() -> None:
    booked = [(DAY + timedelta(minutes=100), DAY + timedelta(minutes=120))]  # booked last slot

    for n in (0, 1, 2):
        starts = [
            int((s.start_time - DAY).total_seconds() // 60)
            for s in plan_day(grid(), n, booked, MORNING_NOW)
        ]
        assert 100 not in starts
