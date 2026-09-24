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
        self._connections: set[sqlite3.Connection] = set()
        self._connections_lock = threading.RLock()
        self._generation = 0

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        local_generation = getattr(self._local, 'generation', -1)
        with self._connections_lock:
            generation = self._generation
        if conn is None or local_generation != generation:
            # Connections remain thread-local for normal use, but disabling SQLite's
            # thread-affinity check lets close_all() safely close idle worker
            # connections during shutdown/test cleanup. No connection is shared for
            # query execution between threads.
            conn = sqlite3.connect(self.path, timeout=self.timeout, check_same_thread=False)
            conn.row_factory = self._row_factory
            conn.execute('PRAGMA busy_timeout=5000')
            if self.path != ':memory:':
                try:
                    conn.execute('PRAGMA journal_mode=WAL')
                except sqlite3.DatabaseError:
                    pass
            if self.foreign_keys:
                conn.execute('PRAGMA foreign_keys=ON')
            with self._connections_lock:
                # close_all() may have advanced the generation while this connection
                # was being initialized. If so, discard it and retry rather than
                # publishing a connection from the retired generation.
                if generation != self._generation:
                    conn.close()
                    self._local.conn = None
                    self._local.generation = -1
                    return self._connection()
                self._connections.add(conn)
                self._local.conn = conn
                self._local.generation = generation
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
                with self._connections_lock:
                    self._connections.discard(conn)
                self._local.conn = None
                self._local.generation = -1

    def close_all(self) -> int:
        """Close every connection created by this proxy and invalidate thread-local caches.

        Callers should use this during quiescent shutdown/cleanup, not while database
        operations are actively running. The generation bump ensures worker threads
        cannot later reuse a connection that another thread closed here.
        """
        with self._connections_lock:
            connections = list(self._connections)
            self._connections.clear()
            self._generation += 1

        closed = 0
        for conn in connections:
            try:
                conn.close()
                closed += 1
            except sqlite3.Error:
                # A connection may already have been closed explicitly; cleanup is
                # best-effort and must not prevent the remaining handles from closing.
                pass

        self._local.conn = None
        self._local.generation = self._generation
        return closed

    def __enter__(self):
        return self._connection().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._connection().__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        return getattr(self._connection(), name)

