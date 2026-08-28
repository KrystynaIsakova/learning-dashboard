"""Create and verify a read-only PostgreSQL connection."""

import os

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, event, text


def get_engine() -> Engine:
    """Create a SQLAlchemy engine using DATABASE_URL from .env."""

    load_dotenv()

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. "
            "Create a .env file based on .env.example."
        )

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    # Every transaction is marked read-only, so a stray write fails at the
    # server. This is done per transaction rather than per session: pooled Neon
    # endpoints reject the startup "options" parameter and may hand a session
    # setting to a different backend, so only a transaction-scoped SET holds.
    @event.listens_for(engine, "begin")
    def _enforce_read_only(connection):
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")

    return engine


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