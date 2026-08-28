"""Step 1: users cleaning rules (docs/cleaning_rules.md, section 1)."""

import pandas as pd
import pytest

from src.cleaning.errors import CleaningError
from src.cleaning.users import (
    check_user_key,
    clean_users,
    normalize_country,
    parse_signup_date,
    validate_user_categories,
)


def make_users(**overrides) -> pd.DataFrame:
    data = {
        "user_id": ["U1", "U2"],
        "signup_date": ["2021-01-03", "2022-05-16"],
        "country": ["USA", "India"],
        "plan": ["free", "monthly"],
        "persona": ["upskiller", "student"],
        "age_band": ["18-24", "45+"],
        "device_primary": ["desktop", "mobile"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_duplicate_user_id_stops_cleaning():
    with pytest.raises(CleaningError, match="not unique"):
        check_user_key(make_users(user_id=["U1", "U1"]))


def test_missing_user_id_stops_cleaning():
    with pytest.raises(CleaningError, match="missing values"):
        check_user_key(make_users(user_id=["U1", None]))


def test_unparsable_signup_date_stops_cleaning():
    with pytest.raises(CleaningError, match="could not be converted"):
        parse_signup_date(make_users(signup_date=["2021-01-03", "not a date"]))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("USA", "United States"),
        ("DE", "Germany"),
        ("UK", "United Kingdom"),
    ],
)
def test_country_abbreviations_are_expanded(raw, expected):
    result, _ = normalize_country(make_users(country=[raw, "India"]))
    assert result["country"].tolist() == [expected, "India"]


def test_missing_country_becomes_unknown_and_others_are_kept():
    result, stats = normalize_country(make_users(country=[None, "Ukraine"]))

    assert result["country"].tolist() == ["Unknown", "Ukraine"]
    assert stats["countries_filled_unknown"] == 1
    assert stats["countries_unified"] == 0


@pytest.mark.parametrize(
    "column",
    ["plan", "persona", "age_band", "device_primary"],
)
def test_unknown_category_stops_cleaning(column):
    df = make_users(**{column: ["free" if column == "plan" else "bogus", "bogus"]})

    with pytest.raises(CleaningError, match="outside the allowed list"):
        validate_user_categories(df)


def test_clean_users_does_not_mutate_the_raw_frame():
    raw = make_users(country=[None, "USA"])
    before = raw.copy()

    clean_users(raw)

    pd.testing.assert_frame_equal(raw, before)


def test_clean_users_reports_counts():
    raw = make_users(country=["USA", None])
    clean, stats = clean_users(raw)

    assert stats["raw_rows"] == 2
    assert stats["clean_rows"] == 2
    assert stats["countries_unified"] == 1
    assert stats["countries_filled_unknown"] == 1
    assert clean["signup_date"].dtype.kind == "M"
