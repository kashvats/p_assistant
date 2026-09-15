from __future__ import annotations
from urllib.parse import urlparse, unquote
import os, re, sqlite3
from .base import Tool
from ..security_policy import is_read_only_sql
from ..security_utils import redact_secrets


def _dsn(alias: str) -> str:
    key = "DB_" + "".join(c if c.isalnum() else "_" for c in alias.upper()) + "_URL"
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"No database DSN configured for alias '{alias}' ({key}).")
    return value


def _sqlite_readonly_connection(dsn: str):
    raw = dsn.replace('sqlite:///', '', 1)
    raw = unquote(raw.split('?', 1)[0])
    if raw == ':memory:':
        conn = sqlite3.connect(':memory:')
    else:
        # URI mode=ro is enforced by SQLite itself, in addition to query_only below.
        conn = sqlite3.connect(f'file:{raw}?mode=ro', uri=True, timeout=10)
    conn.execute('PRAGMA query_only=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def _sql_query(dsn: str, sql: str, limit: int):
    p = urlparse(dsn)
    scheme = p.scheme.split("+")[0]
    transaction_started = False
    if scheme == "sqlite":
        conn = _sqlite_readonly_connection(dsn)
    elif scheme in {"postgresql", "postgres"}:
        import psycopg
        conn = psycopg.connect(dsn, connect_timeout=5)
        conn.execute('BEGIN READ ONLY')
        transaction_started = True
    elif scheme == "mysql":
        import pymysql
        conn = pymysql.connect(host=p.hostname, port=p.port or 3306, user=p.username, password=p.password,
                               database=(p.path or "/").lstrip("/"), connect_timeout=5, read_timeout=15,
                               autocommit=False)
        cur0 = conn.cursor()
        cur0.execute('START TRANSACTION READ ONLY')
        cur0.close()
        transaction_started = True
    else:
        raise ValueError(f"Unsupported SQL scheme: {scheme}")

    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(limit)
        return {"columns": cols, "rows": [list(r) for r in rows], "truncated": len(rows) >= limit}
    finally:
        if transaction_started:
            try:
                conn.rollback()
            except Exception:
                pass
        conn.close()


def _contains_forbidden_mongo_operator(value) -> bool:
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).lower() in {'$where', '$function', '$accumulator'}:
                return True
            if _contains_forbidden_mongo_operator(v):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_mongo_operator(v) for v in value)
    return False


def _mongo_find(dsn: str, database: str, collection: str, filter_doc: dict, limit: int):
    from pymongo import MongoClient
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', database or '') or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', collection or ''):
        raise ValueError('Database/collection name contains unsupported characters.')
    if _contains_forbidden_mongo_operator(filter_doc):
        raise ValueError('Server-side JavaScript MongoDB operators are blocked in read-only mode.')
    client = MongoClient(dsn, serverSelectionTimeoutMS=5000)
    try:
        docs = list(client[database][collection].find(filter_doc).limit(limit))
        for d in docs:
            d["_id"] = str(d.get("_id"))
        return docs
    finally:
        client.close()


def build_database_tools(config: dict) -> list[Tool]:
    max_rows = int(config.get("policy", {}).get("max_db_rows", 200))

    def db_query(alias: str, sql: str, limit: int = 100):
        if not is_read_only_sql(sql):
            return {"ok": False, "blocked": True, "error": "Only one deterministic read-only SQL statement is allowed."}
        dsn = _dsn(alias)
        if dsn.startswith("mongodb"):
            return {"ok": False, "error": "Use mongo_find for MongoDB."}
        try:
            return {"ok": True, **_sql_query(dsn, sql, min(max(1, limit), max_rows))}
        except Exception as e:
            return {"ok": False, "error": redact_secrets(e, 1200)}

    def mongo_find(alias: str, database: str, collection: str, filter: dict | None = None, limit: int = 50):
        dsn = _dsn(alias)
        if not dsn.startswith("mongodb"):
            return {"ok": False, "error": "Configured DSN is not MongoDB."}
        try:
            return {"ok": True, "documents": _mongo_find(dsn, database, collection, filter or {}, min(max(1, limit), max_rows))}
        except Exception as e:
            return {"ok": False, "error": redact_secrets(e, 1200)}

    return [
        Tool("db_query", "Run one read-only SQL query against a configured database alias. Parser checks and database-level read-only mode are both enforced.",
             {"type":"object","properties":{"alias":{"type":"string"},"sql":{"type":"string"},"limit":{"type":"integer","default":100}},"required":["alias","sql"]}, db_query),
        Tool("mongo_find", "Read documents from MongoDB with a bounded find(). Server-side JavaScript operators and writes are blocked.",
             {"type":"object","properties":{"alias":{"type":"string"},"database":{"type":"string"},"collection":{"type":"string"},"filter":{"type":"object"},"limit":{"type":"integer","default":50}},"required":["alias","database","collection"]}, mongo_find),
    ]
