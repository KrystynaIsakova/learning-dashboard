"""Step 5: the cleaning report (docs/cleaning_rules.md, section 5)."""

import pandas as pd
import pytest

from src.checks import CheckResult, run_check, run_final_checks
from src.cleaning.errors import CleaningError
from src.report import TRANSFORMATION_LINES, build_report


STATS = {
    "users": {
        "raw_rows": 40_000,
        "clean_rows": 40_000,
        "countries_unified": 691,
        "countries_filled_unknown": 800,
    },
    "enrollments": {
        "raw_rows": 94_705,
        "clean_rows": 94_686,
        "enrolled_at_reformatted": 3_786,
        "progress_pct_fixed": 277,
        "completed_at_cleared": 356,
        "certified_without_completion_rejected": 19,
        "duplicates_removed": 0,
    },
    "payments": {
        "raw_rows": 87_924,
        "clean_rows": 87_884,
        "payments_unknown_user_rejected": 40,
    },
}

PASSING = [CheckResult("перевірка A", True), CheckResult("перевірка B", True)]


def test_row_table_shows_raw_clean_and_difference():
    report = build_report(STATS, PASSING)

    assert "| users | 40 000 | 40 000 | 0 |" in report
    assert "| enrollments | 94 705 | 94 686 | 19 |" in report
    assert "| payments | 87 924 | 87 884 | 40 |" in report


@pytest.mark.parametrize(("label", "table", "key"), TRANSFORMATION_LINES)
def test_every_required_counter_is_reported(label, table, key):
    report = build_report(STATS, PASSING)

    assert label in report


def test_zero_duplicates_is_reported_as_a_real_value():
    report = build_report(STATS, PASSING)

    assert "| Повних дублікатів enrollment видалено | 0 |" in report


def test_failed_check_is_never_reported_as_passed():
    checks = [CheckResult("перевірка A", True), CheckResult("перевірка B", False, "boom")]

    report = build_report(STATS, checks)

    assert "НЕ ПРОЙДЕНО — boom" in report
    assert "Пройдено: 1. Не пройдено: 1." in report


def test_run_check_records_failure_instead_of_raising():
    def failing():
        raise CleaningError("something broke")

    result = run_check("перевірка", failing)

    assert result.passed is False
    assert "something broke" in result.detail


def test_run_check_records_success_only_after_running():
    calls = []

    result = run_check("перевірка", lambda: calls.append(1))

    assert calls == [1]
    assert result.passed is True


def test_final_checks_detect_a_broken_frame():
    """A deliberately broken frame must produce failures, not silent passes."""

    users = pd.DataFrame(
        {
            "user_id": ["U1", "U1"],
            "signup_date": pd.to_datetime(["2021-01-01", "2021-01-01"]),
            "country": ["USA", "Unknown"],
        }
    )
    enrollments = pd.DataFrame(
        {
            "enrollment_id": ["E1"],
            "user_id": ["U404"],
            "enrolled_at": pd.to_datetime(["2022-01-01"]),
            "completed_at": pd.to_datetime([None]),
            "last_week_reached": [1],
            "n_weeks": [4],
            "progress_pct": [25.0],
            "funnel_state": ["viewed"],
            "is_certified": [0],
        }
    )
    payments = pd.DataFrame(
        {
            "payment_id": ["P1"],
            "user_id": ["U1"],
            "paid_at": pd.to_datetime(["2020-01-01"]),
            "amount_usd": [49.0],
            "plan": ["monthly"],
            "is_refunded": [0],
        }
    )

    results = run_final_checks(users, enrollments, payments)
    failed = {check.name for check in results if not check.passed}

    assert "users: ключ унікальний і без пропусків" in failed
    assert "users: country без пропусків і без USA/DE/UK" in failed
    assert "enrollments: усі user_id присутні в users" in failed
    assert "payments: платіж не раніше за signup" in failed
    assert "payments: повернені платежі залишилися в таблиці" in failed
