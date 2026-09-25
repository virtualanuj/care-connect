"""Real responses of the M2 endpoints must match docs/openapi.yaml."""

import uuid

from fastapi.testclient import TestClient

from app.domain.models import Role
from tests.api_harness import ApiHarness
from tests.contract.conftest import ContractCheck

API = "/api/v1"


def setup(harness: ApiHarness) -> tuple[TestClient, dict[str, str], dict[str, str], dict, dict]:  # type: ignore[type-arg]
    client = harness.client
    admin = harness.admin_headers()
    doctor_user = harness.create_user("doc@clinic.test", Role.DOCTOR)
    doc = harness.headers_for("doc@clinic.test")
    specialty = client.post(
        f"{API}/specialties",
        json={"name": "General", "defaultSlotLengthMinutes": 20},
        headers=admin,
    ).json()
    doctor = client.post(
        f"{API}/doctors",
        json={"userId": str(doctor_user.id), "name": "Dr Doc", "specialtyId": specialty["id"]},
        headers=admin,
    ).json()
    return client, admin, doc, specialty, doctor


def test_clinic_settings(harness: ApiHarness, assert_contract: ContractCheck) -> None:
    client, admin, doc, _, _ = setup(harness)

    assert_contract(client.get(f"{API}/clinic-settings", headers=doc))
    assert_contract(
        client.patch(f"{API}/clinic-settings", json={"followUpMaxDays": 14}, headers=admin)
    )
    assert_contract(
        client.patch(f"{API}/clinic-settings", json={"followUpMaxDays": 0}, headers=admin)
    )
    assert_contract(
        client.patch(f"{API}/clinic-settings", json={"followUpMaxDays": 9}, headers=doc)
    )
    assert_contract(client.get(f"{API}/clinic-settings"))


def test_specialties_and_doctors(harness: ApiHarness, assert_contract: ContractCheck) -> None:
    client, admin, doc, specialty, doctor = setup(harness)
    other_user = harness.create_user("other@clinic.test", Role.DOCTOR)

    assert_contract(client.get(f"{API}/specialties", headers=doc))
    assert_contract(
        client.post(
            f"{API}/specialties",
            json={"name": "General", "defaultSlotLengthMinutes": 20},
            headers=admin,
        )
    )  # 409
    assert_contract(
        client.patch(f"{API}/specialties/{specialty['id']}", json={"name": "GP"}, headers=admin)
    )
    assert_contract(
        client.patch(f"{API}/specialties/{uuid.uuid4()}", json={"name": "x"}, headers=admin)
    )
    assert_contract(client.get(f"{API}/doctors", headers=doc))
    assert_contract(client.get(f"{API}/doctors/{doctor['id']}", headers=doc))
    assert_contract(client.get(f"{API}/doctors/{uuid.uuid4()}", headers=doc))
    assert_contract(
        client.post(
            f"{API}/doctors",
            json={"userId": str(other_user.id), "name": "Dr Other", "specialtyId": specialty["id"]},
            headers=admin,
        )
    )  # 201
    assert_contract(
        client.post(
            f"{API}/doctors",
            json={"userId": str(other_user.id), "name": "Again", "specialtyId": specialty["id"]},
            headers=admin,
        )
    )  # 409
    assert_contract(
        client.patch(f"{API}/doctors/{doctor['id']}", json={"slotLengthMinutes": 30}, headers=doc)
    )
    assert_contract(
        client.patch(f"{API}/doctors/{doctor['id']}", json={"active": False}, headers=doc)
    )


def test_patients_and_history(harness: ApiHarness, assert_contract: ContractCheck) -> None:
    client, admin, doc, _, _ = setup(harness)

    created = client.post(
        f"{API}/patients",
        json={"name": "Asha Rao", "phone": "9876543210", "dob": "1990-05-01"},
        headers=doc,
    )
    assert_contract(created)  # 201
    patient_id = created.json()["id"]
    assert_contract(
        client.post(
            f"{API}/patients", json={"name": "asha rao", "phone": "9876543210"}, headers=doc
        )
    )
    assert_contract(
        client.post(f"{API}/patients", json={"name": "X", "phone": "1"}, headers=doc)
    )  # 400
    assert_contract(client.get(f"{API}/patients?phone=9876543210", headers=doc))
    assert_contract(client.get(f"{API}/patients/{patient_id}", headers=doc))
    assert_contract(client.get(f"{API}/patients/{uuid.uuid4()}", headers=doc))
    assert_contract(client.patch(f"{API}/patients/{patient_id}", json={"dob": None}, headers=admin))

    history = f"{API}/patients/{patient_id}/medical-history"
    entry = client.post(history, json={"description": "Allergic to X"}, headers=admin)
    assert_contract(entry)  # 201
    assert_contract(
        client.post(
            history,
            json={"kind": "amendment", "amendsEntryId": entry.json()["id"], "description": "Y"},
            headers=admin,
        )
    )
    assert_contract(
        client.post(history, json={"kind": "amendment", "description": "no target"}, headers=admin)
    )
    assert_contract(client.get(history, headers=doc))


def test_availability(harness: ApiHarness, assert_contract: ContractCheck) -> None:
    client, admin, doc, _, doctor = setup(harness)
    rules = f"{API}/doctors/{doctor['id']}/availability"
    rule = {"dayOfWeek": "monday", "startTime": "09:00", "endTime": "12:00"}

    created = client.post(rules, json=rule, headers=doc)
    assert_contract(created)  # 201
    rid = created.json()["id"]
    assert_contract(client.post(rules, json={**rule, "startTime": "11:00"}, headers=admin))  # 409
    assert_contract(client.post(rules, json={**rule, "startTime": "bad"}, headers=admin))  # 400
    assert_contract(client.get(rules, headers=doc))
    assert_contract(client.patch(f"{rules}/{rid}", json={"endTime": "13:00"}, headers=doc))
    assert_contract(client.patch(f"{rules}/{uuid.uuid4()}", json={"endTime": "13:00"}, headers=doc))
    assert_contract(client.delete(f"{rules}/{rid}", headers=doc))  # 204
    assert_contract(client.delete(f"{rules}/{rid}", headers=doc))  # 404

    exceptions = f"{API}/doctors/{doctor['id']}/availability-exceptions"
    extra = client.post(
        exceptions,
        json={
            "date": "2026-03-10",
            "type": "extra_hours",
            "startTime": "13:00",
            "endTime": "15:00",
        },
        headers=doc,
    )
    assert_contract(extra)
    assert_contract(
        client.post(exceptions, json={"date": "2026-03-11", "type": "unavailable"}, headers=doc)
    )
    assert_contract(
        client.post(exceptions, json={"date": "2026-03-11", "type": "extra_hours"}, headers=doc)
    )
    assert_contract(client.get(exceptions, headers=doc))
    assert_contract(
        client.patch(f"{exceptions}/{extra.json()['id']}", json={"endTime": "16:00"}, headers=doc)
    )
    assert_contract(client.delete(f"{exceptions}/{extra.json()['id']}", headers=doc))
