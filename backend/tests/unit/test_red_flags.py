import pytest

from app.domain.red_flags import RED_FLAG_LIST_VERSION, match_red_flags


@pytest.mark.parametrize(
    "text",
    [
        "Severe chest pain since this morning",
        "chest tightness when walking",
        "pressure in my chest",
        "having difficulty breathing",
        "trouble breathing at night",
        "shortness of breath climbing stairs",
        "SHORTNESS OF BREATH!!!",
        "he can't breathe",
        "she cannot breathe properly",
        "struggling to breathe",
        "patient is unconscious",
        "found unresponsive on the floor",
        "collapsed at work",
        "heavy bleeding that will not stop",
        "severe bleeding from the leg",
        "coughing up blood",
        "vomiting blood",
        "signs of a stroke: face drooping",
        "slurred speech and confusion",
        "sudden weakness on one side",
        "sudden numbness in the arm",
        "had a seizure an hour ago",
        "convulsions for two minutes",
        "anaphylaxis after a bee sting",
        "throat swelling after eating peanuts",
        "I feel suicidal",
        "I want to die",
        "thinking of suicide",
        "took an overdose of paracetamol",
        "suspected poisoning",
    ],
)
def test_clearly_emergent_presentations_are_flagged(text: str) -> None:
    assert match_red_flags(text) != [], text


@pytest.mark.parametrize(
    "text",
    [
        "mild headache since yesterday",
        "sore throat and a runny nose",
        "routine check-up for blood pressure",
        "knee pain after running",
        "rash on the forearm",
        "",
        "   ",
        "follow-up for diabetes review",
    ],
)
def test_ordinary_presentations_are_not_flagged(text: str) -> None:
    assert match_red_flags(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "no chest pain",
        "denies chest pain",
        "without any chest pain",
        "not having chest pain today",
        "never had chest pain",
        "No shortness of breath.",
        "patient denies difficulty breathing",
    ],
)
def test_a_negation_directly_before_the_phrase_suppresses_the_flag(text: str) -> None:
    assert match_red_flags(text) == [], text


@pytest.mark.parametrize(
    "text",
    [
        "no fever, chest pain since morning",  # clause break resets the negation
        "no fever but chest pain",
        "no cough and chest pain",  # 'no' is more than two words away: flag, do not risk a miss
        "denies nausea; shortness of breath at night",
        "no chest pain but difficulty breathing",  # a different phrase is still flagged
        "not eating well, having a seizure",
    ],
)
def test_a_negation_never_hides_a_different_phrase_or_a_later_clause(text: str) -> None:
    assert match_red_flags(text) != [], text


def test_matches_report_which_phrases_were_found_without_duplicates() -> None:
    found = match_red_flags("Chest pain and chest pain again, plus a SEIZURE")

    assert sorted(found) == ["chest pain", "seizure"]


def test_matching_ignores_case_punctuation_and_extra_whitespace() -> None:
    assert match_red_flags("CHEST     pain!!!") == ["chest pain"]
    assert match_red_flags("chest-pain") == ["chest pain"]


def test_phrases_match_whole_words_only() -> None:
    assert match_red_flags("the strokes of a paintbrush") == []
    assert match_red_flags("a stroke") == ["stroke"]


def test_the_list_is_versioned_so_changes_can_be_audited() -> None:
    assert RED_FLAG_LIST_VERSION
