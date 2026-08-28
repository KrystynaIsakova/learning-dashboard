"""Step 4: payments cleaning rules (docs/cleaning_rules.md, section 3)."""

import pandas as pd
import pytest

from src.cleaning.errors import CleaningError
from src.cleaning.payments import (
    check_paid_after_signup,
    check_payment_key,
    clean_payments,
    parse_paid_at,
    split_unknown_user,
    validate_amount,
    validate_is_refunded,
    validate_payment_plan,
)


CLEAN_USERS = pd.DataFrame(
    {
        "user_id": ["U1", "U2"],
        "signup_date": pd.to_datetime(["2021-01-01", "2022-01-01"]),
    }
)


def make_payments(n: int = 1, **overrides) -> pd.DataFrame:
    data = {
        "payment_id": [f"P{i}" for i in range(n)],
        "user_id": ["U1"] * n,
        "paid_at": ["2022-05-16"] * n,
        "amount_usd": [49.0] * n,
        "plan": ["monthly"] * n,
        "is_refunded": [0] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data)


# --- 3.1 / 3.2 ---------------------------------------------------------------

def test_duplicate_payment_id_stops_cleaning():
    df = make_payments(2)
    df["payment_id"] = ["P0", "P0"]

    with pytest.raises(CleaningError, match="not unique"):
        check_payment_key(df)


def test_missing_payment_id_stops_cleaning():
    with pytest.raises(CleaningError, match="missing values"):
        check_payment_key(make_payments(2, payment_id=["P0", None]))


def test_unparsable_paid_at_stops_cleaning():
    with pytest.raises(CleaningError, match="could not be converted"):
        parse_paid_at(make_payments(1, paid_at=["not a date"]))


# --- 3.3 amount --------------------------------------------------------------

@pytest.mark.parametrize(
    ("plan", "amount"),
    [("monthly", 49.0), ("annual", 399.0)],
)
def test_expected_plan_prices_are_accepted(plan, amount):
    validate_amount(make_payments(1, plan=[plan], amount_usd=[amount]))


def test_amount_not_matching_plan_stops_cleaning():
    df = make_payments(1, plan=["annual"], amount_usd=[49.0])

    with pytest.raises(CleaningError, match="does not match the plan price"):
        validate_amount(df)


@pytest.mark.parametrize("amount", [0.0, -49.0])
def test_non_positive_amount_stops_cleaning(amount):
    with pytest.raises(CleaningError, match="greater than 0"):
        validate_amount(make_payments(1, amount_usd=[amount]))


def test_missing_amount_stops_cleaning():
    df = make_payments(2, amount_usd=[49.0, None])

    with pytest.raises(CleaningError, match="missing values"):
        validate_amount(df)


def test_non_numeric_amount_stops_cleaning():
    with pytest.raises(CleaningError, match="not numeric"):
        validate_amount(make_payments(1, amount_usd=["49.0"]))


# --- 3.4 / 3.5 ---------------------------------------------------------------

def test_unknown_plan_stops_cleaning():
    with pytest.raises(CleaningError, match="outside the allowed list"):
        validate_payment_plan(make_payments(1, plan=["free"]))


def test_invalid_is_refunded_stops_cleaning():
    with pytest.raises(CleaningError, match="only 0 or 1"):
        validate_is_refunded(make_payments(1, is_refunded=[2]))


def test_refunded_payments_are_kept_with_their_amount():
    raw = make_payments(2, is_refunded=[0, 1])

    clean, rejected, stats = clean_payments(raw, CLEAN_USERS)

    assert len(clean) == 2
    assert rejected.empty
    assert stats["refunded_kept"] == 1
    assert clean.loc[clean["is_refunded"] == 1, "amount_usd"].tolist() == [49.0]


# --- 3.6 unknown user --------------------------------------------------------

def test_unknown_user_payments_are_separated_not_dropped():
    raw = make_payments(2, user_id=["U1", "U9999999"])

    kept, rejected, stats = split_unknown_user(raw, CLEAN_USERS)

    assert kept["user_id"].tolist() == ["U1"]
    assert rejected["user_id"].tolist() == ["U9999999"]
    assert stats["payments_unknown_user_rejected"] == 1
    # Nothing is invented or rewritten.
    assert len(kept) + len(rejected) == len(raw)


# --- 3.7 payment date --------------------------------------------------------

def test_payment_before_signup_stops_cleaning():
    df = make_payments(1, user_id=["U2"], paid_at=["2021-06-01"])
    df["paid_at"] = pd.to_datetime(df["paid_at"])

    with pytest.raises(CleaningError, match="earlier than the user's signup_date"):
        check_paid_after_signup(df, CLEAN_USERS)


def test_payment_on_signup_day_is_allowed():
    df = make_payments(1, user_id=["U2"], paid_at=["2022-01-01"])
    df["paid_at"] = pd.to_datetime(df["paid_at"])

    check_paid_after_signup(df, CLEAN_USERS)


# --- orchestration -----------------------------------------------------------

def test_signup_date_is_not_added_to_the_cleaned_frame():
    clean, _, _ = clean_payments(make_payments(1), CLEAN_USERS)

    assert "signup_date" not in clean.columns
    assert clean.columns.tolist() == make_payments(1).columns.tolist()


def test_clean_payments_does_not_mutate_the_raw_frame():
    raw = make_payments(2, user_id=["U1", "U9999999"])
    before = raw.copy()

    clean_payments(raw, CLEAN_USERS)

    pd.testing.assert_frame_equal(raw, before)


def test_clean_payments_reports_counts():
    raw = make_payments(3, user_id=["U1", "U2", "U9999999"])

    clean, rejected, stats = clean_payments(raw, CLEAN_USERS)

    assert stats["raw_rows"] == 3
    assert stats["clean_rows"] == 2
    assert stats["rejected_rows"] == 1
    assert len(clean) + len(rejected) == 3
