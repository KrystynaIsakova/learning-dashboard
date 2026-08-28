"""Step 3: enrollments cleaning rules (docs/cleaning_rules.md, section 2)."""

import pandas as pd
import pytest

from src.cleaning.enrollments import (
    check_certification,
    check_user_reference,
    check_week_and_progress,
    clean_enrollments,
    clear_impossible_completions,
    drop_full_duplicates,
    fix_progress_pct,
    parse_completed_at,
    parse_enrolled_at,
)
from src.cleaning.errors import CleaningError


def make_enrollments(n: int = 1, **overrides) -> pd.DataFrame:
    data = {
        "enrollment_id": [f"E{i}" for i in range(n)],
        "user_id": ["U1"] * n,
        "course_id": ["C1"] * n,
        "course_url": ["http://example.test/c1"] * n,
        "specialization_id": ["S1"] * n,
        "course_no": [1] * n,
        "enrolled_at": ["2022-01-10"] * n,
        "completed_at": [None] * n,
        "last_week_reached": [1] * n,
        "n_weeks": [4] * n,
        "progress_pct": [25.0] * n,
        "funnel_state": ["viewed"] * n,
        "is_certified": [0] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data)


CLEAN_USERS = pd.DataFrame({"user_id": ["U1", "U2"]})


# --- 2.1 / 2.2 dates ---------------------------------------------------------

def test_both_enrolled_at_formats_are_supported():
    df = make_enrollments(2, enrolled_at=["2022-06-08", "08.06.2022"])

    result, stats = parse_enrolled_at(df)

    assert result["enrolled_at"].nunique() == 1
    assert stats["enrolled_at_reformatted"] == 1


def test_ambiguous_dotted_date_is_day_first():
    """03.04.2024 must be 3 April, not 4 March."""

    result, _ = parse_enrolled_at(make_enrollments(1, enrolled_at=["03.04.2024"]))

    assert result["enrolled_at"].iloc[0] == pd.Timestamp("2024-04-03")


def test_unparsable_enrolled_at_stops_cleaning():
    with pytest.raises(CleaningError, match="enrolled_at could not be converted"):
        parse_enrolled_at(make_enrollments(1, enrolled_at=["31.02.2022"]))


def test_empty_completed_at_stays_empty():
    result = parse_completed_at(make_enrollments(2, completed_at=[None, "2022-03-01"]))

    assert result["completed_at"].isna().tolist() == [True, False]


def test_unparsable_completed_at_stops_cleaning():
    with pytest.raises(CleaningError, match="completed_at could not be converted"):
        parse_completed_at(make_enrollments(1, completed_at=["yesterday"]))


# --- 2.3 progress ------------------------------------------------------------

def test_out_of_range_progress_is_recomputed():
    df = make_enrollments(1, progress_pct=[104.0], last_week_reached=[1], n_weeks=[4])

    result, stats = fix_progress_pct(df)

    assert result["progress_pct"].iloc[0] == 25.0
    assert stats["progress_pct_fixed"] == 1


def test_valid_progress_is_left_alone():
    df = make_enrollments(1, progress_pct=[25.0])

    result, stats = fix_progress_pct(df)

    assert result["progress_pct"].iloc[0] == 25.0
    assert stats["progress_pct_fixed"] == 0


def test_zero_n_weeks_stops_cleaning_before_dividing():
    df = make_enrollments(1, n_weeks=[0], last_week_reached=[0], progress_pct=[104.0])

    with pytest.raises(CleaningError, match="cannot divide by zero"):
        fix_progress_pct(df)


def test_missing_n_weeks_stops_cleaning():
    df = make_enrollments(1, n_weeks=[None])

    with pytest.raises(CleaningError, match="n_weeks contains missing values"):
        fix_progress_pct(df)


# --- 2.4 impossible completions ---------------------------------------------

def _with_parsed_dates(df):
    df = df.copy()
    df["enrolled_at"] = pd.to_datetime(df["enrolled_at"])
    df["completed_at"] = pd.to_datetime(df["completed_at"])
    return df


def test_completion_before_enrolment_is_blanked_but_row_is_kept():
    df = _with_parsed_dates(
        make_enrollments(1, enrolled_at=["2022-01-10"], completed_at=["2021-12-01"])
    )

    result, rejected, stats = clear_impossible_completions(df)

    assert len(result) == 1
    assert pd.isna(result["completed_at"].iloc[0])
    assert rejected.empty
    assert stats["completed_at_cleared"] == 1


