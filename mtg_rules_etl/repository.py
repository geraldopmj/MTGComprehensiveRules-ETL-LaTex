from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from .models import RulesDocument


class DuckDBRulesRepository:
    TABLES = {"rule_groups", "rules"}

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(self.database_path))
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rule_groups (
                    id INTEGER NOT NULL,
                    effective_date DATE NOT NULL,
                    name TEXT NOT NULL,
                    PRIMARY KEY (id, effective_date)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    effective_date DATE NOT NULL,
                    name TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    PRIMARY KEY (id, effective_date)
                )
                """
            )
        finally:
            connection.close()

    def is_empty(self) -> bool:
        self.initialize()
        return self.count_rows("rules") == 0

    def latest_effective_date(self) -> date | None:
        self.initialize()
        connection = duckdb.connect(str(self.database_path))
        try:
            row = connection.execute("SELECT max(effective_date) FROM rules").fetchone()
            return row[0] if row else None
        finally:
            connection.close()

    def save_document(self, document: RulesDocument) -> None:
        self.initialize()
        connection = duckdb.connect(str(self.database_path))
        try:
            connection.execute("BEGIN TRANSACTION")
            connection.execute("DELETE FROM rules WHERE effective_date = ?", [document.effective_date])
            connection.execute("DELETE FROM rule_groups WHERE effective_date = ?", [document.effective_date])
            connection.executemany(
                "INSERT INTO rule_groups (id, effective_date, name) VALUES (?, ?, ?)",
                [(group.id, document.effective_date, group.name) for group in document.groups],
            )
            connection.executemany(
                """
                INSERT INTO rules (id, group_id, effective_date, name, rule_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        section.id,
                        section.group_id,
                        document.effective_date,
                        section.name,
                        section.rule_text,
                    )
                    for section in document.sections
                ],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def count_rows(self, table_name: str) -> int:
        if table_name not in self.TABLES:
            raise ValueError(f"Unknown table: {table_name}")
        self.initialize()
        connection = duckdb.connect(str(self.database_path))
        try:
            return int(connection.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0])
        finally:
            connection.close()

