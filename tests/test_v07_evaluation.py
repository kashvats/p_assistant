from __future__ import annotations
from pathlib import Path
import subprocess

import pytest

from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.evaluation import EvaluationEngine, EvaluationStore, compare_benchmark, measure_command
from living_assistant.improvements import ImprovementEngine, ImprovementStore
from living_assistant.workspace import Workspace


def build(tmp_path, monkeypatch=None):
    if monkeypatch is not None:
        import living_assistant.evaluation as evaluation
        monkeypatch.setattr(evaluation, 'data_dir', lambda: tmp_path / 'data')
    project = tmp_path / 'project'; project.mkdir()
    ws = Workspace([project])
    approvals = ApprovalStore(tmp_path / 'approvals.sqlite3')
    manager = ApprovalManager(interactive=False, store=approvals)
    improvements = ImprovementEngine(ws, manager, ImprovementStore(tmp_path / 'improvements.sqlite3'))
    store = EvaluationStore(tmp_path / 'evaluations.sqlite3')
    cfg = {'self_improvement': {'evaluation': {
        'enabled': True, 'execution_provider': 'host', 'benchmark_repetitions': 2, 'max_benchmark_repetitions': 4,
        'max_latency_regression_pct': 15, 'max_memory_regression_pct': 15,
        'command_timeout_seconds': 10, 'max_commands': 8, 'copy_max_files': 100, 'copy_max_mb': 10,
    }}}
    return project, approvals, improvements, EvaluationEngine(ws, manager, improvements, store, cfg)


def approve_and_retry(approvals, first, retry):
    assert first['approval_required'] is True
    approvals.resolve(first['approval_id'], True)
    return retry()


def git(cwd: Path, *args):
    p = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def init_git(project: Path):
    git(project, 'init')
    git(project, 'config', 'user.email', 'test@example.com')
    git(project, 'config', 'user.name', 'Test User')


