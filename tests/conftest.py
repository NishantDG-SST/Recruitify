import os
from pathlib import Path

import pytest
import psycopg


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> None:
    dsn = os.getenv("DATABASE_DSN")
    if not dsn:
        pytest.skip("DATABASE_DSN is not set")
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    seed_path = Path(__file__).resolve().parent / "sql" / "seed.sql"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(schema_path.read_text())
            cursor.execute(seed_path.read_text())
        conn.commit()
