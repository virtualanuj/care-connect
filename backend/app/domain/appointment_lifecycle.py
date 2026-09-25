"""The appointment lifecycle as a pure transition table (docs/spec.md §3).

    Booked -> Checked-in -> In-consultation -> Completed
    Booked | Checked-in -> No-show
    Booked | Checked-in -> Cancelled

Every transition is a manual action; nothing here looks at the clock.
"""

from enum import StrEnum

from app.domain.errors import InvalidTransition
from app.domain.models import AppointmentStatus as S


class Action(StrEnum):
    CHECK_IN = "check_in"
    START_CONSULTATION = "start_consultation"
    COMPLETE = "complete"
    MARK_NO_SHOW = "mark_no_show"
    CANCEL = "cancel"


_TRANSITIONS: dict[tuple[S, Action], S] = {
    (S.BOOKED, Action.CHECK_IN): S.CHECKED_IN,
    (S.CHECKED_IN, Action.START_CONSULTATION): S.IN_CONSULTATION,
    (S.IN_CONSULTATION, Action.COMPLETE): S.COMPLETED,
    (S.BOOKED, Action.MARK_NO_SHOW): S.NO_SHOW,
    (S.CHECKED_IN, Action.MARK_NO_SHOW): S.NO_SHOW,
    (S.BOOKED, Action.CANCEL): S.CANCELLED,
    (S.CHECKED_IN, Action.CANCEL): S.CANCELLED,
}


def next_status(current: S, action: Action) -> S:
    """The status after `action`, or `InvalidTransition` if the pair is not allowed."""
    try:
        return _TRANSITIONS[(current, action)]
    except KeyError:
        raise InvalidTransition(
            f"Cannot {action.value.replace('_', ' ')} an appointment that is {current.value}"
        ) from None