def test_certified_row_with_impossible_date_is_rejected_not_blanked():
    """Rule 2.4 exception: blanking would break rule 2.8, so the row is set aside."""

    df = _with_parsed_dates(
        make_enrollments(
            1,
            enrolled_at=["2022-01-10"],
            completed_at=["2021-12-01"],
            is_certified=[1],
            funnel_state=["certified"],
            last_week_reached=[4],
            progress_pct=[100.0],
        )
    )

    result, rejected, stats = clear_impossible_completions(df)

    assert result.empty
    assert len(rejected) == 1
    # The original date is preserved, not blanked.
    assert rejected["completed_at"].iloc[0] == pd.Timestamp("2021-12-01")
    assert stats["certified_without_completion_rejected"] == 1
    assert stats["completed_at_cleared"] == 0


# --- 2.5 duplicates ----------------------------------------------------------

def test_full_duplicates_are_removed():
    df = pd.concat([make_enrollments(1), make_enrollments(1)], ignore_index=True)

    result, stats = drop_full_duplicates(df)

    assert len(result) == 1
    assert stats["duplicates_removed"] == 1


def test_duplicate_is_only_found_after_dates_are_normalised():
    """The rule order matters: these rows differ as text, not as dates."""

    df = make_enrollments(2, enrolled_at=["2022-06-08", "08.06.2022"])
    df["enrollment_id"] = ["E0", "E0"]

    # Before normalisation the rows differ as text, so they are not full
    # duplicates and the unique-key check reports them as a conflict.
    with pytest.raises(CleaningError, match="share the same enrollment_id"):
        drop_full_duplicates(df.copy())

    normalised, _ = parse_enrolled_at(df)
    _, after = drop_full_duplicates(normalised)
    assert after["duplicates_removed"] == 1


def test_conflicting_enrollment_ids_stop_cleaning():
    df = make_enrollments(2, last_week_reached=[1, 2])
    df["enrollment_id"] = ["E0", "E0"]

    with pytest.raises(CleaningError, match="share the same enrollment_id"):
        drop_full_duplicates(df)


# --- 2.6 / 2.7 / 2.8 checks --------------------------------------------------

def test_unknown_user_id_stops_cleaning():
    df = make_enrollments(1, user_id=["U9999999"])

    with pytest.raises(CleaningError, match="absent from users"):
        check_user_reference(df, CLEAN_USERS)


def test_progress_not_matching_formula_stops_cleaning():
    df = make_enrollments(1, progress_pct=[30.0], last_week_reached=[1], n_weeks=[4])

    with pytest.raises(CleaningError, match="must equal round"):
        check_week_and_progress(df)


def test_last_week_beyond_n_weeks_stops_cleaning():
    df = make_enrollments(1, last_week_reached=[5], n_weeks=[4], progress_pct=[125.0])

    with pytest.raises(CleaningError, match="must not exceed n_weeks"):
        check_week_and_progress(df)


def test_certified_flag_outside_certified_state_stops_cleaning():
    df = make_enrollments(
        1, is_certified=[1], funnel_state=["viewed"], completed_at=["2022-02-01"]
    )
    df["completed_at"] = pd.to_datetime(df["completed_at"])

    with pytest.raises(CleaningError, match="only allowed for funnel_state"):
        check_certification(df)


def test_certified_without_completion_date_stops_cleaning():
    df = make_enrollments(1, is_certified=[1], funnel_state=["certified"])

    with pytest.raises(CleaningError, match="must have a completed_at date"):
        check_certification(df)


def test_unknown_funnel_state_stops_cleaning():
    df = make_enrollments(1, funnel_state=["abandoned"])

    with pytest.raises(CleaningError, match="funnel_state contains values"):
        check_certification(df)


# --- orchestration -----------------------------------------------------------

def test_clean_enrollments_does_not_mutate_the_raw_frame():
    raw = make_enrollments(2, enrolled_at=["2022-06-08", "08.06.2022"])
    before = raw.copy()

    clean_enrollments(raw, CLEAN_USERS)

    pd.testing.assert_frame_equal(raw, before)


def test_clean_enrollments_reports_counts():
    raw = make_enrollments(
        2,
        enrolled_at=["2022-06-08", "08.06.2022"],
        progress_pct=[104.0, 25.0],
    )

    clean, _rejected, stats = clean_enrollments(raw, CLEAN_USERS)

    assert stats["raw_rows"] == 2
    assert stats["clean_rows"] == 2
    assert stats["progress_pct_fixed"] == 1
    assert stats["enrolled_at_reformatted"] == 1
    assert clean["progress_pct"].tolist() == [25.0, 25.0]
