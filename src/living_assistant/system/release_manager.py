from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import venv
import zipfile

STATE_SCHEMA = 1
DATA_SCHEMA = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def default_runtime_root() -> Path:
    override = os.environ.get('LIVING_ASSISTANT_INSTALL_ROOT')
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system()
    home = Path.home()
    if system == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA') or (home / 'AppData' / 'Local'))
        return base / 'LivingAssistant' / 'Runtime'
    if system == 'Darwin':
        return home / 'Library' / 'Application Support' / 'LivingAssistantRuntime'
    base = Path(os.environ.get('XDG_DATA_HOME') or (home / '.local' / 'share'))
    return base / 'LivingAssistantRuntime'


def default_data_root() -> Path:
    override = os.environ.get('LIVING_ASSISTANT_DATA_ROOT')
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system()
    home = Path.home()
    if system == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA') or (home / 'AppData' / 'Local'))
        # platformdirs app=LivingAssistant, author=LivingAssistant uses this shape on Windows.
        return base / 'LivingAssistant' / 'LivingAssistant'
    if system == 'Darwin':
        return home / 'Library' / 'Application Support' / 'LivingAssistant'
    base = Path(os.environ.get('XDG_DATA_HOME') or (home / '.local' / 'share'))
    return base / 'LivingAssistant'


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, indent=2, sort_keys=True)
            f.flush()
            try: os.fsync(f.fileno())
            except OSError: pass
        os.replace(temp, path)
    finally:
        try: Path(temp).unlink(missing_ok=True)
        except Exception: pass


def _safe_version(value: str) -> str:
    value = str(value).strip()
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._+-')
    if not value or any(ch not in allowed for ch in value) or value in {'.', '..'}:
        raise ValueError('unsafe version string')
    return value


def _venv_python(env_dir: Path) -> Path:
    return env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def _venv_organism(env_dir: Path) -> Path:
    return env_dir / ('Scripts/organism.exe' if os.name == 'nt' else 'bin/organism')


def _copy_sqlite_consistently(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True, timeout=5)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()


