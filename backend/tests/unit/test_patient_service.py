import uuid
from datetime import date, timedelta

import pytest

from app.domain.errors import NotFound, PatientAlreadyExists, ValidationFailed
from app.domain.models import HistoryKind, Role, User
from app.services.patient_service import PatientService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import InMemoryMedicalHistoryRepository, InMemoryPatientRepository
from tests.unit.test_audit_service import START


class Setup:
    def __init__(self) -> None:
        self.patients = InMemoryPatientRepository()
        self.history = InMemoryMedicalHistoryRepository()
        self.clock = FixedClock(START)
        self.service = PatientService(self.patients, self.history, self.clock, default_region="IN")
        self.actor = User(uuid.uuid4(), "fd@x.test", "FD", Role.FRONT_DESK_ADMIN, "h")
        self.doctor = User(uuid.uuid4(), "doc@x.test", "Doc", Role.DOCTOR, "h")


@pytest.fixture
def s() -> Setup:
    return Setup()


def test_register_stores_the_e164_phone_and_trimmed_name(s: Setup) -> None:
    patient = s.service.register("  Asha Rao ", "98765 43210", date(1990, 5, 1), "a@x.test")

    assert (patient.name, patient.phone) == ("Asha Rao", "+919876543210")
    assert patient.dob == date(1990, 5, 1)
    assert patient.created_at == START


def test_family_members_can_share_a_phone_number(s: Setup) -> None:
    s.service.register("Asha Rao", "9876543210")
    s.service.register("Kiran Rao", "+91 98765 43210")

    found = s.service.search(phone="098765-43210", name=None, page=1, page_size=10)

    assert sorted(p.name for p in found.items) == ["Asha Rao", "Kiran Rao"]
    assert found.total == 2


@pytest.mark.parametrize("second_name", ["asha rao", "ASHA   RAO", "  Asha Rao  "])
def test_same_person_registered_again_is_a_duplicate_regardless_of_spelling(
    s: Setup, second_name: str
) -> None:
    s.service.register("Asha Rao", "+91 98765 43210")

    with pytest.raises(PatientAlreadyExists):
        s.service.register(second_name, "098765 43210")


def test_same_name_on_a_different_phone_is_a_different_patient(s: Setup) -> None:
    s.service.register("Asha Rao", "9876543210")

    assert s.service.register("Asha Rao", "9123456789").phone == "+919123456789"


