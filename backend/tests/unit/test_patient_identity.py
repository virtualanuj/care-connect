import pytest

from app.domain.errors import ValidationFailed
from app.domain.patient_identity import normalize_name, normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Asha Rao", "asha rao"),
        ("  Asha   Rao  ", "asha rao"),
        ("ASHA RAO", "asha rao"),
        ("asha\trao\n", "asha rao"),
        ("Ａｓｈａ Ｒａｏ", "asha rao"),  # full-width letters (NFKC)
        ("Zoë Müller", "zoë müller"),
        ("STRASSE", "strasse"),
        ("Straße", "strasse"),  # casefold, not just lower
        ("Ó Briain", "ó briain"),
        ("Mary-Jane O'Neil", "mary-jane o'neil"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_composed_and_decomposed_accents_normalize_to_the_same_value() -> None:
    assert normalize_name("José") == normalize_name("José")


@pytest.mark.parametrize(
    ("raw", "region", "expected"),
    [
        ("+91 98765 43210", "IN", "+919876543210"),
        ("98765 43210", "IN", "+919876543210"),
        ("098765 43210", "IN", "+919876543210"),
        ("(415) 555-2671", "US", "+14155552671"),
        ("415.555.2671", "US", "+14155552671"),
        ("+1 415 555 2671", "IN", "+14155552671"),  # explicit country code beats region
        ("  +44 20 7946 0958 ", "US", "+442079460958"),
    ],
)
def test_normalize_phone_to_e164(raw: str, region: str, expected: str) -> None:
    assert normalize_phone(raw, region) == expected


def test_different_spellings_of_one_number_normalize_identically() -> None:
    forms = ["+91 98765 43210", "98765-43210", "(98765) 43210", "0 98765 43210"]

    assert len({normalize_phone(f, "IN") for f in forms}) == 1


@pytest.mark.parametrize("raw", ["", "abc", "12345", "+91 12", "555-0102"])
def test_invalid_phone_numbers_are_rejected(raw: str) -> None:
    with pytest.raises(ValidationFailed):
        normalize_phone(raw, "IN")
