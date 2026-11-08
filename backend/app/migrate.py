"""Tiny additive migration: create new tables and add any model columns missing from an
existing database (SQLite or Postgres). Never drops or rewrites data."""
import logging

from sqlalchemy import inspect, text

from .db import Base, engine

log = logging.getLogger(__name__)


def _default_sql(col) -> str:
    d = col.default.arg if col.default is not None and not callable(col.default.arg) else None
    if d is None:
        if col.type.python_type in (dict,):
            return " DEFAULT '{}'"
        if col.type.python_type in (list,):
            return " DEFAULT '[]'"
        return ""
    if isinstance(d, bool):
        return f" DEFAULT {'1' if d else '0'}" if engine.dialect.name == "sqlite" else f" DEFAULT {str(d).upper()}"
    if isinstance(d, (int, float)):
        return f" DEFAULT {d}"
    return " DEFAULT '" + str(d).replace("'", "''") + "'"


def upgrade():
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                coltype = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}{_default_sql(col)}'))
                log.info("migrate: added %s.%s", table.name, col.name)
