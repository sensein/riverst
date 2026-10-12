from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class KivaDatabase:
    """Connection and transaction boundary for the KIVA SQLite store."""

    def __init__(self, path: str | Path):
        self.path = str(path)

    def initialize(self, schema_path: str | Path) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(Path(schema_path).read_text(encoding="utf-8"))
        self._migrate_roles()

    def _migrate_roles(self) -> None:
        """Widen kiva_role's CHECK to allow 'tester'/'developer' on pre-existing DBs.

        SQLite cannot ALTER a CHECK constraint, so rebuild the tiny lookup table when the
        new roles aren't permitted yet (FK off during the swap; kiva_person_role rows are
        preserved and re-bind by name), then (re)seed the roles. Idempotent and a no-op on
        fresh DBs whose schema already has the widened CHECK.
        """
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.isolation_level = None  # autocommit, so PRAGMA + explicit BEGIN behave predictably
        try:
            row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='kiva_role'"
            ).fetchone()
            if row and "'tester'" not in row["sql"]:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("BEGIN")
                connection.execute(
                    """CREATE TABLE kiva_role_new (
                         role_code TEXT PRIMARY KEY
                           CHECK (role_code IN ('learner','guardian','instructor','tester','developer')),
                         display_name TEXT NOT NULL UNIQUE
                       )"""
                )
                connection.execute("INSERT INTO kiva_role_new SELECT * FROM kiva_role")
                connection.execute("DROP TABLE kiva_role")
                connection.execute("ALTER TABLE kiva_role_new RENAME TO kiva_role")
                connection.execute("COMMIT")
                connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "INSERT OR IGNORE INTO kiva_role (role_code, display_name) VALUES ('tester','Tester'),('developer','Developer')"
            )
        finally:
            connection.close()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
