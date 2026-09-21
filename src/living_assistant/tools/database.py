from __future__ import annotations
from urllib.parse import urlparse, unquote
import os, re, sqlite3
from .base import Tool
from ..security_policy import is_read_only_sql
from ..security_utils import redact_secrets
from ..approval import ApprovalManager


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


_SQL_TOKEN_RE = re.compile(
    r'''--[^\n]*(?:\n|$)|/\*.*?\*/|'(?:''|[^'])*'|"(?:""|[^"])*"|`(?:``|[^`])*`|\[[^\]]*\]|[A-Za-z_][A-Za-z0-9_$]*|[(),.]''',
    re.S,
)
_SQL_FROM_END = {
    'where', 'group', 'order', 'having', 'limit', 'offset', 'fetch', 'union',
    'intersect', 'except', 'returning', 'window', 'qualify',
}


def _sql_tokens(sql: str) -> list[str]:
    tokens = []
    for match in _SQL_TOKEN_RE.finditer(sql):
        token = match.group(0)
        if token.startswith('--') or token.startswith('/*') or token.startswith("'"):
            continue
        tokens.append(token)
    return tokens


def _identifier_value(token: str) -> str:
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1].replace('""', '"')
    if token.startswith('`') and token.endswith('`'):
        return token[1:-1].replace('``', '`')
    if token.startswith('[') and token.endswith(']'):
        return token[1:-1]
    return token


def _is_identifier_token(token: str) -> bool:
    return bool(
        re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', token)
        or (token.startswith('"') and token.endswith('"'))
        or (token.startswith('`') and token.endswith('`'))
        or (token.startswith('[') and token.endswith(']'))
    )


def _cte_names(tokens: list[str]) -> set[str]:
    if not tokens or tokens[0].lower() != 'with':
        return set()
    names: set[str] = set()
    i = 1
    if i < len(tokens) and tokens[i].lower() == 'recursive':
        i += 1
    while i < len(tokens):
        if not _is_identifier_token(tokens[i]):
            break
        names.add(_identifier_value(tokens[i]).lower())
        i += 1
        if i < len(tokens) and tokens[i] == '(':
            depth = 1; i += 1
            while i < len(tokens) and depth:
                depth += tokens[i] == '('
                depth -= tokens[i] == ')'
                i += 1
        if i >= len(tokens) or tokens[i].lower() != 'as':
            break
        i += 1
        if i < len(tokens) and tokens[i].lower() == 'not':
            i += 1
        if i < len(tokens) and tokens[i].lower() == 'materialized':
            i += 1
        if i >= len(tokens) or tokens[i] != '(':
            break
        depth = 1; i += 1
        while i < len(tokens) and depth:
            depth += tokens[i] == '('
            depth -= tokens[i] == ')'
            i += 1
        if i < len(tokens) and tokens[i] == ',':
            i += 1
            continue
        break
    return names


def _referenced_sql_tables(sql: str) -> set[str]:
    """Return conservative FROM/JOIN table references for allowlist enforcement."""
    tokens = _sql_tokens(sql)
    ctes = _cte_names(tokens)
    refs: set[str] = set()
    from_active: dict[int, bool] = {}
    expect_table: dict[int, bool] = {}
    depth = 0
    i = 0
    while i < len(tokens):
        token = tokens[i]
        low = token.lower()
        if token == '(':
            if expect_table.get(depth):
                expect_table[depth] = False
            depth += 1
            i += 1
            continue
        if token == ')':
            from_active.pop(depth, None)
            expect_table.pop(depth, None)
            depth = max(0, depth - 1)
            i += 1
            continue
        if low == 'from':
            from_active[depth] = True
            expect_table[depth] = True
            i += 1
            continue
        if from_active.get(depth) and low in _SQL_FROM_END:
            from_active[depth] = False
            expect_table[depth] = False
            i += 1
            continue
        if low == 'join':
            from_active[depth] = True
            expect_table[depth] = True
            i += 1
            continue
        if token == ',' and from_active.get(depth):
            expect_table[depth] = True
            i += 1
            continue
        if expect_table.get(depth):
            if low in {'only', 'lateral'}:
                i += 1
                continue
            if not _is_identifier_token(token):
                # Unknown table-factor syntax is rejected by returning a sentinel.
                refs.add('__unparsed_table_reference__')
                expect_table[depth] = False
                i += 1
                continue
            parts = [_identifier_value(token)]
            j = i + 1
            while j + 1 < len(tokens) and tokens[j] == '.' and _is_identifier_token(tokens[j + 1]):
                parts.append(_identifier_value(tokens[j + 1]))
                j += 2
            name = '.'.join(parts).lower()
            if name not in ctes:
                refs.add(name)
            expect_table[depth] = False
            i = j
            continue
        i += 1
    return refs


