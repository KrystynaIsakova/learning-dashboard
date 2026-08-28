"""Step 2: writing clean and rejected files."""

import pandas as pd
import pytest

from src import writers


@pytest.fixture(autouse=True)
def temp_output_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(writers, "CLEAN_DIR", tmp_path / "clean")
    monkeypatch.setattr(writers, "REJECTED_DIR", tmp_path / "rejected")
    monkeypatch.setattr(writers, "REPORTS_DIR", tmp_path / "reports")


def test_clean_csv_is_written_without_index():
    df = pd.DataFrame({"user_id": ["U1"], "country": ["Unknown"]})

    path = writers.write_clean_csv(df, "users")

    assert path.name == "users.csv"
    assert path.read_text(encoding="utf-8").splitlines()[0] == "user_id,country"


def test_dates_are_serialised_as_iso():
    df = pd.DataFrame({"signup_date": pd.to_datetime(["2021-01-03"])})

    path = writers.write_clean_csv(df, "users")

    assert path.read_text(encoding="utf-8").splitlines()[1] == "2021-01-03"


def test_empty_dates_stay_empty():
    df = pd.DataFrame(
        {
            "enrollment_id": ["E1", "E2"],
            "completed_at": pd.to_datetime([None, "2022-01-17"]),
        }
    )

    lines = writers.write_clean_csv(df, "enrollments").read_text(
        encoding="utf-8"
    ).splitlines()

    assert lines[1] == "E1,"
    assert lines[2] == "E2,2022-01-17"


def test_rejected_csv_goes_to_its_own_directory():
    df = pd.DataFrame({"payment_id": ["P1"]})

    path = writers.write_rejected_csv(df, "payments_unknown_user")

    assert path.parent.name == "rejected"
    assert path.exists()
