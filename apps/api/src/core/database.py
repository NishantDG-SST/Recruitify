from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Optional, Sequence

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - optional dependency
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass(frozen=True)
class Database:
    dsn: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.dsn)

    @contextmanager
    def connection(self) -> Generator["psycopg.Connection", None, None]:
        if not self.dsn:
            raise RuntimeError("DATABASE_DSN is not configured")
        if psycopg is None:
            raise RuntimeError("psycopg is required") from _IMPORT_ERROR
        with psycopg.connect(self.dsn) as conn:
            yield conn

    def execute(self, query: str, params: Sequence[object]) -> None:
        if not self.is_configured:
            return None
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()

    def fetchone(self, query: str, params: Sequence[object]) -> Optional[tuple]:
        if not self.is_configured:
            return None
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
                conn.commit()
                return row

    def fetchall(self, query: str, params: Sequence[object]) -> list[tuple]:
        if not self.is_configured:
            return []
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.commit()
                return rows


def get_database(dsn: Optional[str]) -> Database:
    return Database(dsn=dsn)
