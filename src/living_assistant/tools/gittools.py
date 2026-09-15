from __future__ import annotations
import subprocess
from pathlib import Path
from .base import Tool
from ..workspace import Workspace
from ..approval import ApprovalManager


def _git(cwd: Path, args: list[str], timeout: int = 30) -> dict:
    p = subprocess.run(['git', *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return {'ok': p.returncode == 0, 'returncode': p.returncode, 'stdout': p.stdout[-30000:], 'stderr': p.stderr[-10000:]}


def _is_repo(cwd: Path) -> bool:
    try:
        p = subprocess.run(['git','rev-parse','--is-inside-work-tree'], cwd=str(cwd), capture_output=True, text=True, timeout=5)
        return p.returncode == 0 and p.stdout.strip() == 'true'
    except Exception:
        return False


def build_git_tools(workspace: Workspace, approval: ApprovalManager) -> list[Tool]:
    def git_status(path: str = '.'):
        cwd = workspace.resolve(path)
        if not _is_repo(cwd): return {'ok': False, 'error': 'Not a git repository.'}
        return _git(cwd, ['status','--short','--branch'])

    def git_diff(path: str = '.', staged: bool = False):
        cwd = workspace.resolve(path)
        if not _is_repo(cwd): return {'ok': False, 'error': 'Not a git repository.'}
        args = ['diff'] + (['--cached'] if staged else [])
        return _git(cwd, args)

    def git_log(path: str = '.', limit: int = 12):
        cwd = workspace.resolve(path)
        if not _is_repo(cwd): return {'ok': False, 'error': 'Not a git repository.'}
        return _git(cwd, ['log', f'-n{max(1,min(limit,50))}', '--oneline', '--decorate'])

    def git_create_branch(name: str, path: str = '.'):
        cwd = workspace.resolve(path)
        if not _is_repo(cwd): return {'ok': False, 'error': 'Not a git repository.'}
        if not name or any(x in name for x in [' ', '..', '~', '^', ':', '?', '*', '[', '\\']):
            return {'ok': False, 'error': 'Unsafe/invalid branch name.'}
        req = approval.request(f'git switch -c {name} in {cwd}', 'Creating and switching git branches changes repository state.', 'WRITE_WORKSPACE')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        return _git(cwd, ['switch','-c',name])

    def git_commit(message: str, path: str = '.'):
        cwd = workspace.resolve(path)
        if not _is_repo(cwd): return {'ok': False, 'error': 'Not a git repository.'}
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