def test_suite_roundtrip(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    suite = engine.create_suite('fast', str(project), ['python -c "print(1)"'], ['python -c "print(2)"'], [], 2, 10, 20)
    assert suite['name'] == 'fast'
    assert suite['repetitions'] == 2
    assert engine.store.get_suite('fast')['test_commands'][0].startswith('python')
    assert engine.store.delete_suite('fast') is True


def test_copy_evaluation_passes_without_modifying_source(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    (project / 'a.txt').write_text('old')
    proposal = improvements.propose('a.txt', 'new', 'change', 'make it new')
    cmd = "python -c \"from pathlib import Path; assert Path('a.txt').read_text() == 'new'\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    result = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    assert result['ok'] is True and result['verdict'] == 'passed'
    assert result['mode'] == 'copy'
    assert (project / 'a.txt').read_text() == 'old'


def test_failed_candidate_is_not_promotable(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    (project / 'a.txt').write_text('old')
    proposal = improvements.propose('a.txt', 'new', 'change', 'reason')
    cmd = "python -c \"import sys; sys.exit(4)\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    result = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    assert result['verdict'] == 'failed'
    assert result['result']['gates']['promotable'] is False
    assert engine.promote(result['id'])['ok'] is False


def test_benchmark_comparison_enforces_budgets():
    baseline = {'all_passed': True, 'median_seconds': 1.0, 'median_peak_rss_mb': 100}
    candidate = {'all_passed': True, 'median_seconds': 1.20, 'median_peak_rss_mb': 105}
    bad = compare_benchmark(baseline, candidate, 10, 10)
    assert bad['passed'] is False and bad['latency_regression_pct'] == 20.0
    good = compare_benchmark(baseline, candidate, 25, 10)
    assert good['passed'] is True


def test_unsafe_evaluation_command_rejected_before_approval(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    (project / 'a.txt').write_text('old')
    proposal = improvements.propose('a.txt', 'new', 'change', 'reason')
    result = engine.evaluate(proposal['id'], project_path=str(project), test_commands=['rm -rf /'])
    assert result['ok'] is False
    assert 'Unsafe evaluation command' in result['error']
    assert approvals.list('pending') == []


def test_measure_command_is_time_bounded(tmp_path):
    result = measure_command('python -c "import time; time.sleep(2)"', tmp_path, timeout_seconds=0.15)
    assert result['ok'] is False and result['timeout'] is True
    assert result['duration_seconds'] < 2


def test_git_evaluation_and_promotion_are_separate_approved_steps(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    init_git(project)
    (project / 'a.txt').write_text('old')
    git(project, 'add', 'a.txt'); git(project, 'commit', '-m', 'base')
    proposal = improvements.propose('a.txt', 'new', 'change', 'reason')
    cmd = "python -c \"from pathlib import Path; assert Path('a.txt').read_text() == 'new'\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    evaluated = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    assert evaluated['mode'] == 'git_worktree' and evaluated['verdict'] == 'passed'
    assert evaluated['branch_name'].startswith('living-assistant/eval/')
    assert evaluated['candidate_commit']
    assert (project / 'a.txt').read_text() == 'old'

    promote_first = engine.promote(evaluated['id'])
    promoted = approve_and_retry(approvals, promote_first, lambda: engine.promote(evaluated['id']))
    assert promoted['ok'] is True
    assert (project / 'a.txt').read_text() == 'new'
    assert improvements.store.get(proposal['id'])['status'] == 'applied'


def test_git_promotion_refuses_stale_head(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    init_git(project)
    (project / 'a.txt').write_text('old'); git(project, 'add', 'a.txt'); git(project, 'commit', '-m', 'base')
    proposal = improvements.propose('a.txt', 'new', 'change', 'reason')
    cmd = "python -c \"from pathlib import Path; assert Path('a.txt').read_text() == 'new'\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    evaluated = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    (project / 'other.txt').write_text('later'); git(project, 'add', 'other.txt'); git(project, 'commit', '-m', 'later')
    result = engine.promote(evaluated['id'])
    assert result['conflict'] is True


def test_git_evaluation_refuses_dirty_source(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    init_git(project)
    (project / 'a.txt').write_text('old'); git(project, 'add', 'a.txt'); git(project, 'commit', '-m', 'base')
    proposal = improvements.propose('a.txt', 'new', 'change', 'reason')
    (project / 'unrelated.txt').write_text('dirty')
    cmd = "python -c \"print('ok')\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    result = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    assert result['ok'] is False and 'must be clean' in result['error']


def test_protected_core_can_be_measured_but_not_auto_promoted(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    init_git(project)
    (project / 'src' / 'living_assistant').mkdir(parents=True)
    (project / 'pyproject.toml').write_text('[project]\nname="living-assistant"\nversion="0.0"\n')
    (project / 'src' / 'living_assistant' / 'security_policy.py').write_text('old')
    git(project, 'add', 'pyproject.toml', 'src/living_assistant/security_policy.py'); git(project, 'commit', '-m', 'base')
    proposal = improvements.propose('src/living_assistant/security_policy.py', 'new', 'core change', 'reason')
    cmd = "python -c \"from pathlib import Path; assert Path('src/living_assistant/security_policy.py').read_text() == 'new'\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    evaluated = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    assert evaluated['verdict'] == 'passed'
    assert evaluated['result']['gates']['protected_core_target'] is True
    result = engine.promote(evaluated['id'])
    assert result['manual_required'] is True


def test_git_promotion_can_be_reverted_without_history_rewrite(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    init_git(project)
    (project / 'a.txt').write_text('old'); git(project, 'add', 'a.txt'); git(project, 'commit', '-m', 'base')
    proposal = improvements.propose('a.txt', 'new', 'change', 'reason')
    cmd = "python -c \"from pathlib import Path; assert Path('a.txt').read_text() == 'new'\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    evaluated = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    p1 = engine.promote(evaluated['id']); approve_and_retry(approvals, p1, lambda: engine.promote(evaluated['id']))
    r1 = engine.revert_promotion(evaluated['id'])
    reverted = approve_and_retry(approvals, r1, lambda: engine.revert_promotion(evaluated['id']))
    assert reverted['ok'] is True and reverted['revert_commit']
    assert (project / 'a.txt').read_text() == 'old'
    assert improvements.store.get(proposal['id'])['status'] == 'rolled_back'

def test_promotion_refuses_branch_tip_tampering(tmp_path, monkeypatch):
    project, approvals, improvements, engine = build(tmp_path, monkeypatch)
    init_git(project)
    (project / 'a.txt').write_text('old'); git(project, 'add', 'a.txt'); git(project, 'commit', '-m', 'base')
    proposal = improvements.propose('a.txt', 'new', 'change', 'reason')
    cmd = "python -c \"from pathlib import Path; assert Path('a.txt').read_text() == 'new'\""
    first = engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd])
    evaluated = approve_and_retry(approvals, first, lambda: engine.evaluate(proposal['id'], project_path=str(project), test_commands=[cmd]))
    # Move the audit branch after evaluation. Promotion must verify the immutable evaluated commit.
    git(project, 'branch', '-f', evaluated['branch_name'], evaluated['base_commit'])
    result = engine.promote(evaluated['id'])
    assert result['conflict'] is True
    assert 'changed after measurement' in result['error']


def test_profile_adaptive_benchmark_defaults(tmp_path, monkeypatch):
    project, approvals, improvements, _ = build(tmp_path, monkeypatch)
    store = EvaluationStore(tmp_path / 'profile-eval.sqlite3')
    cfg = {'self_improvement': {'evaluation': {
        'enabled': True,
        'benchmark_repetitions_by_profile': {'lite': 1, 'balanced': 3, 'power': 5},
        'benchmark_warmup_runs_by_profile': {'lite': 0, 'balanced': 1, 'power': 2},
    }}}
    lite = EvaluationEngine(Workspace([project]), ApprovalManager(interactive=False, store=approvals), improvements, store, cfg, profile='lite')
    power = EvaluationEngine(Workspace([project]), ApprovalManager(interactive=False, store=approvals), improvements, store, cfg, profile='power')
    assert lite._default_repetitions() == 1 and lite._warmup_runs() == 0
    assert power._default_repetitions() == 5 and power._warmup_runs() == 2

def test_evaluation_does_not_execute_shell_chaining(tmp_path):
    marker = tmp_path / 'should-not-exist.txt'
    cmd = f'''python -c "print('first')" && python -c "from pathlib import Path; Path(r'{marker}').write_text('bad')"'''
    result = measure_command(cmd, tmp_path, timeout_seconds=3)
    assert marker.exists() is False
    assert result.get('argv') and '&&' in result['argv']
