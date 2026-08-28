"""Run the cleaning pipeline end to end.

Loading, cleaning and writing are kept apart: cleaning functions receive
DataFrames and return DataFrames, while this module owns the database and the
filesystem.
"""

from src.cleaning.enrollments import clean_enrollments
from src.cleaning.payments import clean_payments
from src.cleaning.users import clean_users
from src.checks import run_final_checks
from src.database import get_engine
from src.extract import load_source_tables
from src.report import build_report
from src.writers import write_clean_csv, write_rejected_csv, write_report


def run_pipeline() -> dict[str, dict[str, int]]:
    """Clean every table, write the clean CSVs and return the report counts."""

    raw = load_source_tables(get_engine())

    clean_users_df, users_stats = clean_users(raw["users"])
    write_clean_csv(clean_users_df, "users")

    clean_enrollments_df, rejected_enrollments_df, enrollments_stats = (
        clean_enrollments(raw["enrollments"], clean_users_df)
    )
    write_clean_csv(clean_enrollments_df, "enrollments")
    write_rejected_csv(
        rejected_enrollments_df, "enrollments_certified_without_completion"
    )

    clean_payments_df, rejected_payments_df, payments_stats = clean_payments(
        raw["payments"], clean_users_df
    )
    write_clean_csv(clean_payments_df, "payments")
    write_rejected_csv(rejected_payments_df, "payments_unknown_user")

    stats = {
        "users": users_stats,
        "enrollments": enrollments_stats,
        "payments": payments_stats,
    }

    checks = run_final_checks(clean_users_df, clean_enrollments_df, clean_payments_df)
    write_report(build_report(stats, checks))

    return stats


if __name__ == "__main__":
    for table, stats in run_pipeline().items():
        print(f"{table}: {stats}")