def _snapshot_data_tree(data_root: Path, archive: Path) -> dict:
    """Create a local data backup with a consistent SQLite snapshot.

    Browser caches and transient evaluation worktrees are intentionally excluded;
    user state, quarantine, models, connectors, projects, and databases are retained.
    """
    archive.parent.mkdir(parents=True, exist_ok=True)
    exclusions = {'evaluation_worktrees', 'canary_worktrees', 'browser_profiles', 'logs', '__pycache__'}
    file_count = 0
    with tempfile.TemporaryDirectory(prefix='living-assistant-backup-') as td:
        stage = Path(td) / 'data'
        stage.mkdir()
        if data_root.exists():
            for src in data_root.rglob('*'):
                rel = src.relative_to(data_root)
                if any(part in exclusions for part in rel.parts):
                    continue
                dst = stage / rel
                try:
                    if src.is_symlink():
                        continue
                    if src.is_dir():
                        dst.mkdir(parents=True, exist_ok=True)
                    elif src.is_file():
                        if src.suffix.lower() in {'.sqlite', '.sqlite3', '.db'}:
                            try:
                                _copy_sqlite_consistently(src, dst)
                            except sqlite3.Error:
                                shutil.copy2(src, dst)
                        else:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dst)
                        file_count += 1
                except (OSError, PermissionError):
                    # Backups are best effort for volatile/locked files; the manifest
                    # makes the fact visible rather than aborting the whole update.
                    continue
        manifest = {'created_at': utc_now(), 'data_root': str(data_root), 'file_count': file_count, 'data_schema': DATA_SCHEMA}
        (stage / '.backup-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for item in stage.rglob('*'):
                if item.is_file(): zf.write(item, item.relative_to(stage).as_posix())
    if os.name != 'nt':
        try: archive.chmod(0o600)
        except OSError: pass
    return {'path': str(archive), **manifest, 'sha256': sha256_file(archive)}


def _restore_data_tree(archive: Path, data_root: Path) -> dict:
    if not archive.is_file(): raise FileNotFoundError(archive)
    with tempfile.TemporaryDirectory(prefix='living-assistant-restore-') as td:
        stage = Path(td)
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = info.filename
                target = (stage / name).resolve()
                if stage.resolve() not in target.parents and target != stage.resolve():
                    raise ValueError('unsafe backup archive path')
            zf.extractall(stage)
        data_root.mkdir(parents=True, exist_ok=True)
        for item in stage.iterdir():
            if item.name == '.backup-manifest.json': continue
            dst = data_root / item.name
            if dst.exists():
                if dst.is_dir(): shutil.rmtree(dst)
                else: dst.unlink()
            if item.is_dir(): shutil.copytree(item, dst)
            else: shutil.copy2(item, dst)
    return {'ok': True, 'archive': str(archive), 'data_root': str(data_root)}


def ensure_data_schema(data_root: Path) -> dict:
    """Run conservative, idempotent data migrations.

    v1 introduces only a schema marker. Existing SQLite tables remain managed by
    their owning stores with CREATE IF NOT EXISTS, making code rollback safe.
    """
    data_root.mkdir(parents=True, exist_ok=True)
    marker = data_root / 'data_schema.json'
    current = 0
    if marker.exists():
        try: current = int(json.loads(marker.read_text(encoding='utf-8')).get('schema', 0))
        except Exception: current = 0
    if current > DATA_SCHEMA:
        raise RuntimeError(f'data schema {current} is newer than supported {DATA_SCHEMA}')
    applied = []
    if current < 1:
        current = 1; applied.append(1)
    _atomic_json(marker, {'schema': current, 'updated_at': utc_now()})
    return {'schema': current, 'applied': applied}


def read_data_schema(data_root: Path) -> int:
    marker = data_root / 'data_schema.json'
    if not marker.exists(): return 0
    try: return int(json.loads(marker.read_text(encoding='utf-8')).get('schema', 0))
    except Exception: return 0


def _service_action(action: str) -> dict:
    """Best-effort user-service lifecycle action; never elevates privileges."""
    system = platform.system()
    try:
        if system == 'Windows':
            if not shutil.which('schtasks'): return {'ok': True, 'supported': False}
            if action == 'restart':
                subprocess.run(['schtasks','/End','/TN','LivingAssistant'],capture_output=True,text=True,timeout=15)
                p=subprocess.run(['schtasks','/Run','/TN','LivingAssistant'],capture_output=True,text=True,timeout=15)
            elif action == 'remove':
                p=subprocess.run(['schtasks','/Delete','/TN','LivingAssistant','/F'],capture_output=True,text=True,timeout=15)
            else: return {'ok':False,'error':'unsupported action'}
            return {'ok': p.returncode == 0, 'supported': True, 'detail': (p.stdout or p.stderr)[-2000:]}
        if system == 'Darwin':
            launchctl=shutil.which('launchctl')
            if not launchctl: return {'ok': True, 'supported': False}
            uid=str(os.getuid()) if hasattr(os,'getuid') else ''
            label='com.livingassistant.daemon'; plist=Path.home()/'Library/LaunchAgents/com.livingassistant.daemon.plist'
            if action == 'restart':
                p=subprocess.run([launchctl,'kickstart','-k',f'gui/{uid}/{label}'],capture_output=True,text=True,timeout=15)
            elif action == 'remove':
                p=subprocess.run([launchctl,'bootout',f'gui/{uid}',str(plist)],capture_output=True,text=True,timeout=15)
                try: plist.unlink(missing_ok=True)
                except OSError: pass
            else: return {'ok':False,'error':'unsupported action'}
            # bootout returns nonzero if it was not installed; treat that as harmless on uninstall.
            return {'ok': p.returncode == 0 or action == 'remove', 'supported': True, 'detail': (p.stdout or p.stderr)[-2000:]}
        if system == 'Linux':
            systemctl=shutil.which('systemctl')
            if not systemctl: return {'ok': True, 'supported': False}
            if action == 'restart':
                p=subprocess.run([systemctl,'--user','try-restart','living-assistant.service'],capture_output=True,text=True,timeout=20)
            elif action == 'remove':
                subprocess.run([systemctl,'--user','disable','--now','living-assistant.service'],capture_output=True,text=True,timeout=20)
                unit=Path.home()/'.config/systemd/user/living-assistant.service'
                try: unit.unlink(missing_ok=True)
                except OSError: pass
                subprocess.run([systemctl,'--user','daemon-reload'],capture_output=True,text=True,timeout=20)
                return {'ok':True,'supported':True}
            else: return {'ok':False,'error':'unsupported action'}
            # try-restart returns success when inactive on systemd; that's what we want.
            return {'ok': p.returncode == 0, 'supported': True, 'detail': (p.stdout or p.stderr)[-2000:]}
    except Exception as exc:
        return {'ok':False,'supported':True,'error':str(exc)}
    return {'ok':True,'supported':False}


def restart_user_service_if_installed() -> dict:
    return _service_action('restart')


def remove_user_service() -> dict:
    return _service_action('remove')


@dataclass
class InstallLayout:
    runtime_root: Path
    data_root: Path

    @property
    def versions(self) -> Path: return self.runtime_root / 'versions'
    @property
    def bin(self) -> Path: return self.runtime_root / 'bin'
    @property
    def backups(self) -> Path: return self.runtime_root / 'backups'
    @property
    def state_file(self) -> Path: return self.runtime_root / 'install-state.json'


class ReleaseManager:
    def __init__(self, runtime_root: str | Path | None = None, data_root: str | Path | None = None):
        self.layout = InstallLayout(
            Path(runtime_root).expanduser().resolve() if runtime_root else default_runtime_root(),
            Path(data_root).expanduser().resolve() if data_root else default_data_root(),
        )
        self.layout.runtime_root.mkdir(parents=True, exist_ok=True)
        self.layout.versions.mkdir(parents=True, exist_ok=True)
        self.layout.bin.mkdir(parents=True, exist_ok=True)
        self.layout.backups.mkdir(parents=True, exist_ok=True)

    def _empty_state(self) -> dict:
        return {'schema': STATE_SCHEMA, 'current_version': None, 'previous_version': None, 'installations': {}, 'history': []}

    def state(self) -> dict:
        if not self.layout.state_file.exists(): return self._empty_state()
        try:
            data = json.loads(self.layout.state_file.read_text(encoding='utf-8'))
        except Exception as exc:
            raise RuntimeError(f'Install state is unreadable: {exc}') from exc
        if int(data.get('schema', 0)) > STATE_SCHEMA:
            raise RuntimeError('Install state belongs to a newer installer')
        base = self._empty_state(); base.update(data)
        return base

    def _write_state(self, state: dict) -> None:
        state['schema'] = STATE_SCHEMA
        _atomic_json(self.layout.state_file, state)

    def _version_dir(self, version: str) -> Path:
        return self.layout.versions / _safe_version(version)

    def _write_shims(self, version: str) -> list[str]:
        env = self._version_dir(version) / 'venv'
        organism = _venv_organism(env)
        py = _venv_python(env)
        if not organism.exists() or not py.exists():
            raise RuntimeError(f'Installed runtime is incomplete for {version}')
        written=[]
        if os.name == 'nt':
            cmd = self.layout.bin / 'organism.cmd'
            cmd.write_text(f'@echo off\r\n"{organism}" %*\r\n', encoding='utf-8')
            pycmd = self.layout.bin / 'living-assistant-python.cmd'
            pycmd.write_text(f'@echo off\r\n"{py}" %*\r\n', encoding='utf-8')
            daemoncmd = self.layout.bin / 'living-assistant-daemon.cmd'
            daemoncmd.write_text(f'@echo off\r\n"{organism}" daemon %*\r\n', encoding='utf-8')
            written += [str(cmd), str(pycmd), str(daemoncmd)]
        else:
            sh = self.layout.bin / 'organism'
            sh.write_text('#!/bin/sh\nexec ' + shlex.quote(str(organism)) + ' "$@"\n', encoding='utf-8')
            sh.chmod(0o755)
            pysh = self.layout.bin / 'living-assistant-python'
            pysh.write_text('#!/bin/sh\nexec ' + shlex.quote(str(py)) + ' "$@"\n', encoding='utf-8')
            pysh.chmod(0o755)
            daemonsh = self.layout.bin / 'living-assistant-daemon'
            daemonsh.write_text('#!/bin/sh\nexec ' + shlex.quote(str(organism)) + ' daemon "$@"\n', encoding='utf-8')
            daemonsh.chmod(0o755)
            written += [str(sh), str(pysh), str(daemonsh)]
        return written

    def create_backup(self, label: str | None = None) -> dict:
        tag = (label or datetime.now().strftime('%Y%m%d-%H%M%S')).replace('/', '_').replace('\\', '_')
        archive = self.layout.backups / f'data-{tag}.zip'
        result = _snapshot_data_tree(self.layout.data_root, archive)
        state=self.state(); state['history'].append({'action':'backup','at':utc_now(),'backup':result['path'],'sha256':result['sha256']}); self._write_state(state)
        return result

    def _inspect_wheel_version(self, wheel: Path) -> str:
        if not wheel.is_file() or wheel.suffix != '.whl': raise ValueError('A .whl file is required')
        with zipfile.ZipFile(wheel) as zf:
            metas=[n for n in zf.namelist() if n.endswith('.dist-info/METADATA')]
            if len(metas)!=1: raise ValueError('Wheel metadata not found')
            text=zf.read(metas[0]).decode('utf-8','replace')
        name = version = None
        for line in text.splitlines():
            if line.startswith('Name: '): name = line.split(':',1)[1].strip().lower().replace('_','-')
            elif line.startswith('Version: '): version = line.split(':',1)[1].strip()
        if name != 'living-assistant': raise ValueError('Wheel is not the Living Assistant package')
        if not version: raise ValueError('Wheel version not found')
        return _safe_version(version)

    def install_wheel(self, wheel: str | Path, *, extras: list[str] | None = None, with_dependencies: bool = True, make_backup: bool = True, expected_sha256: str | None = None) -> dict:
        wheel = Path(wheel).expanduser().resolve()
        actual_sha = sha256_file(wheel)
        if expected_sha256 and actual_sha.lower() != expected_sha256.strip().lower():
            raise RuntimeError('Wheel SHA-256 does not match the expected release checksum')
        version = self._inspect_wheel_version(wheel)
        target = self._version_dir(version)
        state = self.state()
        previous = state.get('current_version')
        if previous == version and version in state.get('installations', {}) and _venv_organism(target / 'venv').exists():
            return {'ok': True, 'version': version, 'already_current': True, 'runtime': str(target), 'data_root': str(self.layout.data_root), 'bin': str(self.layout.bin)}
        backup = None
        if previous and previous != version and make_backup:
            backup = self.create_backup(f'before-{version}')
            state = self.state()

        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        env = target / 'venv'
        data_touched = False
        try:
            venv.EnvBuilder(with_pip=True, clear=True).create(env)
            py = _venv_python(env)
            spec = str(wheel)
            extras = [x.strip() for x in (extras or []) if x.strip()]
            if any(not x.replace('-', '').replace('_', '').isalnum() for x in extras):
                raise ValueError('Invalid optional dependency group name')
            if extras: spec += '[' + ','.join(sorted(set(extras))) + ']'
            cmd=[str(py), '-m', 'pip', 'install', '--disable-pip-version-check']
            if not with_dependencies: cmd.append('--no-deps')
            cmd.append(spec)
            proc=subprocess.run(cmd, text=True, capture_output=True, timeout=1200)
            if proc.returncode != 0:
                raise RuntimeError('pip install failed: ' + (proc.stderr or proc.stdout)[-6000:])
            check=subprocess.run([str(py), '-c', 'import living_assistant; print(living_assistant.__version__)'], text=True, capture_output=True, timeout=30)
            if check.returncode != 0 or check.stdout.strip() != version:
                raise RuntimeError('installed package self-check failed: ' + (check.stderr or check.stdout)[-2000:])
            data_touched = True
            ensure_data_schema(self.layout.data_root)
            shims=self._write_shims(version)
            state=self.state()
            installations=state.setdefault('installations',{})
            installations[version]={
                'version':version,'installed_at':utc_now(),'path':str(target),'wheel_sha256':actual_sha,
                'extras':extras,'dependencies_installed':bool(with_dependencies),
            }
            state['previous_version']=previous if previous != version else state.get('previous_version')
            state['current_version']=version
            state['history'].append({'action':'install' if not previous else 'update','at':utc_now(),'version':version,'previous':previous,'backup':backup['path'] if backup else None})
            self._write_state(state)
            service=restart_user_service_if_installed()
            return {'ok':True,'version':version,'previous_version':previous,'runtime':str(target),'data_root':str(self.layout.data_root),'bin':str(self.layout.bin),'shims':shims,'backup':backup,'service_restart':service}
        except Exception:
            if data_touched and backup:
                try: _restore_data_tree(Path(backup['path']), self.layout.data_root)
                except Exception: pass
            shutil.rmtree(target, ignore_errors=True)
            if previous and previous in self.state().get('installations',{}):
                try: self._write_shims(previous)
                except Exception: pass
            raise

    def rollback(self, version: str | None = None, *, restore_backup: str | Path | None = None) -> dict:
        state=self.state(); current=state.get('current_version')
        target=version or state.get('previous_version')
        if not target: raise RuntimeError('No previous version is recorded')
        target=_safe_version(target)
        if target not in state.get('installations',{}): raise RuntimeError(f'Version {target} is not installed')
        if not self._version_dir(target).exists(): raise RuntimeError(f'Runtime directory for {target} is missing')
        if restore_backup:
            _restore_data_tree(Path(restore_backup).expanduser().resolve(), self.layout.data_root)
            ensure_data_schema(self.layout.data_root)
        self._write_shims(target)
        state['previous_version']=current
        state['current_version']=target
        state['history'].append({'action':'rollback','at':utc_now(),'from':current,'to':target,'restored_backup':str(restore_backup) if restore_backup else None})
        self._write_state(state)
        service=restart_user_service_if_installed()
        return {'ok':True,'from':current,'to':target,'data_restored':bool(restore_backup),'service_restart':service}

    def remove_version(self, version: str) -> dict:
        version=_safe_version(version); state=self.state()
        if state.get('current_version') == version:
            raise RuntimeError('Refusing to remove the active version; rollback first')
        target=self._version_dir(version)
        shutil.rmtree(target, ignore_errors=True)
        state.get('installations',{}).pop(version,None)
        if state.get('previous_version') == version: state['previous_version']=None
        state['history'].append({'action':'remove_version','at':utc_now(),'version':version})
        self._write_state(state)
        return {'ok':True,'removed':version}

    def uninstall_runtime(self, *, purge_data: bool = False, confirm_purge: bool = False, remove_service: bool = True) -> dict:
        if purge_data and not confirm_purge:
            raise RuntimeError('Data purge requires explicit confirmation')
        state=self.state(); current=state.get('current_version')
        service = remove_user_service() if remove_service else {'ok': True, 'removed': False, 'reason': 'not requested'}
        # Shims first so new processes cannot start while runtimes are removed.
        if self.layout.bin.exists(): shutil.rmtree(self.layout.bin, ignore_errors=True)
        if self.layout.versions.exists(): shutil.rmtree(self.layout.versions, ignore_errors=True)
        state['current_version']=None; state['previous_version']=None; state['installations']={}
        state['history'].append({'action':'uninstall_runtime','at':utc_now(),'previous':current})
        self._write_state(state)
        purged=False
        if purge_data:
            shutil.rmtree(self.layout.data_root, ignore_errors=True); purged=True
        return {'ok':True,'runtime_removed':True,'data_preserved':not purged,'data_root':str(self.layout.data_root),'service':service}

    def verify(self) -> dict:
        state=self.state(); current=state.get('current_version')
        checks=[]
        def add(name: str, ok: bool, detail: str=''):
            checks.append({'name':name,'ok':bool(ok),'detail':detail})
        if not current:
            add('active-version',False,'No active version recorded')
            return {'ok':False,'current_version':None,'checks':checks}
        target=self._version_dir(current); env=target/'venv'; py=_venv_python(env); organism=_venv_organism(env)
        add('version-directory',target.is_dir(),str(target))
        add('python',py.is_file(),str(py)); add('organism',organism.is_file(),str(organism))
        install=state.get('installations',{}).get(current)
        add('install-state',isinstance(install,dict),current)
        schema=read_data_schema(self.layout.data_root)
        add('data-schema',schema <= DATA_SCHEMA,f'{schema} <= {DATA_SCHEMA}')
        if py.is_file():
            try:
                proc=subprocess.run([str(py),'-c','import living_assistant; print(living_assistant.__version__)'],text=True,capture_output=True,timeout=30)
                add('package-import',proc.returncode==0 and proc.stdout.strip()==current,(proc.stdout or proc.stderr).strip()[-1000:])
            except Exception as exc: add('package-import',False,str(exc))
        shim=self.layout.bin/('organism.cmd' if os.name=='nt' else 'organism')
        add('stable-shim',shim.is_file(),str(shim))
        if shim.is_file():
            try: add('shim-target',current in shim.read_text(encoding='utf-8',errors='replace'),current)
            except OSError as exc: add('shim-target',False,str(exc))
        return {'ok':all(x['ok'] for x in checks),'current_version':current,'checks':checks}

    def status(self) -> dict:
        state=self.state(); current=state.get('current_version')
        organism=None
        if current:
            candidate=_venv_organism(self._version_dir(current)/'venv')
            organism=str(candidate) if candidate.exists() else None
        return {
            'runtime_root':str(self.layout.runtime_root),'data_root':str(self.layout.data_root),
            'current_version':current,'previous_version':state.get('previous_version'),
            'installed_versions':sorted(state.get('installations',{}).keys()),
            'organism':organism,'bin':str(self.layout.bin),'data_schema':read_data_schema(self.layout.data_root),
        }


def main(argv: list[str] | None = None) -> int:
    import argparse
    p=argparse.ArgumentParser(description='Living Assistant versioned per-user installer/updater')
    p.add_argument('--runtime-root'); p.add_argument('--data-root')
    sub=p.add_subparsers(dest='cmd',required=True)
    i=sub.add_parser('install'); i.add_argument('wheel'); i.add_argument('--extras',default=''); i.add_argument('--no-deps',action='store_true'); i.add_argument('--no-backup',action='store_true'); i.add_argument('--sha256')
    sub.add_parser('status')
    sub.add_parser('verify')
    b=sub.add_parser('backup'); b.add_argument('--label')
    r=sub.add_parser('rollback'); r.add_argument('--version'); r.add_argument('--restore-backup')
    rv=sub.add_parser('remove-version'); rv.add_argument('version')
    u=sub.add_parser('uninstall'); u.add_argument('--purge-data',action='store_true'); u.add_argument('--yes-really-purge-data',action='store_true')
    args=p.parse_args(argv); mgr=ReleaseManager(args.runtime_root,args.data_root)
    try:
        if args.cmd=='install': out=mgr.install_wheel(args.wheel,extras=[x for x in args.extras.split(',') if x],with_dependencies=not args.no_deps,make_backup=not args.no_backup,expected_sha256=args.sha256)
        elif args.cmd=='status': out=mgr.status()
        elif args.cmd=='verify': out=mgr.verify()
        elif args.cmd=='backup': out=mgr.create_backup(args.label)
        elif args.cmd=='rollback': out=mgr.rollback(args.version,restore_backup=args.restore_backup)
        elif args.cmd=='remove-version': out=mgr.remove_version(args.version)
        elif args.cmd=='uninstall': out=mgr.uninstall_runtime(purge_data=args.purge_data,confirm_purge=args.yes_really_purge_data)
        else: return 2
        print(json.dumps(out,indent=2)); return 0
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc)},indent=2),file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
