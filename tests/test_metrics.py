"""Metrics tests (docs/metric_specification.md).

Every metric is checked twice: once against a small hand-built frame, and once
against the real clean CSVs using an independent computation that does not
reuse the metric's own formula.
"""

import pandas as pd
import pytest

from src.metrics import (
    completion_rate,
    gross_revenue,
    load_clean_tables,
    metrics_summary,
    net_revenue,
    refunded_amount,
    total_enrollments,
    total_users,
)


PLAN_PRICES = {"monthly": 49.0, "annual": 399.0}

EXPECTED = {
    "total_users": 40_000,
    "total_enrollments": 94_686,
    "gross_revenue": 6_389_866.0,
    "refunded_amount": 115_003.0,
    "net_revenue": 6_274_863.0,
}
EXPECTED_COMPLETION_RATE = 4_536 / 94_686


@pytest.fixture(scope="module")
def clean():
    return load_clean_tables()


# --- small hand-built frames -------------------------------------------------

def test_total_users_counts_users_without_activity():
    users = pd.DataFrame({"user_id": ["U1", "U2", "U3"]})

    assert total_users(users) == 3


def test_total_enrollments_counts_enrolments_not_users():
    enrollments = pd.DataFrame(
        {"enrollment_id": ["E1", "E2", "E3"], "user_id": ["U1", "U1", "U2"]}
    )

    assert total_enrollments(enrollments) == 3


def test_completion_rate_denominator_includes_registered():
    enrollments = pd.DataFrame(
        {
            "enrollment_id": ["E1", "E2", "E3", "E4"],
            "funnel_state": ["certified", "registered", "registered", "viewed"],
            "is_certified": [1, 0, 0, 0],
        }
    )

    assert completion_rate(enrollments) == 0.25


def test_completion_rate_rejects_an_empty_frame():
    with pytest.raises(ValueError, match="undefined for an empty frame"):
        completion_rate(pd.DataFrame({"is_certified": []}))


def test_refunded_payments_are_included_in_gross_but_not_in_net():
    payments = pd.DataFrame(
        {"amount_usd": [49.0, 399.0, 49.0], "is_refunded": [0, 0, 1]}
    )

    assert gross_revenue(payments) == 497.0
    assert refunded_amount(payments) == 49.0
    assert net_revenue(payments) == 448.0


def test_net_revenue_equals_gross_minus_refunded_on_full_refunds():
    payments = pd.DataFrame(
        {"amount_usd": [49.0, 399.0, 49.0], "is_refunded": [0, 1, 1]}
    )

    assert net_revenue(payments) == gross_revenue(payments) - refunded_amount(payments)


# --- real clean data ---------------------------------------------------------

def test_total_users_on_clean_data(clean):
    assert total_users(clean["users"]) == EXPECTED["total_users"]


def test_total_enrollments_on_clean_data(clean):
    assert total_enrollments(clean["enrollments"]) == EXPECTED["total_enrollments"]


def test_completion_rate_on_clean_data(clean):
    assert completion_rate(clean["enrollments"]) == pytest.approx(
        EXPECTED_COMPLETION_RATE
    )
    assert 0.0 <= completion_rate(clean["enrollments"]) <= 1.0


@pytest.mark.parametrize(
    ("metric", "name"),
    [
        (gross_revenue, "gross_revenue"),
        (refunded_amount, "refunded_amount"),
        (net_revenue, "net_revenue"),
    ],
)
def test_revenue_metrics_on_clean_data(clean, metric, name):
    assert metric(clean["payments"]) == pytest.approx(EXPECTED[name])


# --- reconciliation: independent computations --------------------------------

def test_reconcile_total_users_against_the_file_itself(clean):
    """Count the file's data lines instead of trusting the parsed frame."""

    from src.paths import CLEAN_DIR

    lines = (CLEAN_DIR / "users.csv").read_text(encoding="utf-8").splitlines()

    assert len(lines) - 1 == total_users(clean["users"])


def test_reconcile_completion_rate_against_two_other_definitions(clean):
    """is_certified, completed_at and progress_pct must agree on the numerator."""

    enrollments = clean["enrollments"]

    by_flag = int((enrollments["is_certified"] == 1).sum())
    by_date = int(enrollments["completed_at"].notna().sum())
    by_progress = int((enrollments["progress_pct"] == 100).sum())

    assert by_flag == by_date == by_progress
    assert completion_rate(enrollments) == pytest.approx(by_date / len(enrollments))


def test_reconcile_gross_revenue_against_fixed_plan_prices(clean):
    """Rebuild the total from plan counts, without summing amount_usd."""

    counts = clean["payments"]["plan"].value_counts()
    rebuilt = sum(counts[plan] * price for plan, price in PLAN_PRICES.items())

    assert rebuilt == pytest.approx(gross_revenue(clean["payments"]))


def test_reconcile_refunded_amount_against_fixed_plan_prices(clean):
    payments = clean["payments"]
    counts = payments.loc[payments["is_refunded"] == 1, "plan"].value_counts()
    rebuilt = sum(counts[plan] * price for plan, price in PLAN_PRICES.items())

    assert rebuilt == pytest.approx(refunded_amount(payments))


def test_reconcile_net_revenue_two_ways(clean):
    payments = clean["payments"]

    assert net_revenue(payments) == pytest.approx(
        gross_revenue(payments) - refunded_amount(payments)
    )


def test_reconcile_payment_counts_split_by_refund_flag(clean):
    payments = clean["payments"]
    refunded = payments["is_refunded"] == 1

    assert int(refunded.sum()) + int((~refunded).sum()) == len(payments)


# --- contract ----------------------------------------------------------------

def test_metrics_do_not_modify_the_clean_frames(clean):
    before = {name: df.copy() for name, df in clean.items()}

    metrics_summary(**clean)

    for name, df in clean.items():
        pd.testing.assert_frame_equal(df, before[name])


def test_summary_returns_all_six_metrics(clean):
    summary = metrics_summary(**clean)

    assert isinstance(summary, pd.DataFrame)
    assert summary["metric"].tolist() == [
        "total_users",
        "total_enrollments",
        "completion_rate",
        "gross_revenue",
        "refunded_amount",
        "net_revenue",
    ]
    assert summary["value"].notna().all()


def test_metrics_module_does_not_import_database_or_streamlit():
    """Metrics must read CSVs only, with no database and no UI code."""

    from src.paths import PROJECT_ROOT

    source = (PROJECT_ROOT / "src" / "metrics.py").read_text(encoding="utf-8")

    for forbidden in ("streamlit", "sqlalchemy", "src.database", "src.extract"):
        assert forbidden not in source
