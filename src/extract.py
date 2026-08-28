"""Load approved raw tables from PostgreSQL."""

import pandas as pd
from sqlalchemy import Engine, text

from src.database import get_engine


ALLOWED_TABLES = {
    "users",
    "enrollments",
    "payments",
}


def load_raw_table(
    table_name: str,
    engine: Engine | None = None,
) -> pd.DataFrame:
    """Load one approved raw table into a pandas DataFrame."""

    if table_name not in ALLOWED_TABLES:
        allowed = ", ".join(sorted(ALLOWED_TABLES))
        raise ValueError(
            f"Table {table_name!r} is not allowed. "
            f"Allowed tables: {allowed}."
        )

    active_engine = engine or get_engine()

    # The table name is interpolated only after allowlist validation.
    query = text(f'SELECT * FROM "{table_name}"')

    return pd.read_sql_query(query, active_engine)


def load_source_tables(
    engine: Engine | None = None,
) -> dict[str, pd.DataFrame]:
    """Load all source tables required by the cleaning pipeline."""

    active_engine = engine or get_engine()

    return {
        table_name: load_raw_table(table_name, active_engine)
        for table_name in sorted(ALLOWED_TABLES)
    }


if __name__ == "__main__":
    tables = load_source_tables()

    for name, dataframe in tables.items():
        print(f"{name}: {len(dataframe):,} rows")