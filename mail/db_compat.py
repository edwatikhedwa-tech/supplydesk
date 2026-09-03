"""
SQLite/Postgres DB-API compatibility shim, extracted from mail/repository.py
(TASK-BOUNDED-MAIL-REPOSITORY-DB-COMPAT-EXTRACT-20260903) as Pass 1 of
splitting mail/repository.py by responsibility, following a read-only
structural audit. No behavior changed: every class/function below is moved
byte-for-byte from mail/repository.py.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Iterable


class ManagedConnection(sqlite3.Connection):
    """Close every per-operation SQLite handle, including on Windows."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class CompatRow(dict):
    """Mapping row that also supports SQLite-style numeric indexes."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _postgres_row_factory(cursor: Any):
    columns = [column.name for column in (cursor.description or [])]

    def make_row(values: tuple[Any, ...]) -> CompatRow:
        return CompatRow(zip(columns, values))

    return make_row


def _adapt_postgres_sql(sql: str) -> str:
    """Translate the small SQLite dialect surface used by this repository."""
    adapted = sql.replace("BEGIN IMMEDIATE", "BEGIN")
    adapted = adapted.replace("last_insert_rowid()", "LASTVAL()")
    # «OR IGNORE» в SQLite молча пропускает КАКОЕ УГОДНО нарушение ограничения,
    # а не только по конкретной колонке — ровно то же самое делает
    # ON CONFLICT DO NOTHING без указания цели конфликта в Postgres. Раньше
    # это подставлялось только для одного жёстко зашитого запроса
    # (_seed_request), и любой другой INSERT OR IGNORE, добавленный позже
    # (mail_message_reads — отметка о прочтении письма), на Postgres превращался
    # в обычный INSERT и падал с ошибкой уникальности при повторной вставке.
    was_insert_or_ignore = bool(re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO", adapted, flags=re.IGNORECASE))
    adapted = re.sub(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", adapted, count=1, flags=re.IGNORECASE)
    if was_insert_or_ignore and "ON CONFLICT" not in adapted.upper():
        adapted = adapted.rstrip() + " ON CONFLICT DO NOTHING"
    # The repository uses SQLite-style '?' parameters, while psycopg parses
    # every '%' in a query as part of its own placeholder syntax. Escape SQL
    # wildcard literals (for example LIKE 'mailer-daemon@%') before converting
    # the repository parameters to psycopg's '%s' form.
    return adapted.replace("%", "%%").replace("?", "%s")


class PostgresCursor:
    def __init__(self, cursor: Any, connection: Any) -> None:
        self._cursor = cursor
        self._connection = connection

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    @property
    def lastrowid(self) -> int:
        row = self._connection.execute("SELECT LASTVAL()").fetchone()
        return int(row[0])


class PostgresConnection:
    """Small DB-API compatibility layer for the existing SQLite repository."""

    def __init__(self, raw_connection: Any) -> None:
        self.raw = raw_connection

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        try:
            if exc_type:
                self.raw.rollback()
            else:
                self.raw.commit()
        finally:
            self.raw.close()

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> PostgresCursor:
        params = tuple(parameters)
        cursor = self.raw.execute(_adapt_postgres_sql(sql), params)
        return PostgresCursor(cursor, self)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]) -> None:
        # psycopg's Connection.executemany doesn't exist on the cursor-less
        # wrapper here, and sqlite3.Connection.executemany takes one prepared
        # statement — the loop is equivalent and keeps the same call surface
        # for both backends.
        for parameters in seq_of_parameters:
            self.execute(sql, parameters)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()


def _postgres_migration_sql(script: str) -> str:
    script = re.sub(r"^\s*PRAGMA[^;]+;", "", script, flags=re.IGNORECASE | re.MULTILINE)
    script = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", script, flags=re.IGNORECASE)
    return re.sub(r"\bBLOB\b", "BYTEA", script, flags=re.IGNORECASE)
