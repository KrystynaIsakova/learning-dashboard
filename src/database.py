"""Create and verify a read-only PostgreSQL connection."""

import os

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text


def get_engine() -> Engine:
    """Create a SQLAlchemy engine using DATABASE_URL from .env."""

    load_dotenv()

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. "
            "Create a .env file based on .env.example."
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def test_connection(engine: Engine | None = None) -> None:
    """Run a harmless query to verify the database connection."""

    active_engine = engine or get_engine()

    with active_engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = result.scalar_one()

    if value != 1:
        raise RuntimeError("Database connection test returned an unexpected result.")


if __name__ == "__main__":
    test_connection()
    print("Database connection successful.")