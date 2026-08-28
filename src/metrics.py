"""Metrics built on the cleaned CSV files (docs/metric_specification.md).

Metrics read only data/clean/. They never touch PostgreSQL, never write files
and never modify the cleaned data: every function works on the frame it is
given and returns a number or an aggregated DataFrame.
"""

import pandas as pd

from src.paths import CLEAN_DIR


CERTIFIED_FLAG = 1
REFUNDED = 1
NOT_REFUNDED = 0

METRIC_NAMES = [
    "total_users",
    "total_enrollments",
    "completion_rate",
    "gross_revenue",
    "refunded_amount",
    "net_revenue",
]


def load_clean_table(name: str) -> pd.DataFrame:
    """Read one cleaned CSV. This is the only way metrics obtain data."""

    if name not in {"users", "enrollments", "payments"}:
        raise ValueError(f"Unknown clean table: {name!r}.")

    return pd.read_csv(CLEAN_DIR / f"{name}.csv")


def load_clean_tables() -> dict[str, pd.DataFrame]:
    """Read every cleaned CSV needed by the metrics."""

    return {
        name: load_clean_table(name)
        for name in ("users", "enrollments", "payments")
    }


# --- Metric 1: total users ---------------------------------------------------

def total_users(users: pd.DataFrame) -> int:
    """Registered users. No filters: users without activity are included."""

    return int(users["user_id"].nunique())


# --- Metric 2: total enrollments --------------------------------------------

def total_enrollments(enrollments: pd.DataFrame) -> int:
    """Course enrolments, counted per enrolment rather than per user."""

    return int(enrollments["enrollment_id"].nunique())


# --- Metric 3: completion rate ----------------------------------------------

def completion_rate(enrollments: pd.DataFrame) -> float:
    """Share of enrolments that reached certification.

    The denominator is every enrolment, including 'registered' ones. Narrowing
    it to enrolments that started is a different metric, not this one.
    """

    if enrollments.empty:
        raise ValueError("completion_rate is undefined for an empty frame.")

    certified = (enrollments["is_certified"] == CERTIFIED_FLAG).sum()

    return float(certified / len(enrollments))


# --- Metrics 4-6: revenue ----------------------------------------------------

def gross_revenue(payments: pd.DataFrame) -> float:
    """All payments before refunds. Refunded payments are included in full."""

    return float(payments["amount_usd"].sum())


def refunded_amount(payments: pd.DataFrame) -> float:
    """Money returned to customers. Refunds are full, never partial."""

    return float(payments.loc[payments["is_refunded"] == REFUNDED, "amount_usd"].sum())


def net_revenue(payments: pd.DataFrame) -> float:
    """Revenue after refunds, for the whole period only.

    Deliberately not exposed per month: payments carry no refund date, so a
    monthly split would charge every refund to the month of the payment.
    """

    return float(
        payments.loc[payments["is_refunded"] == NOT_REFUNDED, "amount_usd"].sum()
    )


# --- Summary -----------------------------------------------------------------

def metrics_summary(
    users: pd.DataFrame,
    enrollments: pd.DataFrame,
    payments: pd.DataFrame,
) -> pd.DataFrame:
    """Return all six metrics as one aggregated frame."""

    values = {
        "total_users": total_users(users),
        "total_enrollments": total_enrollments(enrollments),
        "completion_rate": completion_rate(enrollments),
        "gross_revenue": gross_revenue(payments),
        "refunded_amount": refunded_amount(payments),
        "net_revenue": net_revenue(payments),
    }

    return pd.DataFrame(
        {"metric": METRIC_NAMES, "value": [values[name] for name in METRIC_NAMES]}
    )


if __name__ == "__main__":
    tables = load_clean_tables()
    print(metrics_summary(**tables).to_string(index=False))
