from __future__ import annotations
from pathlib import Path
import difflib
import re
from .base import Tool
from ..workspace import Workspace
from ..approval import ApprovalManager
from ..security_utils import is_sensitive_path


def _preview(path: Path, old: str, new: str, max_chars: int = 20000) -> str:
    diff = ''.join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=str(path) + ':before', tofile=str(path) + ':after'
    ))
    return diff[:max_chars]


def _approval_for_sensitive(approval: ApprovalManager | None, path: Path, action: str) -> dict | None:
    if not is_sensitive_path(path):
        return None
    if approval is None:
        return {'ok': False, 'error': f'{action} requires an approval manager for sensitive path {path}.'}
    req = approval.request(
        f'{action} sensitive file {path}',
        'Sensitive files may contain passwords, API tokens, private keys, or account credentials. Contents are not included in this approval record.',
        'SENSITIVE_FILE_ACCESS',
    )
    if not req.get('allowed'):
        return {'ok': False, 'approval_required': True, **req, 'sensitive': True}
    return {'allowed': True}


def build_filesystem_tools(workspace: Workspace, approval: ApprovalManager | None = None,
                           require_write_approval: bool = False) -> list[Tool]:
    def list_files(path: str = '.'):
        return workspace.list(path)

    def read_file(path: str):
        p = workspace.resolve(path)
        gate = _approval_for_sensitive(approval, p, 'Read')
        if gate and not gate.get('allowed'):
            return gate
        return {'path': str(p), 'content': workspace.read_text(path), 'sensitive': bool(gate)}

    def preview_write_file(path: str, content: str):
        p = workspace.resolve(path)
        gate = _approval_for_sensitive(approval, p, 'Preview write to')
        if gate and not gate.get('allowed'):
            return gate
        old = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
        return {'path': str(p), 'exists': p.exists(), 'diff': _preview(p, old, content),
                'bytes_before': len(old.encode('utf-8')), 'bytes_after': len(content.encode('utf-8')), 'sensitive': bool(gate)}

    def write_file(path: str, content: str):
        p = workspace.resolve(path)
        sensitive = is_sensitive_path(p)
        if sensitive:
            gate = _approval_for_sensitive(approval, p, 'Write')
            if gate and not gate.get('allowed'):
                return gate
        old = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
        diff = _preview(p, old, content)
        if require_write_approval and not sensitive:
            if approval is None:
                return {'ok': False, 'error': 'Write approval is required but no approval manager is configured.'}
            req = approval.request(f'Write file {p}', f'Workspace file change. Diff:\n{diff[:5000]}', 'WRITE_WORKSPACE')
            if not req.get('allowed'):
                return {'ok': False, 'approval_required': True, **req, 'diff': diff}
        result = workspace.write_text(path, content)
        return {'ok': True, 'path': result, 'bytes': len(content.encode('utf-8')),
                'diff': '[REDACTED: sensitive file diff]' if sensitive else diff, 'sensitive': sensitive}

    def search_files(query: str, path: str = '.', limit: int = 50, regex: bool = False,
                     extensions: list[str] | None = None):
        root = workspace.resolve(path)
        out = []
        bounded_limit=max(1,min(int(limit),200))
        ext_filter={str(x).lower() if str(x).startswith('.') else '.'+str(x).lower() for x in (extensions or []) if str(x).strip()}
        pattern=None
        if regex:
            try:
                pattern=re.compile(query,re.IGNORECASE)
            except re.error as exc:
                return {'ok':False,'error':f'Invalid search regex: {exc}'}
        q=query.lower()
        for p in root.rglob('*'):
            if len(out) >= bounded_limit:
                break
            if not p.is_file() or (ext_filter and p.suffix.lower() not in ext_filter):
                continue
            filename_match=bool(pattern.search(p.name)) if pattern else q in p.name.lower()
            if filename_match:
                out.append({'path': str(p), 'match': 'filename', 'sensitive': is_sensitive_path(p)})
                continue
            if is_sensitive_path(p):
                # Never index/search sensitive contents without an explicit targeted read approval.
                continue
            try:
                if p.stat().st_size > 2_000_000:
                    continue
                data=p.read_bytes()
                sample=data[:8192]
                # NUL bytes or a high proportion of non-text control bytes are a
                # strong binary signal. Skip content decoding in that case.
                controls=sum(1 for b in sample if b < 32 and b not in (9,10,13))
                if b'\x00' in sample or (sample and controls/len(sample) > 0.10):
                    continue
                txt=data.decode('utf-8',errors='ignore')
                matched=bool(pattern.search(txt)) if pattern else q in txt.lower()
                if matched:
                    out.append({'path': str(p), 'match': 'content'})
            except Exception:
                pass
        return out

    return [
        Tool('list_files', 'List files/directories inside an approved workspace.',
             {'type':'object','properties':{'path':{'type':'string','default':'.'}}}, list_files),
        Tool('read_file', 'Read a UTF-8 text file inside an approved workspace. Sensitive credential/key files require explicit approval.',
             {'type':'object','properties':{'path':{'type':'string'}},'required':['path']}, read_file),
        Tool('preview_write_file', 'Preview the unified diff for a proposed text-file write without changing the file. Sensitive files require approval.',
             {'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}, preview_write_file),
        Tool('write_file', 'Write text inside an approved workspace. Sensitive files always require explicit approval.',
             {'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}, write_file),
        Tool('search_files', 'Search filenames/text inside an approved workspace with optional regex and extension filtering. Binary and sensitive file contents are never indexed.',
             {'type':'object','properties':{'query':{'type':'string'},'path':{'type':'string','default':'.'},'limit':{'type':'integer','default':50},'regex':{'type':'boolean','default':False},'extensions':{'type':'array','items':{'type':'string'}}},'required':['query']}, search_files),
    ]
