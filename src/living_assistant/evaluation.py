from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import datetime as dt
import hashlib
import json
import os
import shutil
import shlex
import sqlite3
import statistics
import subprocess
import tempfile
import time
import uuid

import psutil

from .approval import ApprovalManager
from .config import data_dir
from .improvements import ImprovementEngine, ImprovementStore, PROTECTED_CORE_NAMES
from .security_policy import classify_command
from .workspace import Workspace

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


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _git(cwd: Path, args: list[str], timeout: int = 60, env: dict | None = None) -> dict:
    try:
        p = subprocess.run(
            ['git', *args], cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, env=env or os.environ.copy(),
        )
        return {
            'ok': p.returncode == 0,
            'returncode': p.returncode,
            'stdout': p.stdout[-30000:],
            'stderr': p.stderr[-10000:],
        }
    except FileNotFoundError:
        return {'ok': False, 'returncode': 127, 'stdout': '', 'stderr': 'git is not installed'}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'returncode': 124, 'stdout': '', 'stderr': 'git command timed out'}


def _repo_root(path: Path) -> Path | None:
    r = _git(path, ['rev-parse', '--show-toplevel'], timeout=8)
    if not r['ok']:
        return None
    try:
        return Path(r['stdout'].strip()).resolve()
    except Exception:
        return None


def _reset_eval_worktree(path: Path, commit: str) -> None:
    reset = _git(path, ['reset', '--hard', commit], timeout=60)
    if not reset['ok']:
        raise RuntimeError(reset['stderr'] or f'Could not reset evaluation worktree {path}.')
    clean = _git(path, ['clean', '-fd'], timeout=60)
    if not clean['ok']:
        raise RuntimeError(clean['stderr'] or f'Could not clean evaluation worktree {path}.')


def _kill_tree(pid: int):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        try:
            parent.terminate()
        except Exception:
            pass
        _, alive = psutil.wait_procs(children + [parent], timeout=2)
        for proc in alive:
            try:
                proc.kill()
            except Exception:
                pass
    except Exception:
        pass


