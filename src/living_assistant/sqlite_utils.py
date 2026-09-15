from __future__ import annotations

from pathlib import Path
import sqlite3
import threading


class ThreadLocalSQLite:
    """Small sqlite3.Connection-like proxy backed by one connection per thread.

    The assistant shares stores between FastAPI worker threads and the daemon. A raw
    check_same_thread=False connection still has transaction/cursor state shared across
    threads; this proxy avoids that class of API misuse while WAL/busy_timeout handle
    normal cross-connection contention.
    """
    def __init__(self, path: str | Path, *, foreign_keys: bool = False, timeout: float = 30.0):
        self.path = str(path)
        self.foreign_keys = bool(foreign_keys)
        self.timeout = float(timeout)
        self._local = threading.local()
        self._row_factory = sqlite3.Row

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=self.timeout, check_same_thread=True)
            conn.row_factory = self._row_factory
            conn.execute('PRAGMA busy_timeout=5000')
            if self.path != ':memory:':
                try:
                    conn.execute('PRAGMA journal_mode=WAL')
                except sqlite3.DatabaseError:
                    pass
            if self.foreign_keys:
                conn.execute('PRAGMA foreign_keys=ON')
            self._local.conn = conn
        return conn

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._row_factory = value
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            conn.row_factory = value

    def execute(self, *args, **kwargs):
        return self._connection().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._connection().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._connection().executescript(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        return self._connection().cursor(*args, **kwargs)

    def commit(self):
        return self._connection().commit()

    def rollback(self):
        return self._connection().rollback()

    def close(self):
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            try:
                conn.close()
            finally:
                self._local.conn = None

    def __getattr__(self, name):
        return getattr(self._connection(), name)