def _database_alias_policy(config: dict, alias: str) -> tuple[dict | None, bool]:
    databases = config.get('databases', {}) or {}
    aliases = databases.get('aliases', {}) or {}
    policy = aliases.get(alias) if isinstance(aliases, dict) else None
    return policy if isinstance(policy, dict) else None, bool(databases.get('require_alias_policy', False))


def _allowed_table_names(policy: dict | None) -> set[str]:
    if not policy:
        return set()
    values = policy.get('allowed_tables', []) or []
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _sensitive_column_names(policy: dict | None) -> set[str]:
    if not policy:
        return set()
    values = policy.get('sensitive_columns', []) or []
    names: set[str] = set()
    for value in values:
        name = str(value).strip().lower()
        if not name:
            continue
        names.add(name)
        # A policy may use schema/table qualification; result-set column names normally do not.
        names.add(name.rsplit('.', 1)[-1])
    return names


def _select_expressions(tokens: list[str]) -> list[list[str]]:
    """Return SELECT-list expressions from every nesting level, inner and outer."""
    expressions: list[list[str]] = []
    depths: list[int] = []
    depth = 0
    for token in tokens:
        depths.append(depth)
        if token == '(':
            depth += 1
        elif token == ')':
            depth = max(0, depth - 1)

    end_words = {'from', 'union', 'intersect', 'except', 'order', 'limit', 'offset', 'fetch'}
    for start, token in enumerate(tokens):
        if token.lower() != 'select':
            continue
        base_depth = depths[start]
        current: list[str] = []
        nested = 0
        i = start + 1
        while i < len(tokens):
            item = tokens[i]
            item_depth = depths[i]
            low = item.lower()
            if item_depth == base_depth and nested == 0 and low in end_words:
                break
            if item == '(':
                nested += 1
            elif item == ')' and nested:
                nested -= 1
            if item == ',' and item_depth == base_depth and nested == 0:
                if current:
                    expressions.append(current)
                current = []
            else:
                current.append(item)
            i += 1
        if current:
            expressions.append(current)
    return expressions


def _expression_alias(expression: list[str]) -> str | None:
    """Return an explicit/implicit SELECT alias when it can be identified safely."""
    if not expression:
        return None
    depth = 0
    for idx, token in enumerate(expression):
        if token == '(':
            depth += 1
            continue
        if token == ')':
            depth = max(0, depth - 1)
            continue
        if depth == 0 and token.lower() == 'as' and idx + 1 < len(expression):
            candidate = expression[idx + 1]
            return _identifier_value(candidate).lower() if _is_identifier_token(candidate) else None

    # SQL permits an alias without AS. Only accept the last token when doing so is
    # unambiguous (the prior token is not a qualification dot).
    last = expression[-1]
    if _is_identifier_token(last) and len(expression) >= 2 and expression[-2] != '.':
        return _identifier_value(last).lower()
    return None


def _expression_identifiers(expression: list[str]) -> set[str]:
    names: set[str] = set()
    alias = _expression_alias(expression)
    for token in expression:
        if not _is_identifier_token(token):
            continue
        value = _identifier_value(token).lower()
        if value in {'select', 'distinct', 'all', 'as'}:
            continue
        names.add(value)
    if alias:
        names.discard(alias)
    return names


def _redact_sql_result(sql: str, result: dict, policy: dict | None) -> dict:
    sensitive = _sensitive_column_names(policy)
    if not sensitive:
        return result

    columns = [str(c) for c in (result.get('columns') or [])]
    rows = result.get('rows') or []
    if not columns or not rows:
        return result

    tokens = _sql_tokens(sql)
    expressions = _select_expressions(tokens)

    # Propagate sensitivity through aliases (including aliases created inside a
    # subquery/CTE and referenced by an outer SELECT).
    derived = set(sensitive)
    changed = True
    while changed:
        changed = False
        for expression in expressions:
            if _expression_identifiers(expression) & derived:
                alias = _expression_alias(expression)
                if alias and alias not in derived:
                    derived.add(alias)
                    changed = True

    redacted_indexes = {
        idx for idx, column in enumerate(columns)
        if column.strip().lower() in derived or column.strip().lower().rsplit('.', 1)[-1] in derived
    }

    # If a sensitive identifier is used anywhere in the query but no returned
    # column can be mapped confidently, redact the whole row rather than leak via
    # an unusual expression/driver-generated column name. This intentionally
    # favors confidentiality over partial result utility.
    selected_identifiers = set().union(*(_expression_identifiers(expression) for expression in expressions)) if expressions else set()
    if selected_identifiers & sensitive and not redacted_indexes:
        redacted_indexes = set(range(len(columns)))

    if not redacted_indexes:
        return result

    marker = '[REDACTED:sensitive_column]'
    clean_rows = []
    for row in rows:
        values = list(row)
        for idx in redacted_indexes:
            if idx < len(values):
                values[idx] = marker
        clean_rows.append(values)
    return {**result, 'rows': clean_rows}


