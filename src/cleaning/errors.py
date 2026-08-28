"""Failures that must stop the pipeline."""

import pandas as pd


SAMPLE_SIZE = 5


class CleaningError(Exception):
    """A documented expectation failed, so cleaning must stop."""


def fail(rule: str, message: str, offending: pd.DataFrame) -> None:
    """Raise CleaningError naming the rule and showing representative rows."""

    sample = offending.head(SAMPLE_SIZE).to_string()

    raise CleaningError(
        f"[{rule}] {message}\n"
        f"Offending rows: {len(offending)}. "
        f"Showing up to {SAMPLE_SIZE}:\n{sample}"
    )
