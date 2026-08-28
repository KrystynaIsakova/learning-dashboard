"""Clean the enrollments table (docs/cleaning_rules.md, section 2).

The rule order in clean_enrollments is mandated by the specification: full
duplicates only become identical after dates are normalised and values fixed.
"""

import pandas as pd

from src.cleaning.errors import fail


ALLOWED_FUNNEL_STATES = {"registered", "viewed", "explored", "certified"}
CERTIFIED_STATE = "certified"
ALLOWED_IS_CERTIFIED = {0, 1}

ISO_FORMAT = "%Y-%m-%d"
DOTTED_FORMAT = "%d.%m.%Y"


def _parse_mixed_dates(values: pd.Series) -> pd.Series:
    """Parse ISO dates, and dotted values explicitly as DD.MM.YYYY (rule 2.1)."""

    text = values.astype("string").str.strip()
    dotted = text.str.contains(r"\.", na=False)

    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    parsed[dotted] = pd.to_datetime(
        text[dotted], format=DOTTED_FORMAT, errors="coerce"
    )
    parsed[~dotted] = pd.to_datetime(
        text[~dotted], format=ISO_FORMAT, errors="coerce"
    )
    return parsed


def parse_enrolled_at(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rule 2.1: support both formats; every value must convert."""

    result = df.copy()
    dotted = result["enrolled_at"].astype("string").str.contains(r"\.", na=False)
    parsed = _parse_mixed_dates(result["enrolled_at"])

    unparsed = result[parsed.isna()]
    if not unparsed.empty:
        fail("2.1", "enrolled_at could not be converted to a date.", unparsed)

    result["enrolled_at"] = parsed
    return result, {"enrolled_at_reformatted": int(dotted.sum())}


def parse_completed_at(df: pd.DataFrame) -> pd.DataFrame:
    """Rule 2.2: convert non-empty values; empty values stay empty."""

    result = df.copy()
    original = result["completed_at"]
    present = original.notna() & (original.astype("string").str.strip() != "")

    parsed = _parse_mixed_dates(original)

    unparsed = result[present & parsed.isna()]
    if not unparsed.empty:
        fail("2.2", "completed_at could not be converted to a date.", unparsed)

    result["completed_at"] = parsed.where(present)
    return result


def check_weeks_precondition(df: pd.DataFrame) -> None:
    """Rule 2.3 precondition: n_weeks is the denominator, so guard it first."""

    missing = df[df["n_weeks"].isna()]
    if not missing.empty:
        fail("2.3", "n_weeks contains missing values.", missing)

    too_small = df[df["n_weeks"] < 1]
    if not too_small.empty:
        fail("2.3", "n_weeks must be >= 1; cannot divide by zero.", too_small)


def _expected_progress(df: pd.DataFrame) -> pd.Series:
    return (df["last_week_reached"] / df["n_weeks"] * 100).round(1)


def fix_progress_pct(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rule 2.3: recompute only values outside 0-100; keep valid ones as they are."""

    check_weeks_precondition(df)

    result = df.copy()
    out_of_range = (result["progress_pct"] < 0) | (result["progress_pct"] > 100)

    result.loc[out_of_range, "progress_pct"] = _expected_progress(result)[out_of_range]

    return result, {"progress_pct_fixed": int(out_of_range.sum())}


def clear_impossible_completions(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Rule 2.4: blank completed_at earlier than enrolled_at; keep the row.

    Exception documented in rule 2.4: a certified enrollment cannot have its
    completed_at blanked, because rule 2.8 requires that date. Blanking it and
    inventing one are both forbidden, so those rows are separated as unresolved
    instead of being cleaned or silently dropped.
    """

    result = df.copy()
    impossible = result["completed_at"].notna() & (
        result["completed_at"] < result["enrolled_at"]
    )

    certified = impossible & (result["is_certified"] == 1)
    rejected = result[certified].copy()

    result = result[~certified].copy()
    to_clear = impossible[~certified]
    result.loc[to_clear, "completed_at"] = pd.NaT

    stats = {
        "completed_at_cleared": int(to_clear.sum()),
        "certified_without_completion_rejected": int(certified.sum()),
    }
    return result.reset_index(drop=True), rejected.reset_index(drop=True), stats


def drop_full_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rule 2.5: drop rows identical across all columns, then require a unique key.

    Deliberately not drop_duplicates(subset=["enrollment_id"]): that would
    silently discard rows that differ.
    """

    result = df.drop_duplicates().copy()
    removed = len(df) - len(result)

    conflicting = result[result["enrollment_id"].duplicated(keep=False)]
    if not conflicting.empty:
        fail(
            "2.5",
            "Different rows share the same enrollment_id after removing "
            "full duplicates.",
            conflicting.sort_values("enrollment_id"),
        )

    return result.reset_index(drop=True), {"duplicates_removed": int(removed)}


def check_user_reference(df: pd.DataFrame, clean_users: pd.DataFrame) -> None:
    """Rule 2.6: every user_id must exist in the cleaned users table."""

    unknown = df[~df["user_id"].isin(set(clean_users["user_id"]))]
    if not unknown.empty:
        fail("2.6", "enrollments reference user_id values absent from users.", unknown)


def check_week_and_progress(df: pd.DataFrame) -> None:
    """Rule 2.7: ranges plus the progress formula, for every row."""

    check_weeks_precondition(df)

    checks = {
        "last_week_reached must be >= 0": df["last_week_reached"] < 0,
        "last_week_reached must not exceed n_weeks": (
            df["last_week_reached"] > df["n_weeks"]
        ),
        "progress_pct must be >= 0": df["progress_pct"] < 0,
        "progress_pct must be <= 100": df["progress_pct"] > 100,
        "progress_pct must equal round(last_week_reached / n_weeks * 100, 1)": (
            df["progress_pct"] != _expected_progress(df)
        ),
    }

    for message, offending_mask in checks.items():
        if offending_mask.any():
            fail("2.7", message, df[offending_mask])


def check_certification(df: pd.DataFrame) -> None:
    """Rule 2.8: statuses must agree; never fix them automatically."""

    bad_state = df[~df["funnel_state"].isin(ALLOWED_FUNNEL_STATES)]
    if not bad_state.empty:
        fail("2.8", "funnel_state contains values outside the allowed list.", bad_state)

    bad_flag = df[~df["is_certified"].isin(ALLOWED_IS_CERTIFIED)]
    if not bad_flag.empty:
        fail("2.8", "is_certified must contain only 0 or 1.", bad_flag)

    inconsistent = df[
        (df["is_certified"] == 1) & (df["funnel_state"] != CERTIFIED_STATE)
    ]
    if not inconsistent.empty:
        fail(
            "2.8",
            "is_certified = 1 is only allowed for funnel_state = certified.",
            inconsistent,
        )

    missing_completion = df[(df["is_certified"] == 1) & df["completed_at"].isna()]
    if not missing_completion.empty:
        fail(
            "2.8",
            "Certified enrollments must have a completed_at date.",
            missing_completion,
        )


def verify_enrollments_result(df: pd.DataFrame, clean_users: pd.DataFrame) -> None:
    """Section 2, 'Перевірка результату': re-check the cleaned frame."""

    missing_key = df[df["enrollment_id"].isna()]
    if not missing_key.empty:
        fail("2.5", "enrollment_id contains missing values.", missing_key)

    duplicated = df[df["enrollment_id"].duplicated(keep=False)]
    if not duplicated.empty:
        fail("2.5", "enrollment_id is not unique.", duplicated)

    if df["enrolled_at"].isna().any():
        fail("2.1", "enrolled_at contains invalid dates.", df[df["enrolled_at"].isna()])

    impossible = df[df["completed_at"].notna() & (df["completed_at"] < df["enrolled_at"])]
    if not impossible.empty:
        fail("2.4", "completed_at is still earlier than enrolled_at.", impossible)

    check_user_reference(df, clean_users)
    check_week_and_progress(df)
    check_certification(df)


def clean_enrollments(
    raw_enrollments: pd.DataFrame,
    clean_users: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Apply section 2 in the mandated order.

    Returns the clean frame, the rejected frame (rule 2.4 exception) and the
    counts needed for the cleaning report.
    """

    stats: dict[str, int] = {"raw_rows": len(raw_enrollments)}
    result = raw_enrollments.copy()

    result, enrolled_stats = parse_enrolled_at(result)
    stats.update(enrolled_stats)

    result = parse_completed_at(result)

    result, progress_stats = fix_progress_pct(result)
    stats.update(progress_stats)

    result, rejected, completion_stats = clear_impossible_completions(result)
    stats.update(completion_stats)

    result, duplicate_stats = drop_full_duplicates(result)
    stats.update(duplicate_stats)

    verify_enrollments_result(result, clean_users)

    stats["clean_rows"] = len(result)
    stats["rejected_rows"] = len(rejected)
    return result, rejected, stats
