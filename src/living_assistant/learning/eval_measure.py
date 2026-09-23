from __future__ import annotations

from pathlib import Path
import shlex
import statistics
import subprocess
import tempfile
import time

import psutil

from living_assistant.security.security_policy import classify_command
from living_assistant.security.sandbox import sanitized_env
from living_assistant.learning.regression_detection import detect_metric_regression

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

    env = sanitized_env({
        'LIVING_ASSISTANT_EVALUATION': '1',
        'CI': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    try:
        argv = shlex.split(command, posix=True)
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

    baseline_runs = [x for x in baseline.get('runs', []) if x.get('ok')]
    candidate_runs = [x for x in candidate.get('runs', []) if x.get('ok')]
    latency = detect_metric_regression(
        [x.get('duration_seconds') for x in baseline_runs] or [baseline.get('median_seconds')],
        [x.get('duration_seconds') for x in candidate_runs] or [candidate.get('median_seconds')],
        max_latency_regression_pct,
    )
    memory = detect_metric_regression(
        [x.get('peak_rss_mb') for x in baseline_runs] or [baseline.get('median_peak_rss_mb')],
        [x.get('peak_rss_mb') for x in candidate_runs] or [candidate.get('median_peak_rss_mb')],
        max_memory_regression_pct,
    )
    result['latency_regression_pct'] = latency.get('regression_pct')
    result['memory_regression_pct'] = memory.get('regression_pct')
    result['statistical_detection'] = {'latency': latency, 'memory': memory}
    result['passed'] = bool(latency.get('passed') and memory.get('passed'))
    if not result['passed']:
        failed=[]
        if not latency.get('passed'): failed.append('latency')
        if not memory.get('passed'): failed.append('memory')
        result['reason'] = 'Candidate has a regression beyond the configured budget/noise floor: ' + ', '.join(failed) + '.'
    elif latency.get('budget_exceeded') or memory.get('budget_exceeded'):
        result['reason'] = 'A point estimate exceeded its budget but was not distinguishable from measured benchmark noise.'
    return result
