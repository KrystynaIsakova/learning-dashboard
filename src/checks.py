"""Run the final checks and record what actually happened.

The cleaning functions raise on the first failure, which is what stops the
pipeline. These wrappers run the same checks while recording each outcome, so
the report can state which checks ran instead of claiming a blanket success.
"""

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src.cleaning.enrollments import (
    check_certification,
    check_user_reference,
    check_week_and_progress,
)
from src.cleaning.errors import CleaningError
from src.cleaning.payments import check_paid_after_signup, check_payment_key
from src.cleaning.users import check_user_key


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def run_check(name: str, check: Callable[[], None]) -> CheckResult:
    """Execute one check and record its outcome instead of propagating it."""

    try:
        check()
    except CleaningError as error:
        return CheckResult(name, False, str(error).splitlines()[0])

    return CheckResult(name, True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CleaningError(message)


def run_final_checks(
    clean_users: pd.DataFrame,
    clean_enrollments: pd.DataFrame,
    clean_payments: pd.DataFrame,
) -> list[CheckResult]:
    """Run every check listed in section 6 against the cleaned frames."""

    checks: dict[str, Callable[[], None]] = {
        "users: ключ унікальний і без пропусків": lambda: check_user_key(clean_users),
        "users: signup_date містить валідні дати": lambda: _require(
            clean_users["signup_date"].notna().all(),
            "signup_date contains missing values.",
        ),
        "users: country без пропусків і без USA/DE/UK": lambda: _require(
            clean_users["country"].notna().all()
            and not clean_users["country"].isin(["USA", "DE", "UK"]).any(),
            "country still contains missing values or abbreviations.",
        ),
        "enrollments: ключ унікальний і без пропусків": lambda: _require(
            clean_enrollments["enrollment_id"].notna().all()
            and not clean_enrollments["enrollment_id"].duplicated().any(),
            "enrollment_id is missing or not unique.",
        ),
        "enrollments: усі user_id присутні в users": lambda: check_user_reference(
            clean_enrollments, clean_users
        ),
        "enrollments: дати перетворені": lambda: _require(
            clean_enrollments["enrolled_at"].notna().all(),
            "enrolled_at contains invalid dates.",
        ),
        "enrollments: немає completed_at раніше enrolled_at": lambda: _require(
            not (
                clean_enrollments["completed_at"].notna()
                & (clean_enrollments["completed_at"] < clean_enrollments["enrolled_at"])
            ).any(),
            "completed_at is earlier than enrolled_at.",
        ),
        "enrollments: прогрес у діапазоні та відповідає формулі": lambda: (
            check_week_and_progress(clean_enrollments)
        ),
        "enrollments: статуси сертифікації узгоджені": lambda: check_certification(
            clean_enrollments
        ),
        "payments: ключ унікальний і без пропусків": lambda: check_payment_key(
            clean_payments
        ),
        "payments: усі user_id присутні в users": lambda: _require(
            clean_payments["user_id"].isin(set(clean_users["user_id"])).all(),
            "payments reference unknown user_id values.",
        ),
        "payments: paid_at містить валідні дати": lambda: _require(
            clean_payments["paid_at"].notna().all(),
            "paid_at contains invalid dates.",
        ),
        "payments: платіж не раніше за signup": lambda: check_paid_after_signup(
            clean_payments, clean_users
        ),
        "payments: повернені платежі залишилися в таблиці": lambda: _require(
            (clean_payments["is_refunded"] == 1).any(),
            "no refunded payments remain in the clean table.",
        ),
    }

    return [run_check(name, check) for name, check in checks.items()]