def test_invalid_phone_or_blank_name_is_rejected(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.service.register("Asha", "12345")
    with pytest.raises(ValidationFailed):
        s.service.register("   ", "9876543210")
    with pytest.raises(ValidationFailed):
        s.service.search(phone="not a phone", name=None, page=1, page_size=10)


def test_search_by_name_prefix_is_case_and_space_insensitive_and_paginated(s: Setup) -> None:
    for index, name in enumerate(["Asha Rao", "Ashok Kumar", "Bina Shah"]):
        s.service.register(name, f"98765 0000{index}")

    first = s.service.search(phone=None, name="  ASH", page=1, page_size=1)
    second = s.service.search(phone=None, name="ash", page=2, page_size=1)

    assert first.total == second.total == 2
    assert [p.name for p in first.items] == ["Asha Rao"]
    assert [p.name for p in second.items] == ["Ashok Kumar"]


def test_get_unknown_patient_is_not_found(s: Setup) -> None:
    with pytest.raises(NotFound):
        s.service.get(uuid.uuid4())


def test_update_changes_fields_and_can_clear_optional_ones(s: Setup) -> None:
    patient = s.service.register("Asha Rao", "9876543210", date(1990, 1, 1), "a@x.test")

    updated = s.service.update(
        patient.id, {"name": "Asha R. Rao", "phone": "9123456789", "dob": None, "email": None}
    )

    assert (updated.name, updated.phone, updated.dob, updated.email) == (
        "Asha R. Rao",
        "+919123456789",
        None,
        None,
    )


def test_update_that_collides_with_another_patient_is_rejected(s: Setup) -> None:
    s.service.register("Asha Rao", "9876543210")
    kiran = s.service.register("Kiran Rao", "9876543210")

    with pytest.raises(PatientAlreadyExists):
        s.service.update(kiran.id, {"name": "asha  RAO"})


def test_update_may_keep_its_own_identity_and_unknown_patient_is_not_found(s: Setup) -> None:
    asha = s.service.register("Asha Rao", "9876543210")

    assert s.service.update(asha.id, {"name": "ASHA RAO"}).name == "ASHA RAO"
    with pytest.raises(NotFound):
        s.service.update(uuid.uuid4(), {"name": "x"})


# ---- medical history ---------------------------------------------------------------------------


def test_history_is_listed_oldest_first_with_the_author_and_clock_time(s: Setup) -> None:
    patient = s.service.register("Asha Rao", "9876543210")
    s.service.add_history(s.actor, patient.id, HistoryKind.ENTRY, "Penicillin allergy", None)
    s.clock.advance(timedelta(minutes=5))
    s.service.add_history(s.doctor, patient.id, HistoryKind.ENTRY, "Asthma", None)

    entries = s.service.list_history(patient.id)

    assert [e.description for e in entries] == ["Penicillin allergy", "Asthma"]
    assert (entries[0].recorded_by, entries[0].recorded_at) == (s.actor.id, START)
    assert entries[1].recorded_by == s.doctor.id


def test_an_amendment_references_the_original_and_leaves_it_untouched(s: Setup) -> None:
    patient = s.service.register("Asha Rao", "9876543210")
    original = s.service.add_history(s.actor, patient.id, HistoryKind.ENTRY, "Allergic to X", None)

    amendment = s.service.add_history(
        s.actor, patient.id, HistoryKind.AMENDMENT, "Correction: allergic to Y", original.id
    )

    entries = s.service.list_history(patient.id)
    assert [e.kind for e in entries] == [HistoryKind.ENTRY, HistoryKind.AMENDMENT]
    assert entries[0].description == "Allergic to X"
    assert amendment.amends_entry_id == original.id


def test_amendment_rules_are_enforced(s: Setup) -> None:
    asha = s.service.register("Asha Rao", "9876543210")
    kiran = s.service.register("Kiran Rao", "9876543210")
    kirans_entry = s.service.add_history(s.actor, kiran.id, HistoryKind.ENTRY, "note", None)
    own_entry = s.service.add_history(s.actor, asha.id, HistoryKind.ENTRY, "note", None)

    with pytest.raises(ValidationFailed):  # amendment without a target
        s.service.add_history(s.actor, asha.id, HistoryKind.AMENDMENT, "fix", None)
    with pytest.raises(ValidationFailed):  # target belongs to another patient
        s.service.add_history(s.actor, asha.id, HistoryKind.AMENDMENT, "fix", kirans_entry.id)
    with pytest.raises(ValidationFailed):  # target does not exist
        s.service.add_history(s.actor, asha.id, HistoryKind.AMENDMENT, "fix", uuid.uuid4())
    with pytest.raises(ValidationFailed):  # plain entry may not reference anything
        s.service.add_history(s.actor, asha.id, HistoryKind.ENTRY, "note", own_entry.id)


def test_history_requires_an_existing_patient_and_a_description(s: Setup) -> None:
    patient = s.service.register("Asha Rao", "9876543210")

    with pytest.raises(NotFound):
        s.service.add_history(s.actor, uuid.uuid4(), HistoryKind.ENTRY, "x", None)
    with pytest.raises(NotFound):
        s.service.list_history(uuid.uuid4())
    with pytest.raises(ValidationFailed):
        s.service.add_history(s.actor, patient.id, HistoryKind.ENTRY, "   ", None)


def test_history_has_no_edit_or_delete_operations() -> None:
    public = {n for n in dir(PatientService) if not n.startswith("_")}

    assert not {n for n in public if n.startswith(("edit", "delete", "remove", "update_history"))}
    assert {"add_history", "list_history"} <= public
