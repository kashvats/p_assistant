from __future__ import annotations
import subprocess
from pathlib import Path
from .base import Tool
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.core.approval import ApprovalManager
from living_assistant.security.security_utils import is_sensitive_path, redact_secrets


def _git(cwd: Path, args: list[str], timeout: int = 30) -> dict:
    p = subprocess.run(['git', *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return {'ok': p.returncode == 0, 'returncode': p.returncode, 'stdout': p.stdout[-30000:], 'stderr': p.stderr[-10000:]}


def _is_repo(cwd: Path) -> bool:
    try:
        p = subprocess.run(['git','rev-parse','--is-inside-work-tree'], cwd=str(cwd), capture_output=True, text=True, timeout=5)
        return p.returncode == 0 and p.stdout.strip() == 'true'
    except Exception:
        return False


def _workspace_repo_cwd(workspace: Workspace, path: str) -> tuple[Path | None, dict | None]:
    """Resolve a git working directory and ensure its repository root is in-bounds."""
    try:
        cwd = workspace.resolve(path)
    except (WorkspaceViolation, OSError, RuntimeError):
        return None, {'ok': False, 'blocked': True, 'error': 'Git path is outside allowed workspace roots.'}

    if not _is_repo(cwd):
        return None, {'ok': False, 'error': 'Not a git repository.'}

    try:
        probe = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=str(cwd), capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None, {'ok': False, 'error': 'Could not determine git repository root.'}
    if probe.returncode != 0 or not probe.stdout.strip():
        return None, {'ok': False, 'error': 'Could not determine git repository root.'}

    try:
        workspace.resolve(Path(probe.stdout.strip()))
    except (WorkspaceViolation, OSError, RuntimeError):
        return None, {
            'ok': False,
            'blocked': True,
            'error': 'Git repository root is outside allowed workspace roots.',
        }
    return cwd, None


def build_git_tools(workspace: Workspace, approval: ApprovalManager) -> list[Tool]:
    def git_status(path: str = '.'):
        cwd, error = _workspace_repo_cwd(workspace, path)
        if error: return error
        return _git(cwd, ['status','--short','--branch'])

    def git_diff(path: str = '.', staged: bool = False):
        cwd, error = _workspace_repo_cwd(workspace, path)
        if error: return error
        args = ['diff'] + (['--cached'] if staged else [])
        result = _git(cwd, args)
        if not result.get('ok'):
            result['stdout'] = redact_secrets(result.get('stdout', ''), 30000)
            result['stderr'] = redact_secrets(result.get('stderr', ''), 10000)
            return result

        raw_stdout = result.get('stdout', '')
        redacted_stdout = redact_secrets(raw_stdout, 30000)
        redacted_stderr = redact_secrets(result.get('stderr', ''), 10000)

        name_args = ['diff'] + (['--cached'] if staged else []) + ['--name-only', '--']
        changed = _git(cwd, name_args)
        sensitive_path = False
        if changed.get('ok'):
            sensitive_path = any(
                is_sensitive_path(name.strip())
                for name in changed.get('stdout', '').splitlines()
                if name.strip()
            )
        sensitive_content = redacted_stdout != raw_stdout
        sensitive = sensitive_path or sensitive_content

        if sensitive:
            action = f"git diff ({'staged' if staged else 'working tree'}) in {cwd}"
            reason = 'The diff contains a sensitive file path or secret-like content. Explicit approval is required before exposing a sanitized diff.'
            req = approval.request(action, reason, 'READ_SENSITIVE')
            if not req.get('allowed'):
                return {
                    'ok': False,
                    'approval_required': True,
                    'sensitive': True,
                    **req,
                }

        return {
            **result,
            'stdout': redacted_stdout,
            'stderr': redacted_stderr,
            'sensitive': sensitive,
        }

    def git_log(path: str = '.', limit: int = 12):
        cwd, error = _workspace_repo_cwd(workspace, path)
        if error: return error
        return _git(cwd, ['log', f'-n{max(1,min(limit,50))}', '--oneline', '--decorate'])

    def git_create_branch(name: str, path: str = '.'):
        cwd, error = _workspace_repo_cwd(workspace, path)
        if error: return error
        if not name or any(x in name for x in [' ', '..', '~', '^', ':', '?', '*', '[', '\\']):
            return {'ok': False, 'error': 'Unsafe/invalid branch name.'}
        req = approval.request(f'git switch -c {name} in {cwd}', 'Creating and switching git branches changes repository state.', 'WRITE_WORKSPACE')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        return _git(cwd, ['switch','-c',name])

    def git_commit(message: str, path: str = '.'):
        cwd, error = _workspace_repo_cwd(workspace, path)
        if error: return error
        if not message.strip(): return {'ok': False, 'error': 'Commit message is required.'}
        req = approval.request(f'git commit -m {message!r} in {cwd}', 'Committing records repository changes.', 'WRITE_WORKSPACE')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        return _git(cwd, ['commit','-m',message])

    return [
        Tool('git_status', 'Show concise git status for an approved workspace repository.',
             {'type':'object','properties':{'path':{'type':'string','default':'.'}}}, git_status),
        Tool('git_diff', 'Show current or staged git diff. Read-only.',
             {'type':'object','properties':{'path':{'type':'string','default':'.'},'staged':{'type':'boolean','default':False}}}, git_diff),
        Tool('git_log', 'Show recent git commits. Read-only.',
             {'type':'object','properties':{'path':{'type':'string','default':'.'},'limit':{'type':'integer','default':12}}}, git_log),
        Tool('git_create_branch', 'Create and switch to a new branch. Requires approval.',
             {'type':'object','properties':{'name':{'type':'string'},'path':{'type':'string','default':'.'}},'required':['name']}, git_create_branch),
        Tool('git_commit', 'Commit already-staged changes. Does not stage files automatically. Requires approval.',
             {'type':'object','properties':{'message':{'type':'string'},'path':{'type':'string','default':'.'}},'required':['message']}, git_commit),
    ]
