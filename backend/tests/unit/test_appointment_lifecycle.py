import itertools

import pytest

from app.domain.appointment_lifecycle import Action, next_status
from app.domain.errors import InvalidTransition
from app.domain.models import AppointmentStatus as S

VALID = {
    (S.BOOKED, Action.CHECK_IN): S.CHECKED_IN,
    (S.CHECKED_IN, Action.START_CONSULTATION): S.IN_CONSULTATION,
    (S.IN_CONSULTATION, Action.COMPLETE): S.COMPLETED,
    (S.BOOKED, Action.MARK_NO_SHOW): S.NO_SHOW,
    (S.CHECKED_IN, Action.MARK_NO_SHOW): S.NO_SHOW,
    (S.BOOKED, Action.CANCEL): S.CANCELLED,
    (S.CHECKED_IN, Action.CANCEL): S.CANCELLED,
}


@pytest.mark.parametrize(("status", "action", "expected"), [(*k, v) for k, v in VALID.items()])
def test_every_valid_transition_from_the_spec_succeeds(
    status: S, action: Action, expected: S
) -> None:
    assert next_status(status, action) == expected


INVALID = [pair for pair in itertools.product(S, Action) if pair not in VALID]


@pytest.mark.parametrize(("status", "action"), INVALID)
def test_every_other_status_and_action_pair_is_rejected(status: S, action: Action) -> None:
    with pytest.raises(InvalidTransition):
        next_status(status, action)


def test_the_matrix_covers_all_thirty_pairs() -> None:
    assert len(VALID) + len(INVALID) == len(S) * len(Action) == 30


def test_terminal_states_allow_nothing() -> None:
    for status in (S.COMPLETED, S.NO_SHOW, S.CANCELLED):
        for action in Action:
            with pytest.raises(InvalidTransition):
                next_status(status, action)
