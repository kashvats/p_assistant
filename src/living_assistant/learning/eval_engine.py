from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time

import psutil

from living_assistant.core.approval import ApprovalManager
from living_assistant.learning.improvements import ImprovementEngine, is_protected_core_path
from living_assistant.security.security_policy import classify_command
from living_assistant.core.workspace import Workspace
from living_assistant.security.sandbox import ContainerRuntime, SandboxSpec

from .eval_store import EvaluationStore, _now, _json
from .eval_measure import measure_command, _aggregate_runs, compare_benchmark



class _RepairEvaluationAuthorization:
    __slots__ = (
        "_owner", "target_path", "project_path", "test_commands", "lint_commands",
        "benchmark_commands", "repetitions", "max_latency_regression_pct",
        "max_memory_regression_pct", "execution_provider", "sandbox_image",
        "sandbox_network", "remaining_uses", "expires_at",
    )

    def __init__(self, owner: object, plan: dict, max_uses: int, ttl_seconds: int):
        self._owner = owner
        self.target_path = str(plan.get("target_path"))
        self.project_path = str(plan.get("project_path"))
        self.test_commands = tuple(plan.get("test_commands") or ())
        self.lint_commands = tuple(plan.get("lint_commands") or ())
        self.benchmark_commands = tuple(plan.get("benchmark_commands") or ())
        self.repetitions = int(plan.get("repetitions") or 1)
        self.max_latency_regression_pct = float(plan.get("max_latency_regression_pct") or 0)
        self.max_memory_regression_pct = float(plan.get("max_memory_regression_pct") or 0)
        self.execution_provider = str(plan.get("execution_provider") or "host")
        self.sandbox_image = plan.get("sandbox_image")
        self.sandbox_network = str(plan.get("sandbox_network") or "none")
        self.remaining_uses = max(0, int(max_uses))
        self.expires_at = time.monotonic() + max(1, int(ttl_seconds))

