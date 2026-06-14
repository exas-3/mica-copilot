"""Postgres connection pool with the pgvector type adapter registered.

Mirrors the singleton-pool pattern used in the sibling `mica-dashboard` (lib/db.js),
ported to psycopg 3. Connections are configured once so `vector` columns round-trip
as Python lists / numpy arrays automatically.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from app.config import get_settings

_pool: ConnectionPool | None = None


def _configure(conn: psycopg.Connection) -> None:
    # pgvector must exist before the type can be registered; ingest/migration creates it.
    try:
        register_vector(conn)
    except psycopg.Error:
        # Extension not installed yet (e.g. before first migration). Safe to ignore here.
        conn.rollback()


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=10,
            timeout=10,
            configure=_configure,
            open=True,
        )
    return _pool


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
