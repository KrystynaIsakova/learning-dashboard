"""Clean the users table (docs/cleaning_rules.md, section 1)."""

import pandas as pd

from src.cleaning.errors import fail


COUNTRY_REPLACEMENTS = {
    "USA": "United States",
    "DE": "Germany",
    "UK": "United Kingdom",
}
UNKNOWN_COUNTRY = "Unknown"

ALLOWED_CATEGORIES = {
    "plan": {"free", "monthly", "annual", "financial_aid"},
    "persona": {"upskiller", "career_switcher", "student", "hobbyist"},
    "age_band": {"18-24", "25-34", "35-44", "45+"},
    "device_primary": {"desktop", "mobile", "tablet"},
}

REQUIRED_COLUMNS = [
    "user_id",
    "signup_date",
    "country",
    "plan",
    "persona",
    "age_band",
    "device_primary",
]


def check_user_key(df: pd.DataFrame) -> None:
    """Rule 1.1: user_id must be present and unique. Values stay unchanged."""

    missing = df[df["user_id"].isna()]
    if not missing.empty:
        fail("1.1", "user_id contains missing values.", missing)

    duplicated = df[df["user_id"].duplicated(keep=False)]
    if not duplicated.empty:
        fail("1.1", "user_id is not unique.", duplicated.sort_values("user_id"))


def parse_signup_date(df: pd.DataFrame) -> pd.DataFrame:
    """Rule 1.2: every signup_date must convert to a date."""

    result = df.copy()
    parsed = pd.to_datetime(result["signup_date"], errors="coerce")

    unparsed = result[parsed.isna()]
    if not unparsed.empty:
        fail("1.2", "signup_date could not be converted to a date.", unparsed)

    result["signup_date"] = parsed
    return result


def normalize_country(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rule 1.3: expand USA/DE/UK, fill missing with Unknown, keep the rest."""

    result = df.copy()

    unified = result["country"].isin(COUNTRY_REPLACEMENTS).sum()
    filled = result["country"].isna().sum()

    result["country"] = (
        result["country"].replace(COUNTRY_REPLACEMENTS).fillna(UNKNOWN_COUNTRY)
    )

    return result, {
        "countries_unified": int(unified),
        "countries_filled_unknown": int(filled),
    }


def validate_user_categories(df: pd.DataFrame) -> None:
    """Rule 1.4: every categorical value must belong to its documented list."""

    for column, allowed in ALLOWED_CATEGORIES.items():
        offending = df[~df[column].isin(allowed)]
        if not offending.empty:
            found = sorted(offending[column].dropna().unique())
            fail(
                "1.4",
                f"{column} contains values outside the allowed list. "
                f"Unexpected values: {found}.",
                offending,
            )


def verify_users_result(df: pd.DataFrame) -> None:
    """Section 1, 'Перевірка результату': re-check the cleaned frame."""

    check_user_key(df)
    validate_user_categories(df)

    if df["country"].isna().any():
        fail("1.3", "country still contains missing values.", df[df["country"].isna()])

    leftovers = df[df["country"].isin(COUNTRY_REPLACEMENTS)]
    if not leftovers.empty:
        fail("1.3", "country still contains USA/DE/UK.", leftovers)

    if df["signup_date"].isna().any():
        fail("1.2", "signup_date contains invalid dates.", df[df["signup_date"].isna()])


def clean_users(raw_users: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply section 1 in order and return the clean frame plus report counts."""

    missing_columns = set(REQUIRED_COLUMNS) - set(raw_users.columns)
    if missing_columns:
        raise KeyError(f"users is missing required columns: {sorted(missing_columns)}")

    result = raw_users.copy()

    check_user_key(result)
    result = parse_signup_date(result)
    result, stats = normalize_country(result)
    validate_user_categories(result)

    verify_users_result(result)

    stats["raw_rows"] = len(raw_users)
    stats["clean_rows"] = len(result)
    return result, stats
