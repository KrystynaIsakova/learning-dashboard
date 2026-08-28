"""Project paths and expected raw row counts."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
CLEAN_DIR = DATA_DIR / "clean"
REJECTED_DIR = DATA_DIR / "rejected"
REPORTS_DIR = PROJECT_ROOT / "reports"

# docs/cleaning_rules.md, section 5.
EXPECTED_RAW_ROWS = {
    "users": 40_000,
    "enrollments": 94_705,
    "payments": 87_924,
}


# docs/cleaning_rules.md, section 4.
EXPECTED_CLEAN_ROWS = {
    "users": 40_000,
    "enrollments": 94_686,
    "payments": 87_884,
}

EXPECTED_REJECTED_ROWS = {
    "enrollments_certified_without_completion": 19,
    "payments_unknown_user": 40,
}
