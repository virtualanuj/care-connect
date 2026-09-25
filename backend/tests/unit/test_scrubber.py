from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.adapters.ai.scrubber import scrub
from app.domain.models import PatientIdentifiers

ASHA = PatientIdentifiers(
    name="Asha Rao",
    phone="+919876543210",
    email="asha.rao@example.com",
    dob=date(1990, 5, 1),
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Asha Rao has a cough", "[NAME] has a cough"),
        ("asha rao has a cough", "[NAME] has a cough"),
        ("ASHA RAO has a cough", "[NAME] has a cough"),
        ("Asha reports a cough", "[NAME] reports a cough"),
        ("Rao reports a cough", "[NAME] reports a cough"),
        ("Asha  Rao reports a cough", "[NAME] reports a cough"),
        ("Patient: Asha Rao, cough", "Patient: [NAME], cough"),
        ("Ashaan is not a match", "Ashaan is not a match"),  # whole words only
    ],
)
def test_the_patients_own_name_is_replaced_in_any_case(text: str, expected: str) -> None:
    assert scrub(text, ASHA) == expected


def test_short_name_parts_are_left_alone_but_the_full_name_still_goes() -> None:
    who = PatientIdentifiers(name="Al Li")

    assert scrub("Al Li is here, also li and al", who) == "[NAME] is here, also li and al"


@pytest.mark.parametrize(
    "phone",
    [
        "+919876543210",
        "+91 98765 43210",
        "+91-98765-43210",
        "98765 43210",
        "(98765) 43210",
        "09876543210",
    ],
)
def test_the_patients_phone_is_removed_in_common_formats(phone: str) -> None:
    result = scrub(f"call me on {phone} please", ASHA)

    assert result == "call me on [PHONE] please"


def test_other_phone_numbers_are_removed_too() -> None:
    assert scrub("my husband's number is 555-0102", ASHA) == "my husband's number is [PHONE]"
    assert scrub("emergency contact 020 7946 0958", ASHA) == "emergency contact [PHONE]"
    assert scrub("call +1 (415) 555-2671", ASHA) == "call [PHONE]"


@pytest.mark.parametrize(
    "email",
    ["asha.rao@example.com", "ASHA.RAO@EXAMPLE.COM", "someone.else@clinic.co.uk", "a+tag@x.io"],
)
def test_email_addresses_are_removed(email: str) -> None:
    assert scrub(f"write to {email} thanks", ASHA) == "write to [EMAIL] thanks"


@pytest.mark.parametrize(
    "written",
    [
        "1990-05-01",
        "01/05/1990",
        "01-05-1990",
        "1.5.1990",
        "1 May 1990",
        "1st May 1990",
        "May 1, 1990",
        "1 may 1990",
    ],
)
def test_the_date_of_birth_is_removed_in_common_formats(written: str) -> None:
    assert scrub(f"born {written}, cough", ASHA) == "born [DATE], cough"


def test_other_full_dates_are_removed() -> None:
    assert scrub("seen on 12/03/2001 and 2001-03-12", ASHA) == "seen on [DATE] and [DATE]"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("my wife Priya called", "my wife [NAME] called"),
        ("his son Rohan Das is worried", "his son [NAME] is worried"),
        ("Her mother Meena is with her", "Her mother [NAME] is with her"),
        ("my neighbour Kumar drove me", "my neighbour [NAME] drove me"),
    ],
)
def test_a_named_relative_is_removed(text: str, expected: str) -> None:
    assert scrub(text, ASHA) == expected


@pytest.mark.parametrize(
    "clinical",
    [
        "chest pain for 3 days",
        "35 year old with temperature 101.5 and BP 140/90",
        "took 500 mg twice a day for 10 days",
        "pain 7/10, started at 6pm",
        "cough since March",
        "weight 72 kg, height 175 cm",
    ],
)
def test_ordinary_clinical_numbers_and_words_are_untouched(clinical: str) -> None:
    assert scrub(clinical, ASHA) == clinical


def test_several_identifiers_in_one_note_are_all_removed() -> None:
    text = "Asha Rao (DOB 1 May 1990, asha.rao@example.com, +91 98765 43210) has chest pain"

    assert scrub(text, ASHA) == "[NAME] (DOB [DATE], [EMAIL], [PHONE]) has chest pain"


def test_missing_optional_identifiers_are_fine() -> None:
    assert scrub("Kiran is unwell", PatientIdentifiers(name="Kiran Rao")) == "[NAME] is unwell"


def test_scrubbing_is_idempotent() -> None:
    once = scrub("Asha Rao 98765 43210 asha.rao@example.com 1990-05-01 my wife Priya", ASHA)

    assert scrub(once, ASHA) == once


@given(
    prefix=st.text(alphabet="abcdefghij ,.", max_size=30),
    suffix=st.text(alphabet="klmnopqrst ,.", max_size=30),
)
def test_known_identifiers_never_survive_whatever_surrounds_them(prefix: str, suffix: str) -> None:
    text = f"{prefix} Asha Rao +91 98765 43210 asha.rao@example.com 1990-05-01 {suffix}"

    out = scrub(text, ASHA).lower()

    for secret in ("asha", "rao", "98765", "43210", "asha.rao@example.com", "1990-05-01"):
        assert secret not in out
