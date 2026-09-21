from __future__ import annotations

from pathlib import Path
import datetime as dt
import json
import sqlite3
import uuid

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_suites(
  name TEXT PRIMARY KEY,
  project_path TEXT NOT NULL,
  test_commands TEXT NOT NULL DEFAULT '[]',
  lint_commands TEXT NOT NULL DEFAULT '[]',
  benchmark_commands TEXT NOT NULL DEFAULT '[]',
  repetitions INTEGER NOT NULL DEFAULT 3,
  max_latency_regression_pct REAL NOT NULL DEFAULT 15,
  max_memory_regression_pct REAL NOT NULL DEFAULT 15,
  execution_provider TEXT NOT NULL DEFAULT 'host',
  sandbox_image TEXT,
  sandbox_network TEXT NOT NULL DEFAULT 'none',
  sandbox_memory_mb INTEGER NOT NULL DEFAULT 1024,
  sandbox_cpus REAL NOT NULL DEFAULT 1.0,
  sandbox_pids_limit INTEGER NOT NULL DEFAULT 256,
  require_canary INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS improvement_evaluations(
  id TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  suite_name TEXT,
  project_path TEXT NOT NULL,
  mode TEXT NOT NULL,
  branch_name TEXT,
  base_commit TEXT,
  candidate_commit TEXT,
  status TEXT NOT NULL,
  verdict TEXT,
  config_json TEXT NOT NULL DEFAULT '{}',
  result_json TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  promoted_at TEXT,
  promotion_commit TEXT,
  reverted_at TEXT,
  revert_commit TEXT
);
CREATE INDEX IF NOT EXISTS eval_proposal_idx ON improvement_evaluations(proposal_id, created_at);
CREATE INDEX IF NOT EXISTS eval_status_idx ON improvement_evaluations(status, created_at);
"""

DEFAULT_IGNORES = {
    '.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'dist', 'build', '.next', '.turbo',
}

def _now() -> str:
    return dt.datetime.now().isoformat(timespec='seconds')

def _json(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)

def _decode(value: str, fallback):
    try:
        return json.loads(value)
    except Exception:
        return fallback

class EvaluationStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / 'assistant.sqlite3')
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._ensure_suite_columns()
        self.conn.commit()

    def _ensure_suite_columns(self):
        existing={str(r[1]) for r in self.conn.execute('PRAGMA table_info(evaluation_suites)').fetchall()}
        columns={
            'execution_provider': "TEXT NOT NULL DEFAULT 'host'", 'sandbox_image':'TEXT',
            'sandbox_network': "TEXT NOT NULL DEFAULT 'none'", 'sandbox_memory_mb':'INTEGER NOT NULL DEFAULT 1024',
            'sandbox_cpus':'REAL NOT NULL DEFAULT 1.0', 'sandbox_pids_limit':'INTEGER NOT NULL DEFAULT 256',
            'require_canary':'INTEGER NOT NULL DEFAULT 0',
        }
        for name, ddl in columns.items():
            if name not in existing:
                self.conn.execute(f'ALTER TABLE evaluation_suites ADD COLUMN {name} {ddl}')

    def upsert_suite(self, name: str, project_path: str, test_commands: list[str] | None = None,
                     lint_commands: list[str] | None = None, benchmark_commands: list[str] | None = None,
                     repetitions: int = 3, max_latency_regression_pct: float = 15,
                     max_memory_regression_pct: float = 15, execution_provider: str = 'host', sandbox_image: str | None = None,
                     sandbox_network: str = 'none', sandbox_memory_mb: int = 1024, sandbox_cpus: float = 1.0,
                     sandbox_pids_limit: int = 256, require_canary: bool = False) -> dict:
        if not name.strip():
            raise ValueError('Suite name is required.')
        now = _now()
        self.conn.execute(
            """INSERT INTO evaluation_suites(name,project_path,test_commands,lint_commands,benchmark_commands,repetitions,max_latency_regression_pct,max_memory_regression_pct,execution_provider,sandbox_image,sandbox_network,sandbox_memory_mb,sandbox_cpus,sandbox_pids_limit,require_canary,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET project_path=excluded.project_path,test_commands=excluded.test_commands,lint_commands=excluded.lint_commands,
                 benchmark_commands=excluded.benchmark_commands,repetitions=excluded.repetitions,max_latency_regression_pct=excluded.max_latency_regression_pct,
                 max_memory_regression_pct=excluded.max_memory_regression_pct,execution_provider=excluded.execution_provider,sandbox_image=excluded.sandbox_image,
                 sandbox_network=excluded.sandbox_network,sandbox_memory_mb=excluded.sandbox_memory_mb,sandbox_cpus=excluded.sandbox_cpus,
                 sandbox_pids_limit=excluded.sandbox_pids_limit,require_canary=excluded.require_canary,updated_at=excluded.updated_at""",
            (name, project_path, _json(test_commands or []), _json(lint_commands or []), _json(benchmark_commands or []),
             max(1, min(int(repetitions), 10)), float(max_latency_regression_pct), float(max_memory_regression_pct), execution_provider, sandbox_image,
             sandbox_network, max(128,int(sandbox_memory_mb)), max(0.1,float(sandbox_cpus)), max(32,int(sandbox_pids_limit)), int(bool(require_canary)), now, now),
        )
        self.conn.commit()
        return self.get_suite(name) or {}

    def get_suite(self, name: str) -> dict | None:
        row = self.conn.execute('SELECT * FROM evaluation_suites WHERE name=?', (name,)).fetchone()
        if not row:
            return None
        item = dict(row)
        for key in ('test_commands', 'lint_commands', 'benchmark_commands'):
            item[key] = _decode(item[key], [])
        return item

    def list_suites(self) -> list[dict]:
        rows = self.conn.execute('SELECT * FROM evaluation_suites ORDER BY name').fetchall()
        return [self.get_suite(str(r['name'])) for r in rows if self.get_suite(str(r['name']))]

    def delete_suite(self, name: str) -> bool:
        cur = self.conn.execute('DELETE FROM evaluation_suites WHERE name=?', (name,))
        self.conn.commit()
        return cur.rowcount > 0

    def create_evaluation(self, proposal_id: str, suite_name: str | None, project_path: str,
                          mode: str, config: dict) -> dict:
        eid = uuid.uuid4().hex[:12]
        now = _now()
        self.conn.execute(
            "INSERT INTO improvement_evaluations(id,proposal_id,suite_name,project_path,mode,status,config_json,created_at) VALUES(?,?,?,?,?,'created',?,?)",
            (eid, proposal_id, suite_name, project_path, mode, _json(config), now),
        )
        self.conn.commit()
        return self.get(eid) or {}

    def update(self, evaluation_id: str, **fields):
        allowed = {
            'mode','branch_name','base_commit','candidate_commit','status','verdict','config_json','result_json','error',
            'started_at','finished_at','promoted_at','promotion_commit','reverted_at','revert_commit',
        }
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return
        columns = ','.join(f'{k}=?' for k in clean)
        self.conn.execute(f'UPDATE improvement_evaluations SET {columns} WHERE id=?', (*clean.values(), evaluation_id))
        self.conn.commit()

    def get(self, evaluation_id: str) -> dict | None:
        row = self.conn.execute('SELECT * FROM improvement_evaluations WHERE id=?', (evaluation_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item['config'] = _decode(item.pop('config_json'), {})
        item['result'] = _decode(item.pop('result_json'), {})
        return item

    def list(self, status: str | None = None, limit: int = 100) -> list[dict]:
        if status:
            rows = self.conn.execute('SELECT id FROM improvement_evaluations WHERE status=? ORDER BY created_at DESC LIMIT ?', (status, limit)).fetchall()
        else:
            rows = self.conn.execute('SELECT id FROM improvement_evaluations ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        return [x for x in (self.get(str(r['id'])) for r in rows) if x]

