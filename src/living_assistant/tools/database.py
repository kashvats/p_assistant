from __future__ import annotations
from urllib.parse import urlparse
import os, sqlite3
from .base import Tool
from ..security_policy import is_read_only_sql

def _dsn(alias: str) -> str:
    key = "DB_" + "".join(c if c.isalnum() else "_" for c in alias.upper()) + "_URL"
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"No database DSN configured for alias '{alias}' ({key}).")
    return value

def _sql_query(dsn: str, sql: str, limit: int):
    p = urlparse(dsn)
    scheme = p.scheme.split("+")[0]
    if scheme == "sqlite":
        path = dsn.replace("sqlite:///", "", 1)
        conn = sqlite3.connect(path)
    elif scheme in {"postgresql","postgres"}:
        import psycopg
        conn = psycopg.connect(dsn, connect_timeout=5)
    elif scheme == "mysql":
        import pymysql
        conn = pymysql.connect(host=p.hostname, port=p.port or 3306, user=p.username, password=p.password,
                               database=(p.path or "/").lstrip("/"), connect_timeout=5, read_timeout=15)
    else:
        raise ValueError(f"Unsupported SQL scheme: {scheme}")

    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(limit)
        return {"columns":cols,"rows":[list(r) for r in rows],"truncated":len(rows) >= limit}
    finally:
        conn.close()

def _mongo_find(dsn: str, database: str, collection: str, filter_doc: dict, limit: int):
    from pymongo import MongoClient
    client = MongoClient(dsn, serverSelectionTimeoutMS=5000)
    try:
        docs = list(client[database][collection].find(filter_doc).limit(limit))
        for d in docs:
            d["_id"] = str(d.get("_id"))
        return docs
    finally:
        client.close()

def build_database_tools(config: dict) -> list[Tool]:
    max_rows = int(config.get("policy",{}).get("max_db_rows",200))

    def db_query(alias: str, sql: str, limit: int = 100):
        if not is_read_only_sql(sql):
            return {"ok":False,"blocked":True,"error":"Only read-only SQL is allowed by default."}
        dsn = _dsn(alias)
        if dsn.startswith("mongodb"):
            return {"ok":False,"error":"Use mongo_find for MongoDB."}
        try:
            return {"ok":True, **_sql_query(dsn, sql, min(limit,max_rows))}
        except Exception as e:
            return {"ok":False,"error":str(e)}

    def mongo_find(alias: str, database: str, collection: str, filter: dict | None = None, limit: int = 50):
        dsn = _dsn(alias)
        if not dsn.startswith("mongodb"):
            return {"ok":False,"error":"Configured DSN is not MongoDB."}
        try:
            return {"ok":True,"documents":_mongo_find(dsn,database,collection,filter or {},min(limit,max_rows))}
        except Exception as e:
            return {"ok":False,"error":str(e)}

    return [
        Tool("db_query", "Run a read-only SQL query against a configured database alias. DML/DDL is blocked.",
             {"type":"object","properties":{"alias":{"type":"string"},"sql":{"type":"string"},"limit":{"type":"integer","default":100}},"required":["alias","sql"]}, db_query),
        Tool("mongo_find", "Read documents from MongoDB with a bounded find(). No writes.",
             {"type":"object","properties":{"alias":{"type":"string"},"database":{"type":"string"},"collection":{"type":"string"},"filter":{"type":"object"},"limit":{"type":"integer","default":50}},"required":["alias","database","collection"]}, mongo_find),
    ]
