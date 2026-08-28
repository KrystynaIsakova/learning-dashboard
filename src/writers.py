"""Write cleaning results to disk.

File writing lives here only. Cleaning functions never touch the filesystem.
"""

from pathlib import Path

import pandas as pd

from src.paths import CLEAN_DIR, REJECTED_DIR, REPORTS_DIR


DATE_FORMAT = "%Y-%m-%d"


def _write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    # Format dates ourselves: to_csv(date_format=...) writes NaT as a quoted
    # empty string, and missing dates must stay genuinely empty.
    formatted = df.copy()
    for column in formatted.columns:
        if pd.api.types.is_datetime64_any_dtype(formatted[column]):
            formatted[column] = formatted[column].dt.strftime(DATE_FORMAT)

    formatted.to_csv(path, index=False)
    return path


def write_clean_csv(df: pd.DataFrame, name: str) -> Path:
    """Save a cleaned table to data/clean/<name>.csv."""

    return _write_csv(df, CLEAN_DIR / f"{name}.csv")


def write_rejected_csv(df: pd.DataFrame, name: str) -> Path:
    """Save rejected records to data/rejected/<name>.csv."""

    return _write_csv(df, REJECTED_DIR / f"{name}.csv")


def write_report(text: str, name: str = "cleaning_report") -> Path:
    """Save a report to reports/<name>.md."""

    path = REPORTS_DIR / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
