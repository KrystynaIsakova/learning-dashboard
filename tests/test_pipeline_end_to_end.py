"""Step 6: acceptance criteria (docs/cleaning_rules.md, section 6)."""

import pandas as pd
import pytest

from src.database import get_engine
from src.extract import load_source_tables
from src.paths import (
    CLEAN_DIR,
    EXPECTED_CLEAN_ROWS,
    EXPECTED_RAW_ROWS,
    EXPECTED_REJECTED_ROWS,
    REJECTED_DIR,
    REPORTS_DIR,
)
from src.pipeline import run_pipeline


@pytest.fixture(scope="module")
def pipeline_run():
    """Run the real pipeline once and expose its stats."""

    return run_pipeline()


@pytest.fixture(scope="module")
def clean_frames(pipeline_run):
    return {
        name: pd.read_csv(CLEAN_DIR / f"{name}.csv")
        for name in EXPECTED_CLEAN_ROWS
    }


# --- files and row counts ----------------------------------------------------

@pytest.mark.parametrize("name", sorted(EXPECTED_CLEAN_ROWS))
def test_clean_csv_exists_with_expected_rows(clean_frames, name):
    assert (CLEAN_DIR / f"{name}.csv").exists()
    assert len(clean_frames[name]) == EXPECTED_CLEAN_ROWS[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_REJECTED_ROWS))
def test_rejected_csv_exists_with_expected_rows(pipeline_run, name):
    path = REJECTED_DIR / f"{name}.csv"

    assert path.exists()
    assert len(pd.read_csv(path)) == EXPECTED_REJECTED_ROWS[name]


def test_no_record_is_lost_between_raw_clean_and_rejected(pipeline_run):
    for table, stats in pipeline_run.items():
        rejected = stats.get("rejected_rows", 0)
        assert stats["clean_rows"] + rejected == stats["raw_rows"], table


# --- keys, relationships, dates ---------------------------------------------

@pytest.mark.parametrize(
    ("table", "key"),
    [
        ("users", "user_id"),
        ("enrollments", "enrollment_id"),
        ("payments", "payment_id"),
    ],
)
def test_keys_are_unique_and_present(clean_frames, table, key):
    column = clean_frames[table][key]

    assert column.notna().all()
    assert not column.duplicated().any()


@pytest.mark.parametrize("table", ["enrollments", "payments"])
def test_every_user_id_exists_in_users(clean_frames, table):
    known = set(clean_frames["users"]["user_id"])

    assert clean_frames[table]["user_id"].isin(known).all()


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("users", "signup_date"),
        ("enrollments", "enrolled_at"),
        ("payments", "paid_at"),
    ],
)
def test_dates_are_written_as_iso(clean_frames, table, column):
    values = clean_frames[table][column]

    assert values.notna().all()
    assert values.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()


def test_completed_at_is_either_iso_or_empty(clean_frames):
    values = clean_frames["enrollments"]["completed_at"]
    present = values.dropna()

    assert present.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert values.isna().any()


# --- documented value constraints -------------------------------------------

def test_no_completion_before_enrolment(clean_frames):
    df = clean_frames["enrollments"]
    completed = pd.to_datetime(df["completed_at"])
    enrolled = pd.to_datetime(df["enrolled_at"])

    assert not (completed.notna() & (completed < enrolled)).any()


def test_progress_is_in_range_and_matches_the_formula(clean_frames):
    df = clean_frames["enrollments"]
    expected = (df["last_week_reached"] / df["n_weeks"] * 100).round(1)

    assert df["progress_pct"].between(0, 100).all()
    assert (df["progress_pct"] == expected).all()


def test_certification_is_consistent(clean_frames):
    df = clean_frames["enrollments"]
    certified = df["is_certified"] == 1

    assert df["is_certified"].isin([0, 1]).all()
    assert (df.loc[certified, "funnel_state"] == "certified").all()
    assert df.loc[certified, "completed_at"].notna().all()


def test_refunded_payments_are_kept_unchanged(clean_frames):
    df = clean_frames["payments"]
    refunded = df[df["is_refunded"] == 1]

    assert len(refunded) > 0
    assert refunded["amount_usd"].gt(0).all()


def test_signup_date_is_not_leaked_into_payments(clean_frames):
    assert "signup_date" not in clean_frames["payments"].columns


# --- report ------------------------------------------------------------------

def test_report_exists_and_states_actual_counts(pipeline_run):
    report = (REPORTS_DIR / "cleaning_report.md").read_text(encoding="utf-8")

    assert "| users | 40 000 | 40 000 | 0 |" in report
    assert "| enrollments | 94 705 | 94 686 | 19 |" in report
    assert "| payments | 87 924 | 87 884 | 40 |" in report
    assert "Не пройдено: 0." in report


# --- raw data safety ---------------------------------------------------------

def test_raw_tables_are_unchanged(pipeline_run):
    """The pipeline must never write to PostgreSQL."""

    raw = load_source_tables(get_engine())

    for name, expected_rows in EXPECTED_RAW_ROWS.items():
        assert len(raw[name]) == expected_rows