def _redact_mongo_document(value, sensitive: set[str]):
    marker = '[REDACTED:sensitive_column]'
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            name = str(key).strip().lower()
            if name in sensitive or name.rsplit('.', 1)[-1] in sensitive:
                clean[key] = marker
            else:
                clean[key] = _redact_mongo_document(item, sensitive)
        return clean
    if isinstance(value, list):
        return [_redact_mongo_document(item, sensitive) for item in value]
    return value


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


def build_database_tools(config: dict, approval_manager: ApprovalManager | None = None) -> list[Tool]:
    max_rows = int(config.get("policy", {}).get("max_db_rows", 200))

    def db_query(alias: str, sql: str, limit: int = 100):
        if not is_read_only_sql(sql):
            return {"ok": False, "blocked": True, "error": "Only one deterministic read-only SQL statement is allowed."}
        alias_policy, require_alias_policy = _database_alias_policy(config, alias)
        if require_alias_policy and alias_policy is None:
            return {"ok": False, "blocked": True, "error": f"Database alias '{alias}' has no configured access policy."}
        if alias_policy is not None:
            allowed_tables = _allowed_table_names(alias_policy)
            referenced_tables = _referenced_sql_tables(sql)
            denied = sorted(name for name in referenced_tables if name not in allowed_tables)
            if denied:
                return {
                    "ok": False,
                    "blocked": True,
                    "error": "Query references table(s) outside the configured allowlist.",
                    "denied_tables": denied,
                }
        dsn = _dsn(alias)
        if dsn.startswith("mongodb"):
            return {"ok": False, "error": "Use mongo_find for MongoDB."}
        try:
            result = _sql_query(dsn, sql, min(max(1, limit), max_rows))
            result = _redact_sql_result(sql, result, alias_policy)
            return {"ok": True, **result}
        except Exception as e:
            return {"ok": False, "error": redact_secrets(e, 1200)}

    def mongo_find(alias: str, database: str, collection: str, filter: dict | None = None, limit: int = 50):
        alias_policy, require_alias_policy = _database_alias_policy(config, alias)
        if require_alias_policy and alias_policy is None:
            return {"ok": False, "blocked": True, "error": f"Database alias '{alias}' has no configured access policy."}
        if alias_policy is not None:
            allowed_tables = _allowed_table_names(alias_policy)
            collection_name = str(collection).strip().lower()
            qualified_name = f"{str(database).strip().lower()}.{collection_name}"
            if collection_name not in allowed_tables and qualified_name not in allowed_tables:
                return {
                    "ok": False,
                    "blocked": True,
                    "error": "MongoDB collection is outside the configured allowlist.",
                    "denied_tables": [qualified_name],
                }
        dsn = _dsn(alias)
        if not dsn.startswith("mongodb"):
            return {"ok": False, "error": "Configured DSN is not MongoDB."}
        try:
            documents = _mongo_find(dsn, database, collection, filter or {}, min(max(1, limit), max_rows))
            sensitive = _sensitive_column_names(alias_policy)
            if sensitive:
                documents = [_redact_mongo_document(document, sensitive) for document in documents]
            return {"ok": True, "documents": documents}
        except Exception as e:
            return {"ok": False, "error": redact_secrets(e, 1200)}

    return [
        Tool("db_query", "Run one read-only SQL query against a configured database alias. Parser checks and database-level read-only mode are both enforced.",
             {"type":"object","properties":{"alias":{"type":"string"},"sql":{"type":"string"},"limit":{"type":"integer","default":100}},"required":["alias","sql"]}, db_query),
        Tool("mongo_find", "Read documents from MongoDB with a bounded find(). Server-side JavaScript operators and writes are blocked.",
             {"type":"object","properties":{"alias":{"type":"string"},"database":{"type":"string"},"collection":{"type":"string"},"filter":{"type":"object"},"limit":{"type":"integer","default":50}},"required":["alias","database","collection"]}, mongo_find),
    ]
