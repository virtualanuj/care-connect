import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.postgres.models import AvailabilityExceptionRow, AvailabilityRow
from app.domain.models import Availability, AvailabilityException


def _rule(row: AvailabilityRow) -> Availability:
    return Availability(row.id, row.doctor_id, row.day_of_week, row.start_time, row.end_time)


def _exception(row: AvailabilityExceptionRow) -> AvailabilityException:
    return AvailabilityException(
        row.id, row.doctor_id, row.date, row.type, row.start_time, row.end_time
    )


class PostgresAvailabilityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ---- weekly rules -----------------------------------------------------------------------

    def add_rule(self, rule: Availability) -> None:
        self._session.add(
            AvailabilityRow(
                id=rule.id,
                doctor_id=rule.doctor_id,
                day_of_week=rule.day_of_week,
                start_time=rule.start_time,
                end_time=rule.end_time,
            )
        )
        self._session.flush()

    def get_rule(self, rule_id: uuid.UUID) -> Availability | None:
        row = self._session.get(AvailabilityRow, rule_id)
        return _rule(row) if row else None

    def list_rules(self, doctor_id: uuid.UUID) -> list[Availability]:
        rows = self._session.scalars(
            select(AvailabilityRow)
            .where(AvailabilityRow.doctor_id == doctor_id)
            .order_by(AvailabilityRow.day_of_week, AvailabilityRow.start_time)
        )
        return [_rule(r) for r in rows]

    def update_rule(self, rule: Availability) -> None:
        row = self._session.get(AvailabilityRow, rule.id)
        if row is None:
            return
        row.day_of_week, row.start_time, row.end_time = (
            rule.day_of_week,
            rule.start_time,
            rule.end_time,
        )
        self._session.flush()

    def delete_rule(self, rule_id: uuid.UUID) -> None:
        row = self._session.get(AvailabilityRow, rule_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    # ---- exceptions -------------------------------------------------------------------------

    def add_exception(self, exception: AvailabilityException) -> None:
        self._session.add(
            AvailabilityExceptionRow(
                id=exception.id,
                doctor_id=exception.doctor_id,
                date=exception.date,
                type=exception.type,
                start_time=exception.start_time,
                end_time=exception.end_time,
            )
        )
        self._session.flush()

    def get_exception(self, exception_id: uuid.UUID) -> AvailabilityException | None:
        row = self._session.get(AvailabilityExceptionRow, exception_id)
        return _exception(row) if row else None

    def list_exceptions(self, doctor_id: uuid.UUID) -> list[AvailabilityException]:
        rows = self._session.scalars(
            select(AvailabilityExceptionRow)
            .where(AvailabilityExceptionRow.doctor_id == doctor_id)
            .order_by(AvailabilityExceptionRow.date, AvailabilityExceptionRow.start_time)
        )
        return [_exception(r) for r in rows]

    def update_exception(self, exception: AvailabilityException) -> None:
        row = self._session.get(AvailabilityExceptionRow, exception.id)
        if row is None:
            return
        row.date, row.type = exception.date, exception.type
        row.start_time, row.end_time = exception.start_time, exception.end_time
        self._session.flush()

    def delete_exception(self, exception_id: uuid.UUID) -> None:
        row = self._session.get(AvailabilityExceptionRow, exception_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()