DEFAULT_IGNORES = {
    '.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'dist', 'build', '.next', '.turbo',
}

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
        self.sandbox_config = (config or {}).get('self_improvement', {}).get('sandbox', {})
        self.container_runtime = ContainerRuntime(str(self.sandbox_config.get('runtime','auto')))
        self.canary_store = None
        self.profile = profile
        self._repair_authorization_owner = object()

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
                     max_memory_regression_pct: float | None = None, execution_provider: str = 'host', sandbox_image: str | None = None,
                     sandbox_network: str = 'none', sandbox_memory_mb: int | None = None, sandbox_cpus: float | None = None,
                     sandbox_pids_limit: int | None = None, require_canary: bool = False) -> dict:
        project = self.workspace.resolve(project_path)
        if not project.is_dir():
            raise ValueError('Evaluation suite project path must be a directory.')
        execution_provider=str(execution_provider).lower()
        if execution_provider not in {'host','container'}:
            raise ValueError('Execution provider must be host or container.')
        if sandbox_network != 'none':
            raise ValueError('Evaluation suites only support sandbox_network=none. Use canary mode for service networking.')
        if execution_provider == 'container' and not sandbox_image:
            raise ValueError('Container evaluation suite requires an explicit local sandbox image.')
        return self.store.upsert_suite(
            name, str(project), test_commands, lint_commands, benchmark_commands,
            repetitions if repetitions is not None else self._default_repetitions(),
            max_latency_regression_pct if max_latency_regression_pct is not None else float(self.config.get('max_latency_regression_pct', 15)),
            max_memory_regression_pct if max_memory_regression_pct is not None else float(self.config.get('max_memory_regression_pct', 15)),
            execution_provider, sandbox_image, sandbox_network,
            int(sandbox_memory_mb if sandbox_memory_mb is not None else self.sandbox_config.get('memory_mb',1024)),
            float(sandbox_cpus if sandbox_cpus is not None else self.sandbox_config.get('cpus',1.0)),
            int(sandbox_pids_limit if sandbox_pids_limit is not None else self.sandbox_config.get('pids_limit',256)),
            require_canary,
        )

    def _resolve_plan(self, proposal: dict, suite_name: str | None, project_path: str | None,
                      test_commands: list[str] | None, lint_commands: list[str] | None,
                      benchmark_commands: list[str] | None, repetitions: int | None,
                      max_latency_regression_pct: float | None, max_memory_regression_pct: float | None,
                      execution_provider: str | None = None, sandbox_image: str | None = None, sandbox_network: str | None = None) -> dict:
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
        provider = str(execution_provider or (suite.get('execution_provider') if suite else None) or 'host').lower()
        if provider not in {'host','container'}:
            raise ValueError('Execution provider must be host or container.')
        image = sandbox_image if sandbox_image is not None else (suite.get('sandbox_image') if suite else None)
        if provider == 'container' and self.profile == 'lite' and not bool(self.sandbox_config.get('lite_enabled',False)):
            raise ValueError('Container evaluation is disabled on the lite profile by default. Use host evaluation or explicitly enable sandbox.lite_enabled.')
        if provider == 'container' and not image:
            raise ValueError('Container evaluation requires an explicit sandbox image.')
        network = str(sandbox_network if sandbox_network is not None else (suite.get('sandbox_network') if suite else 'none') or 'none')
        if network not in {'none'}:
            raise ValueError('Evaluation containers default to network=none; networked evaluation is intentionally unsupported. Use canary mode for service health checks.')
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
            'execution_provider': provider, 'sandbox_image': image, 'sandbox_network': network,
            'sandbox_memory_mb': int((suite.get('sandbox_memory_mb') if suite else None) or self.sandbox_config.get('memory_mb',1024)),
            'sandbox_cpus': float((suite.get('sandbox_cpus') if suite else None) or self.sandbox_config.get('cpus',1.0)),
            'sandbox_pids_limit': int((suite.get('sandbox_pids_limit') if suite else None) or self.sandbox_config.get('pids_limit',256)),
            'require_canary': bool(suite.get('require_canary')) if suite else False,
        }

    def _create_repair_authorization(self, plan: dict, max_uses: int, ttl_seconds: int = 7200) -> _RepairEvaluationAuthorization:
        """Create an in-process capability for an already-approved bounded repair loop.

        The returned object is intentionally not serializable/tool-facing. Evaluation
        validates object identity, exact target/project/commands, expiry and use count.
        """
        return _RepairEvaluationAuthorization(self._repair_authorization_owner, plan, max_uses, ttl_seconds)

    def _consume_repair_authorization(self, authorization: object, plan: dict) -> tuple[bool, str | None]:
        if not isinstance(authorization, _RepairEvaluationAuthorization):
            return False, 'Invalid repair evaluation authorization.'
        if authorization._owner is not self._repair_authorization_owner:
            return False, 'Repair evaluation authorization belongs to a different engine.'
        if time.monotonic() > authorization.expires_at:
            return False, 'Repair evaluation authorization expired.'
        if authorization.remaining_uses <= 0:
            return False, 'Repair evaluation authorization has no remaining uses.'
        expected = (
            authorization.target_path, authorization.project_path, authorization.test_commands,
            authorization.lint_commands, authorization.benchmark_commands, authorization.repetitions,
            authorization.max_latency_regression_pct, authorization.max_memory_regression_pct,
            authorization.execution_provider, authorization.sandbox_image, authorization.sandbox_network,
        )
        actual = (
            str(plan.get('target_path')), str(plan.get('project_path')), tuple(plan.get('test_commands') or ()),
            tuple(plan.get('lint_commands') or ()), tuple(plan.get('benchmark_commands') or ()), int(plan.get('repetitions') or 1),
            float(plan.get('max_latency_regression_pct') or 0), float(plan.get('max_memory_regression_pct') or 0),
            str(plan.get('execution_provider') or 'host'), plan.get('sandbox_image'), str(plan.get('sandbox_network') or 'none'),
        )
        if actual != expected:
            return False, 'Repair evaluation plan does not match the approved bounded plan.'
        authorization.remaining_uses -= 1
        return True, None

    def sandbox_status(self) -> dict:
        return {'config': self.sandbox_config, 'container': self.container_runtime.status()}

    def _measure(self, command: str, cwd: Path, timeout: int, plan: dict) -> dict:
        if plan.get('execution_provider') != 'container':
            result = measure_command(command, cwd, timeout)
            result.setdefault('execution_provider','host')
            return result
        spec = SandboxSpec(
            image=str(plan.get('sandbox_image_id') or plan['sandbox_image']), network='none', memory_mb=int(plan.get('sandbox_memory_mb',1024)),
            cpus=float(plan.get('sandbox_cpus',1.0)), pids_limit=int(plan.get('sandbox_pids_limit',256)),
            read_only_root=bool(self.sandbox_config.get('read_only_root',True)), tmpfs_mb=int(self.sandbox_config.get('tmpfs_mb',128)),
        )
        return self.container_runtime.run_command(command, cwd, timeout, spec)

    def evaluate(self, proposal_id: str, suite_name: str | None = None, project_path: str | None = None,
                 test_commands: list[str] | None = None, lint_commands: list[str] | None = None,
                 benchmark_commands: list[str] | None = None, repetitions: int | None = None,
                 max_latency_regression_pct: float | None = None, max_memory_regression_pct: float | None = None,
                 execution_provider: str | None = None, sandbox_image: str | None = None, sandbox_network: str | None = None,
                 _repair_authorization: object | None = None) -> dict:
        if not bool((self.config or {}).get('enabled', True)):
            return {'ok': False, 'error': 'Evaluated self-improvement is disabled in config.'}
        proposal = self.improvements.store.get(proposal_id)
        if not proposal:
            return {'ok': False, 'error': 'Unknown proposal id'}
        if proposal['status'] != 'pending':
            return {'ok': False, 'error': f"Proposal is {proposal['status']}; only pending proposals can be evaluated."}
        try:
            plan = self._resolve_plan(proposal, suite_name, project_path, test_commands, lint_commands,
                                      benchmark_commands, repetitions, max_latency_regression_pct, max_memory_regression_pct,
                                      execution_provider, sandbox_image, sandbox_network)
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

        target = Path(plan['target_path'])
        if plan.get('execution_provider') == 'container':
            state=self.container_runtime.status()
            if not state.get('available'):
                return {'ok':False,'container_unavailable':True,'error':state.get('error') or state.get('reason') or 'Container runtime unavailable.'}
            image_state=self.container_runtime.image_info(str(plan.get('sandbox_image')))
            if not image_state.get('available') or not image_state.get('image_id'):
                return {'ok':False,'image_unavailable':True,'error':'Sandbox image must already exist locally; automatic pulls are disabled.','image':image_state}
            plan['sandbox_image_id']=image_state['image_id']
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
            'benchmarks': plan['benchmark_commands'], 'repetitions': plan['repetitions'], 'execution_provider': plan['execution_provider'],
            'sandbox_image': plan.get('sandbox_image'), 'sandbox_image_id': plan.get('sandbox_image_id'), 'sandbox_network': plan.get('sandbox_network'),
        })
        approval_reason = 'Runs the exact listed commands in isolated repository worktrees/copies. Container provider additionally applies resource/capability/network restrictions; host provider is repository-state isolation only.'
        if _repair_authorization is not None:
            authorized, authorization_error = self._consume_repair_authorization(_repair_authorization, plan)
            if not authorized:
                return {'ok': False, 'internal_authorization_invalid': True, 'error': authorization_error, 'plan': plan}
        else:
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
        from . import evaluation as evaluation_facade
        root = evaluation_facade.data_dir() / 'evaluation_worktrees' / eid
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
                'candidate_commit': candidate_commit, 'execution_provider': plan.get('execution_provider','host'),
                'sandbox': {'image':plan.get('sandbox_image'),'image_id':plan.get('sandbox_image_id'),'network':plan.get('sandbox_network'),'memory_mb':plan.get('sandbox_memory_mb'),'cpus':plan.get('sandbox_cpus'),'pids_limit':plan.get('sandbox_pids_limit')},
                'tests': [], 'lint': [], 'benchmarks': [], 'gates': {},
            }

            for kind, commands in [('tests', plan['test_commands']), ('lint', plan['lint_commands'])]:
                for command in commands:
                    if mode == 'git_worktree':
                        _reset_eval_worktree(baseline_dir, base_commit)
                        _reset_eval_worktree(candidate_dir, candidate_commit)
                    baseline_run = self._measure(command, baseline_cwd, timeout, plan)
                    candidate_run = self._measure(command, candidate_cwd, timeout, plan)
                    results[kind].append({'command': command, 'baseline': baseline_run, 'candidate': candidate_run})

            for command in plan['benchmark_commands']:
                base_runs=[]; cand_runs=[]
                for _ in range(plan.get('benchmark_warmup_runs', 0)):
                    if mode == 'git_worktree':
                        _reset_eval_worktree(baseline_dir, base_commit); _reset_eval_worktree(candidate_dir, candidate_commit)
                    self._measure(command, baseline_cwd, timeout, plan); self._measure(command, candidate_cwd, timeout, plan)
                for index in range(plan['repetitions']):
                    if mode == 'git_worktree':
                        _reset_eval_worktree(baseline_dir, base_commit); _reset_eval_worktree(candidate_dir, candidate_commit)
                    # Alternate order to reduce persistent first/second-run thermal and cache bias.
                    if index % 2 == 0:
                        base_runs.append(self._measure(command, baseline_cwd, timeout, plan))
                        cand_runs.append(self._measure(command, candidate_cwd, timeout, plan))
                    else:
                        cand_runs.append(self._measure(command, candidate_cwd, timeout, plan))
                        base_runs.append(self._measure(command, baseline_cwd, timeout, plan))
                base_agg = _aggregate_runs(base_runs); cand_agg = _aggregate_runs(cand_runs)
                comparison = compare_benchmark(base_agg, cand_agg, plan['max_latency_regression_pct'], plan['max_memory_regression_pct'])
                results['benchmarks'].append({'command': command, 'baseline': base_agg, 'candidate': cand_agg, 'comparison': comparison})

            required_checks = [*results['tests'], *results['lint']]
            checks_pass = all(item['candidate'].get('ok') for item in required_checks)
            benchmarks_pass = all(item['comparison'].get('passed') for item in results['benchmarks'])
            results['gates'] = {
                'candidate_checks_pass': checks_pass,
                'benchmarks_within_budget': benchmarks_pass,
                'protected_core_target': is_protected_core_path(target),
                'canary_required': bool(plan.get('require_canary',False)),
                'promotable': checks_pass and benchmarks_pass and not is_protected_core_path(target),
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
        if evaluation.get('result', {}).get('gates', {}).get('canary_required'):
            latest = self.canary_store.latest_for_evaluation(evaluation_id) if self.canary_store is not None else None
            if not latest or latest.get('status') != 'completed' or latest.get('verdict') != 'passed':
                return {'ok': False, 'canary_required': True, 'error': 'This evaluation suite requires a passing canary run before promotion.'}
            canary_result = latest.get('result', {})
            if canary_result.get('candidate_commit') != evaluation.get('candidate_commit') or canary_result.get('base_commit') != evaluation.get('base_commit'):
                return {'ok': False, 'conflict': True, 'error': 'Latest canary was not measured against the exact evaluated commits.'}
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

