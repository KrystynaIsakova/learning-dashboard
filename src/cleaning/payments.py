"""Clean the payments table (docs/cleaning_rules.md, section 3)."""

import pandas as pd

from src.cleaning.errors import fail


ALLOWED_PLANS = {"monthly", "annual"}
ALLOWED_IS_REFUNDED = {0, 1}

EXPECTED_AMOUNTS = {
    "monthly": 49.0,
    "annual": 399.0,
}

UNKNOWN_USER_ID = "U9999999"

REQUIRED_COLUMNS = [
    "payment_id",
    "user_id",
    "paid_at",
    "amount_usd",
    "plan",
    "is_refunded",
]


def check_payment_key(df: pd.DataFrame) -> None:
    """Rule 3.1: payment_id must be present and unique. Values stay unchanged."""

    missing = df[df["payment_id"].isna()]
    if not missing.empty:
        fail("3.1", "payment_id contains missing values.", missing)

    duplicated = df[df["payment_id"].duplicated(keep=False)]
    if not duplicated.empty:
        fail("3.1", "payment_id is not unique.", duplicated.sort_values("payment_id"))


def parse_paid_at(df: pd.DataFrame) -> pd.DataFrame:
    """Rule 3.2: every paid_at must convert to a date."""

    result = df.copy()
    parsed = pd.to_datetime(result["paid_at"], errors="coerce")

    unparsed = result[parsed.isna()]
    if not unparsed.empty:
        fail("3.2", "paid_at could not be converted to a date.", unparsed)

    result["paid_at"] = parsed
    return result


def validate_payment_plan(df: pd.DataFrame) -> None:
    """Rule 3.4: only monthly and annual are allowed."""

    offending = df[~df["plan"].isin(ALLOWED_PLANS)]
    if not offending.empty:
        found = sorted(offending["plan"].dropna().unique())
        fail(
            "3.4",
            f"plan contains values outside the allowed list. Unexpected: {found}.",
            offending,
        )


def validate_amount(df: pd.DataFrame) -> None:
    """Rule 3.3: numeric, present, positive, and matching the plan's price."""

    if not pd.api.types.is_numeric_dtype(df["amount_usd"]):
        fail("3.3", "amount_usd is not numeric.", df.head())

    missing = df[df["amount_usd"].isna()]
    if not missing.empty:
        fail("3.3", "amount_usd contains missing values.", missing)

    non_positive = df[df["amount_usd"] <= 0]
    if not non_positive.empty:
        fail("3.3", "amount_usd must be greater than 0.", non_positive)

    expected = df["plan"].map(EXPECTED_AMOUNTS)
    mismatched = df[df["amount_usd"] != expected]
    if not mismatched.empty:
        fail(
            "3.3",
            f"amount_usd does not match the plan price {EXPECTED_AMOUNTS}.",
            mismatched,
        )


def validate_is_refunded(df: pd.DataFrame) -> None:
    """Rule 3.5: only 0 and 1. Refunds are kept, and their amount is untouched."""

    offending = df[~df["is_refunded"].isin(ALLOWED_IS_REFUNDED)]
    if not offending.empty:
        fail("3.5", "is_refunded must contain only 0 or 1.", offending)


def split_unknown_user(
    df: pd.DataFrame,
    clean_users: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Rule 3.6: set aside payments whose user_id is absent from users.

    The records are returned so they can be saved, never dropped. No fake user
    is created and no user_id is rewritten.
    """

    known = set(clean_users["user_id"])
    unknown = ~df["user_id"].isin(known)

    kept = df[~unknown].copy()
    rejected = df[unknown].copy()

    return (
        kept.reset_index(drop=True),
        rejected.reset_index(drop=True),
        {"payments_unknown_user_rejected": int(unknown.sum())},
    )


def check_paid_after_signup(df: pd.DataFrame, clean_users: pd.DataFrame) -> None:
    """Rule 3.7: paid_at must not precede signup_date.

    signup_date is joined temporarily and never added to the cleaned frame.
    """

    duplicated_users = clean_users[clean_users["user_id"].duplicated(keep=False)]
    if not duplicated_users.empty:
        fail(
            "3.7",
            "Cannot join signup_date: user_id is not unique in the cleaned users.",
            duplicated_users.sort_values("user_id"),
        )

    signup = clean_users.set_index("user_id")["signup_date"]
    joined = df.assign(signup_date=df["user_id"].map(signup))

    too_early = joined[joined["paid_at"] < joined["signup_date"]]
    if not too_early.empty:
        fail("3.7", "paid_at is earlier than the user's signup_date.", too_early)


def verify_payments_result(df: pd.DataFrame, clean_users: pd.DataFrame) -> None:
    """Section 3, 'Перевірка результату': re-check the cleaned frame."""

    check_payment_key(df)

    unknown = df[~df["user_id"].isin(set(clean_users["user_id"]))]
    if not unknown.empty:
        fail("3.6", "payments still reference user_id values absent from users.", unknown)

    if df["paid_at"].isna().any():
        fail("3.2", "paid_at contains invalid dates.", df[df["paid_at"].isna()])

    validate_payment_plan(df)
    validate_amount(df)
    validate_is_refunded(df)
    check_paid_after_signup(df, clean_users)

    if "signup_date" in df.columns:
        fail("3.7", "signup_date must not be part of the cleaned payments.", df.head())


def clean_payments(
    raw_payments: pd.DataFrame,
    clean_users: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Apply section 3 and return the clean frame, the rejected frame and counts."""

    missing_columns = set(REQUIRED_COLUMNS) - set(raw_payments.columns)
    if missing_columns:
        raise KeyError(f"payments is missing required columns: {sorted(missing_columns)}")

    stats: dict[str, int] = {"raw_rows": len(raw_payments)}
    result = raw_payments.copy()

    check_payment_key(result)
    result = parse_paid_at(result)
    validate_payment_plan(result)
    validate_amount(result)
    validate_is_refunded(result)

    result, rejected, split_stats = split_unknown_user(result, clean_users)
    stats.update(split_stats)

    check_paid_after_signup(result, clean_users)

    verify_payments_result(result, clean_users)

    stats["refunded_kept"] = int((result["is_refunded"] == 1).sum())
    stats["clean_rows"] = len(result)
    stats["rejected_rows"] = len(rejected)
    return result, rejected, stats
