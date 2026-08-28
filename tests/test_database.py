"""Step 0: the database connection exists and is read-only."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError

from src.database import get_engine


@pytest.fixture(scope="module")
def engine():
    return get_engine()


def test_connection_works(engine):
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_session_is_read_only(engine):
    with engine.connect() as connection:
        setting = connection.execute(
            text("SHOW transaction_read_only")
        ).scalar_one()

    assert setting == "on"


def test_write_is_rejected(engine):
    """A write must fail at the server, not rely on our own discipline."""

    with pytest.raises(InternalError) as error:
        with engine.connect() as connection:
            connection.execute(text("CREATE TEMP TABLE claude_probe (id int)"))

    assert "read-only transaction" in str(error.value)
