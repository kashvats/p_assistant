from __future__ import annotations
from pathlib import Path
import difflib
import fnmatch
import re
from typing import TYPE_CHECKING
from .base import Tool
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.core.approval import ApprovalManager
from living_assistant.security.security_utils import is_sensitive_path

if TYPE_CHECKING:
    from living_assistant.system.workspace_snapshots import WorkspaceSnapshotManager


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
                           require_write_approval: bool = False,
                           snapshot_manager: "WorkspaceSnapshotManager | None" = None) -> list[Tool]:
    def list_files(path: str = '.'):
        try:
            return workspace.list(path)
        except (FileNotFoundError, NotADirectoryError, WorkspaceViolation) as exc:
            return {'ok': False, 'error': str(exc)}

    def read_file(path: str):
        try:
            p = workspace.resolve(path)
        except WorkspaceViolation as exc:
            return {'ok': False, 'error': str(exc)}
        if not p.exists():
            return {'ok': False, 'error': f'File not found: {path}'}
        if p.is_dir():
            return {'ok': False, 'error': f'Path is a directory, not a file: {path}. Use list_files to inspect directory contents.'}
        gate = _approval_for_sensitive(approval, p, 'Read')
        if gate and not gate.get('allowed'):
            return gate
        if p.suffix.lower() == '.pdf':
            try:
                from living_assistant.core import chat_files
                info = chat_files.describe(p, p.name, max_chars=20000)
                return {'path': str(p), 'content': info.get('text', ''), 'pdf_pages': info.get('pdf_pages'),
                        'kind': 'pdf', 'sensitive': bool(gate)}
            except Exception:
                pass
        return {'path': str(p), 'content': workspace.read_text(path), 'sensitive': bool(gate)}

    def preview_write_file(path: str, content: str):
        try:
            p = workspace.resolve(path)
        except WorkspaceViolation as exc:
            return {'ok': False, 'error': str(exc)}
        gate = _approval_for_sensitive(approval, p, 'Preview write to')
        if gate and not gate.get('allowed'):
            return gate
        old = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
        return {'path': str(p), 'exists': p.exists(), 'diff': _preview(p, old, content),
                'bytes_before': len(old.encode('utf-8')), 'bytes_after': len(content.encode('utf-8')), 'sensitive': bool(gate)}

    def write_file(path: str, content: str):
        try:
            p = workspace.resolve(path)
        except WorkspaceViolation as exc:
            return {'ok': False, 'error': str(exc)}
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
        snapshot_id = None
        if snapshot_manager is not None:
            try:
                snapshot_id = snapshot_manager.create_for_path(p, 'AI workspace file write')['snapshot_id']
            except Exception as exc:
                return {'ok': False, 'blocked': True, 'error': f'Pre-change workspace snapshot failed: {exc}'}
        try:
            result = workspace.write_text(path, content)
            if not p.exists():
                return {'ok': False, 'error': f'Failed to write file: {p} does not exist after write operation'}
        except Exception as exc:
            return {'ok': False, 'error': f'Failed to write file: {exc}'}

        return {'ok': True, 'path': result, 'bytes': len(content.encode('utf-8')),
                'diff': '[REDACTED: sensitive file diff]' if sensitive else diff, 'sensitive': sensitive,
                'snapshot_id': snapshot_id}

    def edit_file(path: str, old_str: str, new_str: str):
        try:
            p = workspace.resolve(path)
        except WorkspaceViolation as exc:
            return {'ok': False, 'error': str(exc)}
        if not p.exists():
            return {'ok': False, 'error': f'File not found: {path}'}
        if p.is_dir():
            return {'ok': False, 'error': f'Path is a directory: {path}'}

        sensitive = is_sensitive_path(p)
        if sensitive:
            gate = _approval_for_sensitive(approval, p, 'Edit')
            if gate and not gate.get('allowed'):
                return gate

        old_content = p.read_text(encoding='utf-8', errors='replace')
        if old_str not in old_content:
            return {'ok': False, 'error': f'Target string not found in {path}'}
        new_content = old_content.replace(old_str, new_str, 1)
        diff = _preview(p, old_content, new_content)

        if require_write_approval and not sensitive:
            if approval is None:
                return {'ok': False, 'error': 'Write approval is required but no approval manager is configured.'}
            req = approval.request(f'Edit file {p}', f'Workspace file edit. Diff:\n{diff[:5000]}', 'WRITE_WORKSPACE')
            if not req.get('allowed'):
                return {'ok': False, 'approval_required': True, **req, 'diff': diff}

        snapshot_id = None
        if snapshot_manager is not None:
            try:
                snapshot_id = snapshot_manager.create_for_path(p, 'AI workspace file edit')['snapshot_id']
            except Exception as exc:
                return {'ok': False, 'blocked': True, 'error': f'Pre-change workspace snapshot failed: {exc}'}

        try:
            result = workspace.edit_text(path, old_str, new_str)
        except Exception as exc:
            return {'ok': False, 'error': f'Failed to edit file: {exc}'}

        return {'ok': True, 'path': result, 'diff': '[REDACTED: sensitive file diff]' if sensitive else diff,
                'sensitive': sensitive, 'snapshot_id': snapshot_id}

    def delete_file(path: str, recursive: bool = False):
        try:
            p = workspace.resolve(path)
        except WorkspaceViolation as exc:
            return {'ok': False, 'error': str(exc)}
        if not p.exists():
            return {'ok': False, 'error': f'File/directory not found: {path}'}

        # Root protection
        for root in workspace.roots:
            if p == root:
                return {'ok': False, 'error': f'Cannot delete workspace root directory: {p}'}

        sensitive = is_sensitive_path(p)
        if sensitive:
            gate = _approval_for_sensitive(approval, p, 'Delete')
            if gate and not gate.get('allowed'):
                return gate

        if require_write_approval and not sensitive:
            if approval is None:
                return {'ok': False, 'error': 'Delete approval is required but no approval manager is configured.'}
            req = approval.request(f'Delete {"directory" if p.is_dir() else "file"} {p}',
                                   f'Workspace deletion target: {p}', 'WRITE_WORKSPACE')
            if not req.get('allowed'):
                return {'ok': False, 'approval_required': True, **req}

        snapshot_id = None
        if snapshot_manager is not None:
            try:
                snapshot_id = snapshot_manager.create_for_path(p, 'AI workspace file deletion')['snapshot_id']
            except Exception as exc:
                return {'ok': False, 'blocked': True, 'error': f'Pre-change workspace snapshot failed: {exc}'}

        try:
            workspace.delete(path, recursive=recursive)
        except Exception as exc:
            return {'ok': False, 'error': f'Failed to delete: {exc}'}

        return {'ok': True, 'path': str(p), 'deleted': True, 'snapshot_id': snapshot_id}

    def search_files(query: str, path: str = '.', limit: int = 50, regex: bool = False,
                     extensions: list[str] | None = None):
        try:
            root = workspace.resolve(path)
        except WorkspaceViolation as exc:
            return {'ok': False, 'error': str(exc)}
        if not root.exists():
            return []
        out = []
        bounded_limit = max(1, min(int(limit), 1000))
        ext_filter = {str(x).lower() if str(x).startswith('.') else '.' + str(x).lower() for x in (extensions or []) if str(x).strip()}
        pattern = None
        if regex:
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error as exc:
                return {'ok': False, 'error': f'Invalid search regex: {exc}'}
        q = query.lower()
        is_glob = not regex and any(c in q for c in ('*', '?', '['))
        candidates_iter = [root] if root.is_file() else root.rglob('*')
        for p in candidates_iter:
            if len(out) >= bounded_limit:
                break
            if not p.is_file() or (ext_filter and p.suffix.lower() not in ext_filter):
                continue
            if pattern:
                filename_match = bool(pattern.search(p.name))
            elif is_glob:
                filename_match = fnmatch.fnmatch(p.name.lower(), q)
            elif q in ('', '.'):
                filename_match = True
            else:
                filename_match = q in p.name.lower()
            if filename_match:
                out.append({'path': str(p), 'match': 'filename', 'sensitive': is_sensitive_path(p)})
                continue
            if is_sensitive_path(p):
                # Never index/search sensitive contents without an explicit targeted read approval.
                continue
            try:
                if p.stat().st_size > 2_000_000:
                    continue
                data = p.read_bytes()
                sample = data[:8192]
                # NUL bytes or a high proportion of non-text control bytes are a
                # strong binary signal. Skip content decoding in that case.
                controls = sum(1 for b in sample if b < 32 and b not in (9, 10, 13))
                if b'\x00' in sample or (sample and controls / len(sample) > 0.10):
                    continue
                txt = data.decode('utf-8', errors='ignore')
                matched = bool(pattern.search(txt)) if pattern else (fnmatch.fnmatch(txt.lower(), q) if is_glob else q in txt.lower())
                if matched:
                    out.append({'path': str(p), 'match': 'content'})
            except Exception:
                pass
        return out

    return [
        Tool('list_files', 'List files/directories inside an approved workspace. Path can be ".", "books", "workspace/books", or any subpath.',
             {'type':'object','properties':{'path':{'type':'string','default':'.'}}}, list_files),
        Tool('read_file', 'Read a UTF-8 text file or extract PDF text inside an approved workspace. Sensitive credential/key files require explicit approval.',
             {'type':'object','properties':{'path':{'type':'string'}},'required':['path']}, read_file),
        Tool('preview_write_file', 'Preview the unified diff for a proposed text-file write without changing the file. Sensitive files require approval.',
             {'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}, preview_write_file),
        Tool('write_file', 'Write text inside an approved workspace. Sensitive files always require explicit approval.',
             {'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}, write_file),
        Tool('edit_file', 'Edit a text file inside an approved workspace by replacing an exact string match (old_str) with new text (new_str).',
             {'type':'object','properties':{'path':{'type':'string'},'old_str':{'type':'string'},'new_str':{'type':'string'}},'required':['path','old_str','new_str']}, edit_file),
        Tool('delete_file', 'Delete a file or directory inside an approved workspace. Setting recursive=True deletes directories and their contents. Root workspace directories cannot be deleted.',
             {'type':'object','properties':{'path':{'type':'string'},'recursive':{'type':'boolean','default':False}},'required':['path']}, delete_file),
        Tool('search_files', 'Search filenames/text inside an approved workspace with optional regex, wildcard (*.pdf), and extension filtering. Path can be ".", "workspace", "books", "workspace/books", etc.',
             {'type':'object','properties':{'query':{'type':'string'},'path':{'type':'string','default':'.'},'limit':{'type':'integer','default':50},'regex':{'type':'boolean','default':False},'extensions':{'type':'array','items':{'type':'string'}}},'required':['query']}, search_files),
    ]