def measure_command(command: str, cwd: Path, timeout_seconds: int = 300) -> dict:
    """Run one approved evaluation command with bounded output/time and process-tree RSS sampling."""
    decision = classify_command(command, require_execute_approval=False)
    if not decision.allowed:
        return {
            'ok': False, 'blocked': True, 'command': command, 'returncode': None,
            'reason': decision.reason, 'duration_seconds': 0.0, 'peak_rss_mb': 0.0,
        }
    if decision.risk.value in {'PRIVILEGED', 'DESTRUCTIVE'}:
        return {
            'ok': False, 'blocked': True, 'command': command, 'returncode': None,
            'reason': 'Privileged/destructive commands are not allowed in automated evaluations.',
            'duration_seconds': 0.0, 'peak_rss_mb': 0.0,
        }

    env = os.environ.copy()
    env.update({
        'LIVING_ASSISTANT_EVALUATION': '1',
        'CI': env.get('CI', '1'),
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    try:
        argv = shlex.split(command, posix=(os.name != 'nt'))
    except ValueError as exc:
        return {'ok':False,'blocked':True,'command':command,'returncode':None,'reason':f'Could not parse command safely: {exc}','duration_seconds':0.0,'peak_rss_mb':0.0}
    if not argv:
        return {'ok':False,'blocked':True,'command':command,'returncode':None,'reason':'Empty evaluation command.','duration_seconds':0.0,'peak_rss_mb':0.0}
    started = time.perf_counter()
    peak = 0
    with tempfile.TemporaryFile(mode='w+b') as out, tempfile.TemporaryFile(mode='w+b') as err:
        try:
            proc = subprocess.Popen(
                argv, cwd=str(cwd), shell=False, stdout=out, stderr=err, env=env,
            )
        except Exception as exc:
            return {
                'ok': False, 'command': command, 'returncode': None, 'error': str(exc),
                'duration_seconds': round(time.perf_counter() - started, 4), 'peak_rss_mb': 0.0,
            }

        timed_out = False
        while proc.poll() is None:
            elapsed = time.perf_counter() - started
            if elapsed > timeout_seconds:
                timed_out = True
                _kill_tree(proc.pid)
                break
            try:
                root = psutil.Process(proc.pid)
                procs = [root, *root.children(recursive=True)]
                rss = 0
                for item in procs:
                    try:
                        rss += item.memory_info().rss
                    except Exception:
                        pass
                peak = max(peak, rss)
            except Exception:
                pass
            time.sleep(0.04)

        try:
            rc = proc.wait(timeout=3)
        except Exception:
            _kill_tree(proc.pid)
            rc = proc.poll()
        duration = time.perf_counter() - started
        out.seek(0); err.seek(0)
        stdout = out.read().decode('utf-8', errors='replace')[-30000:]
        stderr = err.read().decode('utf-8', errors='replace')[-10000:]
        return {
            'ok': (rc == 0 and not timed_out),
            'command': command,
            'argv': argv,
            'returncode': rc,
            'timeout': timed_out,
            'duration_seconds': round(duration, 4),
            'peak_rss_mb': round(peak / (1024 ** 2), 2),
            'stdout': stdout,
            'stderr': stderr,
        }


def _aggregate_runs(runs: list[dict]) -> dict:
    successful = [x for x in runs if x.get('ok')]
    return {
        'runs': runs,
        'all_passed': len(successful) == len(runs) and bool(runs),
        'pass_count': len(successful),
        'run_count': len(runs),
        'median_seconds': round(statistics.median([x['duration_seconds'] for x in successful]), 4) if successful else None,
        'median_peak_rss_mb': round(statistics.median([x['peak_rss_mb'] for x in successful]), 2) if successful else None,
    }


def compare_benchmark(baseline: dict, candidate: dict, max_latency_regression_pct: float, max_memory_regression_pct: float) -> dict:
    result = {
        'valid': bool(baseline.get('all_passed') and candidate.get('all_passed')),
        'passed': False,
        'latency_regression_pct': None,
        'memory_regression_pct': None,
        'limits': {
            'max_latency_regression_pct': max_latency_regression_pct,
            'max_memory_regression_pct': max_memory_regression_pct,
        },
    }
    if not result['valid']:
        result['reason'] = 'Baseline and candidate benchmark runs must all succeed.'
        return result

    b_time = float(baseline.get('median_seconds') or 0)
    c_time = float(candidate.get('median_seconds') or 0)
    b_mem = float(baseline.get('median_peak_rss_mb') or 0)
    c_mem = float(candidate.get('median_peak_rss_mb') or 0)

    latency_pct = 0.0 if b_time <= 1e-9 else ((c_time - b_time) / b_time) * 100.0
    memory_pct = 0.0 if b_mem <= 1e-9 else ((c_mem - b_mem) / b_mem) * 100.0
    result['latency_regression_pct'] = round(latency_pct, 2)
    result['memory_regression_pct'] = round(memory_pct, 2)
    result['passed'] = latency_pct <= max_latency_regression_pct and memory_pct <= max_memory_regression_pct
    if not result['passed']:
        result['reason'] = 'Candidate exceeded one or more configured regression budgets.'
    return result


class EvaluationStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / 'assistant.sqlite3')
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_suite(self, name: str, project_path: str, test_commands: list[str] | None = None,
                     lint_commands: list[str] | None = None, benchmark_commands: list[str] | None = None,
                     repetitions: int = 3, max_latency_regression_pct: float = 15,
                     max_memory_regression_pct: float = 15) -> dict:
        if not name.strip():
            raise ValueError('Suite name is required.')
        now = _now()
        self.conn.execute(
            """INSERT INTO evaluation_suites(name,project_path,test_commands,lint_commands,benchmark_commands,repetitions,max_latency_regression_pct,max_memory_regression_pct,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET project_path=excluded.project_path,test_commands=excluded.test_commands,lint_commands=excluded.lint_commands,
                 benchmark_commands=excluded.benchmark_commands,repetitions=excluded.repetitions,max_latency_regression_pct=excluded.max_latency_regression_pct,
                 max_memory_regression_pct=excluded.max_memory_regression_pct,updated_at=excluded.updated_at""",
            (name, project_path, _json(test_commands or []), _json(lint_commands or []), _json(benchmark_commands or []),
             max(1, min(int(repetitions), 10)), float(max_latency_regression_pct), float(max_memory_regression_pct), now, now),
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


def _copy_project(src: Path, dst: Path, max_files: int, max_mb: int):
    count = 0
    total = 0
    max_bytes = max_mb * 1024 * 1024
    dst.mkdir(parents=True, exist_ok=False)
    for root, dirs, files in os.walk(src, followlinks=False):
        rootp = Path(root)
        rel = rootp.relative_to(src)
        dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORES and not (rootp / d).is_symlink()]
        target_root = dst / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for name in files:
            source = rootp / name
            if source.is_symlink():
                continue
            count += 1
            if count > max_files:
                raise RuntimeError(f'Non-git evaluation copy exceeded {max_files} files.')
            try:
                size = source.stat().st_size
            except OSError:
                continue
            total += size
            if total > max_bytes:
                raise RuntimeError(f'Non-git evaluation copy exceeded {max_mb} MB.')
            shutil.copy2(source, target_root / name)


class EvaluationEngine:
    def __init__(self, workspace: Workspace, approval: ApprovalManager, improvement_engine: ImprovementEngine,
                 store: EvaluationStore, config: dict | None = None, profile: str = 'balanced'):
        self.workspace = workspace
        self.approval = approval
        self.improvements = improvement_engine
        self.store = store
        self.config = (config or {}).get('self_improvement', {}).get('evaluation', {})
        self.profile = profile

    def _default_repetitions(self) -> int:
        by_profile = self.config.get('benchmark_repetitions_by_profile', {})
        if isinstance(by_profile, dict) and self.profile in by_profile:
            return int(by_profile[self.profile])
        return int(self.config.get('benchmark_repetitions', 3))

    def _warmup_runs(self) -> int:
        by_profile = self.config.get('benchmark_warmup_runs_by_profile', {})
        if isinstance(by_profile, dict) and self.profile in by_profile:
            return max(0, int(by_profile[self.profile]))
        return max(0, int(self.config.get('benchmark_warmup_runs', 1)))

    def create_suite(self, name: str, project_path: str, test_commands: list[str] | None = None,
                     lint_commands: list[str] | None = None, benchmark_commands: list[str] | None = None,
                     repetitions: int | None = None, max_latency_regression_pct: float | None = None,
                     max_memory_regression_pct: float | None = None) -> dict:
        project = self.workspace.resolve(project_path)
        if not project.is_dir():
            raise ValueError('Evaluation suite project path must be a directory.')
        return self.store.upsert_suite(
            name, str(project), test_commands, lint_commands, benchmark_commands,
            repetitions if repetitions is not None else self._default_repetitions(),
            max_latency_regression_pct if max_latency_regression_pct is not None else float(self.config.get('max_latency_regression_pct', 15)),
            max_memory_regression_pct if max_memory_regression_pct is not None else float(self.config.get('max_memory_regression_pct', 15)),
        )

    def _resolve_plan(self, proposal: dict, suite_name: str | None, project_path: str | None,
                      test_commands: list[str] | None, lint_commands: list[str] | None,
                      benchmark_commands: list[str] | None, repetitions: int | None,
                      max_latency_regression_pct: float | None, max_memory_regression_pct: float | None) -> dict:
        suite = self.store.get_suite(suite_name) if suite_name else None
        if suite_name and not suite:
            raise ValueError(f'Unknown evaluation suite: {suite_name}')
        target = self.workspace.resolve(proposal['target_path'])
        if suite:
            project = self.workspace.resolve(suite['project_path'])
        elif project_path:
            project = self.workspace.resolve(project_path)
        else:
            repo = _repo_root(target.parent)
            project = repo if repo else next((r for r in self.workspace.roots if target.is_relative_to(r)), target.parent)
            project = self.workspace.resolve(project)
        if not project.is_dir():
            raise ValueError('Evaluation project path is not a directory.')
        try:
            target.relative_to(project)
        except ValueError as exc:
            raise ValueError('Proposal target must be inside the evaluation project.') from exc

        tests = list(test_commands if test_commands is not None else (suite['test_commands'] if suite else proposal.get('tests', [])))
        lints = list(lint_commands if lint_commands is not None else (suite['lint_commands'] if suite else []))
        benches = list(benchmark_commands if benchmark_commands is not None else (suite['benchmark_commands'] if suite else []))
        max_commands = int(self.config.get('max_commands', 12))
        if len(tests) + len(lints) + len(benches) > max_commands:
            raise ValueError(f'Evaluation contains more than {max_commands} distinct commands.')
        if not tests and not lints and not benches:
            raise ValueError('At least one test, lint/static-check, or benchmark command is required.')
        max_command_chars = int(self.config.get('max_command_chars', 4000))
        for command in [*tests, *lints, *benches]:
            if not isinstance(command, str) or not command.strip():
                raise ValueError('Evaluation commands must be non-empty strings.')
            if len(command) > max_command_chars:
                raise ValueError(f'Evaluation command exceeds {max_command_chars} characters.')
            decision = classify_command(command, require_execute_approval=False)
            if not decision.allowed or decision.risk.value in {'PRIVILEGED','DESTRUCTIVE'}:
                raise ValueError(f'Unsafe evaluation command rejected: {command}')

        reps = int(repetitions if repetitions is not None else (suite['repetitions'] if suite else self._default_repetitions()))
        return {
            'project_path': str(project),
            'target_path': str(target),
            'test_commands': tests,
            'lint_commands': lints,
            'benchmark_commands': benches,
            'repetitions': max(1, min(reps, int(self.config.get('max_benchmark_repetitions', 10)))),
            'max_latency_regression_pct': float(max_latency_regression_pct if max_latency_regression_pct is not None else (suite['max_latency_regression_pct'] if suite else self.config.get('max_latency_regression_pct', 15))),
            'max_memory_regression_pct': float(max_memory_regression_pct if max_memory_regression_pct is not None else (suite['max_memory_regression_pct'] if suite else self.config.get('max_memory_regression_pct', 15))),
            'command_timeout_seconds': int(self.config.get('command_timeout_seconds', 300)),
            'benchmark_warmup_runs': self._warmup_runs(),
        }

    def evaluate(self, proposal_id: str, suite_name: str | None = None, project_path: str | None = None,
                 test_commands: list[str] | None = None, lint_commands: list[str] | None = None,
                 benchmark_commands: list[str] | None = None, repetitions: int | None = None,
                 max_latency_regression_pct: float | None = None, max_memory_regression_pct: float | None = None) -> dict:
        if not bool((self.config or {}).get('enabled', True)):
            return {'ok': False, 'error': 'Evaluated self-improvement is disabled in config.'}
        proposal = self.improvements.store.get(proposal_id)
        if not proposal:
            return {'ok': False, 'error': 'Unknown proposal id'}
        if proposal['status'] != 'pending':
            return {'ok': False, 'error': f"Proposal is {proposal['status']}; only pending proposals can be evaluated."}
        try:
            plan = self._resolve_plan(proposal, suite_name, project_path, test_commands, lint_commands,
                                      benchmark_commands, repetitions, max_latency_regression_pct, max_memory_regression_pct)
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

        target = Path(plan['target_path'])
        vm = psutil.virtual_memory()
        minimum_by_profile = self.config.get('minimum_available_ram_gb_by_profile', {'lite':0.5,'balanced':1.0,'power':2.0})
        minimum_gb = float(minimum_by_profile.get(self.profile, 1.0)) if isinstance(minimum_by_profile, dict) else 1.0
        available_gb = vm.available / (1024 ** 3)
        if available_gb < minimum_gb:
            return {'ok':False,'resource_blocked':True,'error':f'Only {available_gb:.2f} GB RAM is available; evaluation requires at least {minimum_gb:.2f} GB for profile {self.profile}.'}
        current = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        if _sha_text(current) != proposal['base_sha256']:
            return {'ok': False, 'conflict': True, 'error': 'Target changed since proposal creation; regenerate the proposal.'}

        approval_action = 'Evaluate improvement ' + proposal_id + ': ' + _json({
            'project': plan['project_path'], 'tests': plan['test_commands'], 'lint': plan['lint_commands'],
            'benchmarks': plan['benchmark_commands'], 'repetitions': plan['repetitions'],
        })
        approval_reason = 'Runs the exact listed local commands in isolated repository worktrees/copies. Repository-state isolation is not an OS/network sandbox.'
        req = self.approval.request(approval_action, approval_reason, 'SELF_EVALUATION')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req, 'plan': plan}

        project = Path(plan['project_path']).resolve()
        repo = _repo_root(project)
        mode = 'git_worktree' if repo and target.is_relative_to(repo) else 'copy'
        if repo:
            try:
                self.workspace.resolve(repo)
            except Exception:
                mode = 'copy'
                repo = None
        evaluation = self.store.create_evaluation(proposal_id, suite_name, str(project), mode, plan)
        eid = evaluation['id']
        self.store.update(eid, status='running', started_at=_now())
        root = data_dir() / 'evaluation_worktrees' / eid
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        baseline_dir = root / 'baseline'
        candidate_dir = root / 'candidate'
        branch = None
        base_commit = None
        candidate_commit = None

        try:
            if mode == 'git_worktree' and repo is not None:
                status = _git(repo, ['status', '--porcelain'])
                if not status['ok']:
                    raise RuntimeError(status['stderr'] or 'Could not inspect git status.')
                if status['stdout'].strip():
                    raise RuntimeError('Source repository must be clean before an evaluated improvement. Commit/stash unrelated changes first.')
                base = _git(repo, ['rev-parse', 'HEAD'])
                if not base['ok']:
                    raise RuntimeError(base['stderr'] or 'Could not read git HEAD.')
                base_commit = base['stdout'].strip()
                branch = f'living-assistant/eval/{eid}'
                if not _git(repo, ['worktree', 'add', '--detach', str(baseline_dir), base_commit], timeout=120)['ok']:
                    raise RuntimeError('Could not create baseline git worktree.')
                cand_add = _git(repo, ['worktree', 'add', '-b', branch, str(candidate_dir), base_commit], timeout=120)
                if not cand_add['ok']:
                    raise RuntimeError(cand_add['stderr'] or 'Could not create candidate git worktree/branch.')
                rel_target = target.relative_to(repo)
                project_rel = project.relative_to(repo)
                baseline_cwd = baseline_dir / project_rel
                candidate_cwd = candidate_dir / project_rel
            else:
                max_files = int(self.config.get('copy_max_files', 8000))
                max_mb = int(self.config.get('copy_max_mb', 500))
                _copy_project(project, baseline_dir, max_files, max_mb)
                _copy_project(project, candidate_dir, max_files, max_mb)
                rel_target = target.relative_to(project)
                baseline_cwd = baseline_dir
                candidate_cwd = candidate_dir

            candidate_target = candidate_dir / rel_target
            baseline_target = baseline_dir / rel_target
            baseline_content = baseline_target.read_text(encoding='utf-8', errors='replace') if baseline_target.exists() else ''
            if _sha_text(baseline_content) != proposal['base_sha256']:
                raise RuntimeError('Isolated baseline does not match the proposal base. Ensure the proposal was created from the committed/selected project state.')
            candidate_target.parent.mkdir(parents=True, exist_ok=True)
            candidate_target.write_text(proposal['proposed_content'], encoding='utf-8')

            if mode == 'git_worktree':
                add = _git(candidate_dir, ['add', '--', str(rel_target)])
                if not add['ok']:
                    raise RuntimeError(add['stderr'] or 'Could not stage evaluated candidate.')
                env = os.environ.copy()
                env.update({'GIT_AUTHOR_NAME':'Living Assistant','GIT_AUTHOR_EMAIL':'living-assistant@localhost','GIT_COMMITTER_NAME':'Living Assistant','GIT_COMMITTER_EMAIL':'living-assistant@localhost'})
                commit = _git(candidate_dir, ['commit', '-m', f'evaluate: {proposal["title"]} ({eid})'], env=env)
                if not commit['ok']:
                    raise RuntimeError(commit['stderr'] or 'Could not commit candidate branch.')
                head = _git(candidate_dir, ['rev-parse', 'HEAD'])
                candidate_commit = head['stdout'].strip() if head['ok'] else None
                self.store.update(eid, branch_name=branch, base_commit=base_commit, candidate_commit=candidate_commit)

            timeout = int(plan['command_timeout_seconds'])
            results = {
                'proposal_id': proposal_id,
                'mode': mode,
                'branch_name': branch,
                'base_commit': base_commit,
                'candidate_commit': candidate_commit,
                'tests': [], 'lint': [], 'benchmarks': [], 'gates': {},
            }

            for kind, commands in [('tests', plan['test_commands']), ('lint', plan['lint_commands'])]:
                for command in commands:
                    if mode == 'git_worktree':
                        _reset_eval_worktree(baseline_dir, base_commit)
                        _reset_eval_worktree(candidate_dir, candidate_commit)
                    baseline_run = measure_command(command, baseline_cwd, timeout)
                    candidate_run = measure_command(command, candidate_cwd, timeout)
                    results[kind].append({'command': command, 'baseline': baseline_run, 'candidate': candidate_run})

            for command in plan['benchmark_commands']:
                base_runs=[]; cand_runs=[]
                for _ in range(plan.get('benchmark_warmup_runs', 0)):
                    if mode == 'git_worktree':
                        _reset_eval_worktree(baseline_dir, base_commit); _reset_eval_worktree(candidate_dir, candidate_commit)
                    measure_command(command, baseline_cwd, timeout); measure_command(command, candidate_cwd, timeout)
                for index in range(plan['repetitions']):
                    if mode == 'git_worktree':
                        _reset_eval_worktree(baseline_dir, base_commit); _reset_eval_worktree(candidate_dir, candidate_commit)
                    # Alternate order to reduce persistent first/second-run thermal and cache bias.
                    if index % 2 == 0:
                        base_runs.append(measure_command(command, baseline_cwd, timeout))
                        cand_runs.append(measure_command(command, candidate_cwd, timeout))
                    else:
                        cand_runs.append(measure_command(command, candidate_cwd, timeout))
                        base_runs.append(measure_command(command, baseline_cwd, timeout))
                base_agg = _aggregate_runs(base_runs); cand_agg = _aggregate_runs(cand_runs)
                comparison = compare_benchmark(base_agg, cand_agg, plan['max_latency_regression_pct'], plan['max_memory_regression_pct'])
                results['benchmarks'].append({'command': command, 'baseline': base_agg, 'candidate': cand_agg, 'comparison': comparison})

            required_checks = [*results['tests'], *results['lint']]
            checks_pass = all(item['candidate'].get('ok') for item in required_checks)
            benchmarks_pass = all(item['comparison'].get('passed') for item in results['benchmarks'])
            results['gates'] = {
                'candidate_checks_pass': checks_pass,
                'benchmarks_within_budget': benchmarks_pass,
                'protected_core_target': target.name in PROTECTED_CORE_NAMES,
                'promotable': checks_pass and benchmarks_pass and target.name not in PROTECTED_CORE_NAMES,
            }
            verdict = 'passed' if checks_pass and benchmarks_pass else 'failed'
            self.store.update(
                eid, status='completed', verdict=verdict, result_json=_json(results), finished_at=_now(),
                branch_name=branch, base_commit=base_commit, candidate_commit=candidate_commit,
            )
            return {'ok': True, **(self.store.get(eid) or {}), 'promotable': results['gates']['promotable']}
        except Exception as exc:
            self.store.update(eid, status='error', verdict='error', error=str(exc), finished_at=_now(),
                              branch_name=branch, base_commit=base_commit, candidate_commit=candidate_commit)
            return {'ok': False, **(self.store.get(eid) or {}), 'error': str(exc)}
        finally:
            if mode == 'git_worktree' and repo is not None:
                for path in (baseline_dir, candidate_dir):
                    if path.exists():
                        _git(repo, ['worktree', 'remove', '--force', str(path)], timeout=120)
                _git(repo, ['worktree', 'prune'])
            else:
                shutil.rmtree(root, ignore_errors=True)

    def promote(self, evaluation_id: str) -> dict:
        evaluation = self.store.get(evaluation_id)
        if not evaluation:
            return {'ok': False, 'error': 'Unknown evaluation id'}
        if evaluation.get('status') != 'completed' or evaluation.get('verdict') != 'passed':
            return {'ok': False, 'error': 'Only a completed, passing evaluation can be promoted.'}
        if not evaluation.get('result', {}).get('gates', {}).get('promotable'):
            if evaluation.get('result', {}).get('gates', {}).get('protected_core_target'):
                return {'ok': False, 'manual_required': True, 'error': 'Security-critical assistant core cannot be auto-promoted even after evaluation.'}
            return {'ok': False, 'error': 'Evaluation gates do not mark this candidate promotable.'}
        proposal = self.improvements.store.get(evaluation['proposal_id'])
        if not proposal:
            return {'ok': False, 'error': 'Proposal no longer exists.'}
        if proposal['status'] != 'pending':
            return {'ok': False, 'error': f"Proposal is {proposal['status']}."}

        if evaluation['mode'] == 'git_worktree':
            repo = _repo_root(Path(evaluation['project_path']))
            if repo is None:
                return {'ok': False, 'error': 'Git repository is no longer available.'}
            status = _git(repo, ['status', '--porcelain'])
            if not status['ok'] or status['stdout'].strip():
                return {'ok': False, 'conflict': True, 'error': 'Source repository is not clean; promotion refused.'}
            current = _git(repo, ['rev-parse', 'HEAD'])
            if not current['ok'] or current['stdout'].strip() != evaluation.get('base_commit'):
                return {'ok': False, 'conflict': True, 'error': 'Repository HEAD changed since evaluation; re-evaluate against the new base.'}
            branch = evaluation.get('branch_name')
            candidate_commit = evaluation.get('candidate_commit')
            if not branch or not candidate_commit:
                return {'ok': False, 'error': 'Evaluation branch metadata is missing.'}
            branch_tip = _git(repo, ['rev-parse', branch])
            if not branch_tip['ok'] or branch_tip['stdout'].strip() != candidate_commit:
                return {'ok':False,'conflict':True,'error':'Evaluation branch changed after measurement; promotion refused. Re-evaluate the candidate.'}
            action = f'Promote evaluated improvement {evaluation_id}: git merge --ff-only {candidate_commit} in {repo}'
            reason = 'This modifies the active repository only after the exact immutable candidate commit passed its configured checks and regression budgets.'
            req = self.approval.request(action, reason, 'SELF_PROMOTION')
            if not req.get('allowed'):
                return {'ok': False, 'approval_required': True, **req}
            merged = _git(repo, ['merge', '--ff-only', candidate_commit], timeout=120)
            if not merged['ok']:
                return {'ok': False, 'error': merged['stderr'] or 'Fast-forward promotion failed.', 'git': merged}
            new_head = _git(repo, ['rev-parse', 'HEAD'])
            promotion_commit = new_head['stdout'].strip() if new_head['ok'] else candidate_commit
            self.improvements.store.set_status(evaluation['proposal_id'], 'applied')
            self.store.update(evaluation_id, status='promoted', promoted_at=_now(), promotion_commit=promotion_commit)
            return {'ok': True, 'evaluation_id': evaluation_id, 'proposal_id': evaluation['proposal_id'], 'promotion_commit': promotion_commit, 'branch': branch}

        # Non-git projects reuse the exact proposal apply path and its existing backup/approval mechanism.
        applied = self.improvements.apply(evaluation['proposal_id'])
        if applied.get('ok'):
            self.store.update(evaluation_id, status='promoted', promoted_at=_now())
        return {'evaluation_id': evaluation_id, **applied}

    def revert_promotion(self, evaluation_id: str) -> dict:
        evaluation = self.store.get(evaluation_id)
        if not evaluation:
            return {'ok': False, 'error': 'Unknown evaluation id'}
        if evaluation.get('status') != 'promoted':
            return {'ok': False, 'error': 'Only promoted evaluations can be reverted.'}
        if evaluation['mode'] != 'git_worktree':
            result = self.improvements.rollback(evaluation['proposal_id'])
            if result.get('ok'):
                self.store.update(evaluation_id, status='reverted', reverted_at=_now())
            return {'evaluation_id': evaluation_id, **result}

        repo = _repo_root(Path(evaluation['project_path']))
        if repo is None:
            return {'ok': False, 'error': 'Git repository is no longer available.'}
        status = _git(repo, ['status', '--porcelain'])
        if not status['ok'] or status['stdout'].strip():
            return {'ok': False, 'conflict': True, 'error': 'Repository must be clean before reverting an evaluated promotion.'}
        commit = evaluation.get('promotion_commit') or evaluation.get('candidate_commit')
        if not commit:
            return {'ok': False, 'error': 'Promotion commit metadata is missing.'}
        action = f'Revert evaluated promotion {evaluation_id}: git revert {commit} in {repo}'
        reason = 'Creates a new Git revert commit; it does not rewrite history.'
        req = self.approval.request(action, reason, 'SELF_PROMOTION_ROLLBACK')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        env = os.environ.copy()
        env.update({'GIT_AUTHOR_NAME':'Living Assistant','GIT_AUTHOR_EMAIL':'living-assistant@localhost','GIT_COMMITTER_NAME':'Living Assistant','GIT_COMMITTER_EMAIL':'living-assistant@localhost'})
        reverted = _git(repo, ['revert', '--no-edit', commit], timeout=120, env=env)
        if not reverted['ok']:
            _git(repo, ['revert', '--abort'])
            return {'ok': False, 'error': reverted['stderr'] or 'Git revert failed.', 'git': reverted}
        head = _git(repo, ['rev-parse', 'HEAD'])
        revert_commit = head['stdout'].strip() if head['ok'] else None
        self.improvements.store.set_status(evaluation['proposal_id'], 'rolled_back')
        self.store.update(evaluation_id, status='reverted', reverted_at=_now(), revert_commit=revert_commit)
        return {'ok': True, 'evaluation_id': evaluation_id, 'revert_commit': revert_commit}

    def cleanup_branch(self, evaluation_id: str) -> dict:
        evaluation = self.store.get(evaluation_id)
        if not evaluation:
            return {'ok': False, 'error': 'Unknown evaluation id'}
        branch = evaluation.get('branch_name')
        if not branch or evaluation.get('mode') != 'git_worktree':
            return {'ok': True, 'message': 'No evaluation branch to clean.'}
        if evaluation.get('status') == 'promoted':
            return {'ok': False, 'error': 'Do not delete a promoted evaluation branch through cleanup; keep it for audit or delete manually.'}
        repo = _repo_root(Path(evaluation['project_path']))
        if repo is None:
            return {'ok': False, 'error': 'Git repository is no longer available.'}
        action = f'Delete evaluation branch {branch} in {repo}'
        reason = 'Deletes only the isolated Living Assistant evaluation branch, not the active branch.'
        req = self.approval.request(action, reason, 'SELF_EVALUATION_CLEANUP')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        result = _git(repo, ['branch', '-D', branch])
        return {'ok': result['ok'], 'branch': branch, 'git': result}
