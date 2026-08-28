"""Step 0: the three raw tables load with the documented row counts."""

import pandas as pd
import pytest

from src.database import get_engine
from src.extract import load_raw_table, load_source_tables
from src.paths import EXPECTED_RAW_ROWS


@pytest.fixture(scope="module")
def raw_tables():
    return load_source_tables(get_engine())


def test_all_source_tables_are_loaded(raw_tables):
    assert set(raw_tables) == set(EXPECTED_RAW_ROWS)
    assert all(isinstance(df, pd.DataFrame) for df in raw_tables.values())


@pytest.mark.parametrize("table_name", sorted(EXPECTED_RAW_ROWS))
def test_raw_row_counts(raw_tables, table_name):
    assert len(raw_tables[table_name]) == EXPECTED_RAW_ROWS[table_name]


def test_unknown_table_is_rejected():
    with pytest.raises(ValueError, match="is not allowed"):
        load_raw_table("secrets")
