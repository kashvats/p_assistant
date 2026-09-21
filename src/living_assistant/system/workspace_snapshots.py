from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import uuid

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.security.security_utils import redact_secrets


_EXCLUDED_DIRS = {
    '.git', '.hg', '.svn', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    '.tox', '.nox', '.venv', 'venv', 'env', 'node_modules', 'bower_components',
    'vendor', 'dist', 'build', 'target', '.next', '.nuxt', '.output', 'coverage',
    'htmlcov', '.cache', '.turbo', '.living-assistant-backups',
}
_MANIFEST_NAME = '.living-assistant-snapshot.json'
_SCHEMA = '''
CREATE TABLE IF NOT EXISTS workspace_snapshots(
  id TEXT PRIMARY KEY,
  root_path TEXT NOT NULL,
  archive_path TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  file_count INTEGER NOT NULL,
  total_bytes INTEGER NOT NULL,
  skipped_symlinks INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS workspace_snapshots_root_time_idx
ON workspace_snapshots(root_path, created_at DESC);
'''


class WorkspaceSnapshotManager:
    """Source-tree snapshots for AI-driven workspace mutation recovery.

    Dependency/build/VCS metadata directories are intentionally excluded so automatic
    snapshots remain bounded and restore source state without corrupting package caches
    or Git internals. Credential files are included in the archive because recovery
    must be faithful, but archive contents are never exposed through the public API.
    """

    def __init__(
        self,
        workspace: Workspace,
        root: Path | None = None,
        db_path: Path | None = None,
        *,
        max_files: int = 50_000,
        max_total_bytes: int = 2_000_000_000,
        retention_per_root: int = 30,
    ):
        self.workspace = workspace
        self.root = (root or (data_dir() / 'workspace_snapshots')).expanduser().resolve()
        for workspace_root in workspace.roots:
            try:
                self.root.relative_to(workspace_root)
            except ValueError:
                continue
            raise ValueError('Snapshot storage must be outside approved workspace roots.')
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt':
            try:
                self.root.chmod(0o700)
            except OSError:
                pass
        self.db_path = db_path or (data_dir() / 'assistant.sqlite3')
        self.conn = ThreadLocalSQLite(self.db_path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        self.max_files = max(1, min(int(max_files), 500_000))
        self.max_total_bytes = max(1_000_000, min(int(max_total_bytes), 20_000_000_000))
        self.retention_per_root = max(1, min(int(retention_per_root), 500))

    def project_root_for(self, path: str | Path) -> Path:
        resolved = self.workspace.resolve(path)
        candidates: list[Path] = []
        for root in self.workspace.roots:
            try:
                resolved.relative_to(root)
                candidates.append(root)
            except ValueError:
                continue
        if not candidates:
            raise WorkspaceViolation(f'No approved workspace root contains {resolved}')
        return max(candidates, key=lambda item: len(item.parts))

    @staticmethod
    def _safe_symlink(path: Path, root: Path) -> bool:
        try:
            raw = os.readlink(path)
        except OSError:
            return False
        if os.path.isabs(raw):
            return False
        try:
            target = (path.parent / raw).resolve()
            target.relative_to(root)
            return True
        except (OSError, ValueError, RuntimeError):
            return False

    def _iter_entries(self, root: Path):
        for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            dirnames[:] = [name for name in dirnames if name not in _EXCLUDED_DIRS]
            for name in sorted(filenames):
                yield current_path / name
            for name in sorted(dirnames):
                candidate = current_path / name
                if candidate.is_symlink():
                    yield candidate

    def create_for_path(self, path: str | Path, reason: str) -> dict:
        return self.create(self.project_root_for(path), reason)

    def create(self, project_root: str | Path, reason: str = 'manual snapshot') -> dict:
        root = self.workspace.resolve(project_root)
        if not root.is_dir():
            raise ValueError(f'Snapshot root is not a directory: {root}')
        safe_reason = redact_secrets(reason, 500)
        snapshot_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        project_key = uuid.uuid5(uuid.NAMESPACE_URL, str(root)).hex[:16]
        target_dir = self.root / project_key
        target_dir.mkdir(parents=True, exist_ok=True)
        archive = target_dir / f'{snapshot_id}.tar.gz'
        file_count = 0
        total_bytes = 0
        skipped_symlinks = 0
        manifest_files: list[str] = []

        with tempfile.NamedTemporaryFile(prefix='snapshot-', suffix='.tar.gz', dir=target_dir, delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            with tarfile.open(temp_path, 'w:gz', dereference=False) as tar:
                for path in self._iter_entries(root):
                    rel = path.relative_to(root).as_posix()
                    if path.is_symlink():
                        if not self._safe_symlink(path, root):
                            skipped_symlinks += 1
                            continue
                        tar.add(path, arcname=rel, recursive=False)
                        manifest_files.append(rel)
                        file_count += 1
                        continue
                    try:
                        size = path.stat().st_size
                    except OSError:
                        continue
                    if file_count + 1 > self.max_files or total_bytes + size > self.max_total_bytes:
                        raise RuntimeError('Workspace snapshot exceeds configured file/size limits; refusing mutation without a complete recovery point.')
                    tar.add(path, arcname=rel, recursive=False)
                    manifest_files.append(rel)
                    file_count += 1
                    total_bytes += size

                manifest = {
                    'id': snapshot_id,
                    'root': str(root),
                    'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'reason': safe_reason,
                    'files': manifest_files,
                    'excluded_dirs': sorted(_EXCLUDED_DIRS),
                }
                payload = json.dumps(manifest, sort_keys=True).encode('utf-8')
                info = tarfile.TarInfo(_MANIFEST_NAME)
                info.size = len(payload)
                info.mode = 0o600
                info.mtime = int(dt.datetime.now().timestamp())
                import io
                tar.addfile(info, io.BytesIO(payload))
            temp_path.replace(archive)
            if os.name != 'nt':
                try:
                    archive.chmod(0o600)
                except OSError:
                    pass
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        created_at = dt.datetime.now(dt.timezone.utc).isoformat()
        self.conn.execute(
            'INSERT INTO workspace_snapshots(id,root_path,archive_path,reason,created_at,file_count,total_bytes,skipped_symlinks) VALUES(?,?,?,?,?,?,?,?)',
            (snapshot_id, str(root), str(archive), safe_reason, created_at, file_count, total_bytes, skipped_symlinks),
        )
        self.conn.commit()
        self._prune(str(root))
        return {
            'ok': True,
            'snapshot_id': snapshot_id,
            'root': str(root),
            'created_at': created_at,
            'file_count': file_count,
            'total_bytes': total_bytes,
            'skipped_symlinks': skipped_symlinks,
        }

    def _prune(self, root_path: str) -> None:
        rows = self.conn.execute(
            'SELECT id,archive_path FROM workspace_snapshots WHERE root_path=? ORDER BY created_at DESC',
            (root_path,),
        ).fetchall()
        for row in rows[self.retention_per_root:]:
            try:
                Path(row[1]).unlink(missing_ok=True)
            except OSError:
                continue
            self.conn.execute('DELETE FROM workspace_snapshots WHERE id=?', (row[0],))
        self.conn.commit()

    def list(self, project_root: str | Path | None = None, limit: int = 50) -> list[dict]:
        bounded = max(1, min(int(limit), 500))
        if project_root is None:
            rows = self.conn.execute(
                'SELECT id,root_path,reason,created_at,file_count,total_bytes,skipped_symlinks FROM workspace_snapshots ORDER BY created_at DESC LIMIT ?',
                (bounded,),
            ).fetchall()
        else:
            root = self.workspace.resolve(project_root)
            rows = self.conn.execute(
                'SELECT id,root_path,reason,created_at,file_count,total_bytes,skipped_symlinks FROM workspace_snapshots WHERE root_path=? ORDER BY created_at DESC LIMIT ?',
                (str(root), bounded),
            ).fetchall()
        return [
            {
                'snapshot_id': row[0], 'root': row[1], 'reason': row[2], 'created_at': row[3],
                'file_count': row[4], 'total_bytes': row[5], 'skipped_symlinks': row[6],
            }
            for row in rows
        ]

    def _lookup(self, snapshot_id: str):
        row = self.conn.execute(
            'SELECT id,root_path,archive_path,reason,created_at,file_count,total_bytes,skipped_symlinks FROM workspace_snapshots WHERE id=?',
            (snapshot_id,),
        ).fetchone()
        if not row:
            raise KeyError(snapshot_id)
        return row

    @staticmethod
    def _validate_members(members: list[tarfile.TarInfo]) -> None:
        for member in members:
            name = member.name.replace('\\', '/')
            parts = Path(name).parts
            if name.startswith('/') or '..' in parts:
                raise RuntimeError('Snapshot archive contains an unsafe path.')
            if member.isdev() or member.isfifo():
                raise RuntimeError('Snapshot archive contains an unsupported special file.')
            if member.issym() or member.islnk():
                link = member.linkname.replace('\\', '/')
                if os.path.isabs(link) or '..' in Path(link).parts:
                    raise RuntimeError('Snapshot archive contains an unsafe link target.')

    @staticmethod
    def _clear_managed_source(root: Path) -> None:
        for current, dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
            current_path = Path(current)
            rel_parts = current_path.relative_to(root).parts if current_path != root else ()
            if any(part in _EXCLUDED_DIRS for part in rel_parts):
                continue
            for name in filenames:
                path = current_path / name
                try:
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                except OSError:
                    pass
            for name in dirnames:
                if name in _EXCLUDED_DIRS:
                    continue
                path = current_path / name
                try:
                    if path.is_symlink():
                        path.unlink()
                    elif path.is_dir() and not any(path.iterdir()):
                        path.rmdir()
                except OSError:
                    pass

    def restore(self, snapshot_id: str) -> dict:
        row = self._lookup(str(snapshot_id).strip())
        root = self.workspace.resolve(row[1])
        archive = Path(row[2]).expanduser().resolve()
        try:
            archive.relative_to(self.root)
        except ValueError as exc:
            raise RuntimeError('Snapshot archive path is outside the configured snapshot store.') from exc
        if not archive.is_file():
            raise FileNotFoundError(f'Snapshot archive is missing: {snapshot_id}')

        safety = self.create(root, reason=f'pre-restore safety snapshot before {snapshot_id}')
        with tempfile.TemporaryDirectory(prefix='living-assistant-restore-') as temp_dir:
            temp_root = Path(temp_dir)
            with tarfile.open(archive, 'r:gz') as tar:
                members = tar.getmembers()
                self._validate_members(members)
                extract_members = [member for member in members if member.name != _MANIFEST_NAME]
                # Prefer the hardened stdlib extraction filter where available,
                # while retaining Python 3.11 compatibility after our own validation.
                try:
                    tar.extractall(temp_root, members=extract_members, filter='data')
                except TypeError:
                    tar.extractall(temp_root, members=extract_members)
            self._clear_managed_source(root)
            for current, dirnames, filenames in os.walk(temp_root, topdown=True, followlinks=False):
                current_path = Path(current)
                rel = current_path.relative_to(temp_root)
                target_dir = root / rel
                target_dir.mkdir(parents=True, exist_ok=True)
                for name in filenames:
                    source = current_path / name
                    target = target_dir / name
                    if source.is_symlink():
                        link = os.readlink(source)
                        target.unlink(missing_ok=True)
                        target.symlink_to(link)
                    else:
                        shutil.copy2(source, target)
                for name in list(dirnames):
                    source = current_path / name
                    if source.is_symlink():
                        target = target_dir / name
                        target.unlink(missing_ok=True)
                        target.symlink_to(os.readlink(source), target_is_directory=True)
                        dirnames.remove(name)

        return {
            'ok': True,
            'snapshot_id': snapshot_id,
            'root': str(root),
            'pre_restore_snapshot_id': safety['snapshot_id'],
        }
