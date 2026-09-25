from app.api.schemas.base import CamelModel


class Sample(CamelModel):
    slot_length_minutes: int
    reported_symptoms: str | None = None


def test_snake_case_fields_serialize_as_camel_case() -> None:
    sample = Sample(slot_length_minutes=20)

    assert sample.model_dump(by_alias=True) == {
        "slotLengthMinutes": 20,
        "reportedSymptoms": None,
    }


def test_model_accepts_camel_case_input() -> None:
    sample = Sample.model_validate({"slotLengthMinutes": 15, "reportedSymptoms": "cough"})

    assert sample.slot_length_minutes == 15
    assert sample.reported_symptoms == "cough"


def test_model_still_accepts_snake_case_names_for_internal_construction() -> None:
    assert Sample(slot_length_minutes=5).slot_length_minutes == 5
