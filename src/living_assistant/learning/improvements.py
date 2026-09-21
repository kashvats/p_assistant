from __future__ import annotations
from pathlib import Path
import sqlite3, hashlib, json, datetime as dt, uuid, ast
from typing import TYPE_CHECKING
from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.core.workspace import Workspace
from living_assistant.core.approval import ApprovalManager
from living_assistant.security.security_utils import is_sensitive_path
from living_assistant.learning.patch_engine import ASTSafePatchEngine

if TYPE_CHECKING:
    from living_assistant.system.workspace_snapshots import WorkspaceSnapshotManager

SCHEMA = """
CREATE TABLE IF NOT EXISTS improvement_proposals(
 id TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 rationale TEXT NOT NULL,
 target_path TEXT NOT NULL,
 base_sha256 TEXT NOT NULL,
 proposed_content TEXT NOT NULL,
 diff TEXT NOT NULL,
 tests TEXT NOT NULL DEFAULT '[]',
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 applied_at TEXT
);
"""

PROTECTED_CORE_NAMES = {'security_policy.py','security_guardian.py','approval.py','improvements.py','evaluation.py','sandbox.py','canary.py','workspace.py','quarantine.py','assistant.yaml'}  # legacy compatibility
MAX_PROPOSAL_CHARS = 2_000_000


def _assistant_repo_root_for(path: Path) -> Path | None:
    target = path.resolve()
    for parent in [target.parent, *target.parents]:
        pkg = parent / 'src' / 'living_assistant'
        pyproject = parent / 'pyproject.toml'
        if pkg.exists() and pyproject.exists():
            try:
                text = pyproject.read_text(encoding='utf-8', errors='ignore')[:12000].lower()
            except Exception:
                text = ''
            if 'living-assistant' in text or 'living_assistant' in text:
                return parent
    return None


def is_protected_core_path(path: str | Path) -> bool:
    target = Path(path).resolve()
    root = _assistant_repo_root_for(target)
    if root is None:
        return False
    protected_roots = [
        (root / 'src' / 'living_assistant').resolve(),
        (root / 'config').resolve(),
        (root / 'scripts').resolve(),
        (root / 'tests').resolve(),
        (root / '.github').resolve(),
    ]
    protected_files = {(root / 'pyproject.toml').resolve()}
    if target in protected_files:
        return True
    for base in protected_roots:
        try:
            target.relative_to(base)
            return True
        except ValueError:
            pass
    return False

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class ImprovementStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / 'assistant.sqlite3')
        self.conn = ThreadLocalSQLite(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def create(self, **fields) -> dict:
        proposal_id = uuid.uuid4().hex[:12]
        now = dt.datetime.now().isoformat(timespec='seconds')
        self.conn.execute(
            "INSERT INTO improvement_proposals(id,title,rationale,target_path,base_sha256,proposed_content,diff,tests,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, fields['title'], fields['rationale'], fields['target_path'], fields['base_sha256'],
             fields['proposed_content'], fields['diff'], json.dumps(fields.get('tests', [])), 'pending', now),
        )
        self.conn.commit()
        return self.get(proposal_id)

    def get(self, proposal_id: str) -> dict | None:
        row = self.conn.execute('SELECT * FROM improvement_proposals WHERE id=?', (proposal_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item['tests'] = json.loads(item['tests'])
        except Exception:
            pass
        return item

    def list(self, status: str | None = None, limit: int = 100) -> list[dict]:
        if status:
            rows = self.conn.execute('SELECT * FROM improvement_proposals WHERE status=? ORDER BY created_at DESC LIMIT ?', (status, limit)).fetchall()
        else:
            rows = self.conn.execute('SELECT * FROM improvement_proposals ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item['tests'] = json.loads(item['tests'])
            except Exception:
                pass
            out.append(item)
        return out

    def set_status(self, proposal_id: str, status: str):
        applied_at = dt.datetime.now().isoformat(timespec='seconds') if status == 'applied' else None
        self.conn.execute('UPDATE improvement_proposals SET status=?, applied_at=COALESCE(?,applied_at) WHERE id=?', (status, applied_at, proposal_id))
        self.conn.commit()

class ImprovementEngine:
    def __init__(self, workspace: Workspace, approval: ApprovalManager, store: ImprovementStore, patch_engine: ASTSafePatchEngine | None = None, snapshot_manager: "WorkspaceSnapshotManager | None" = None):
        self.workspace = workspace
        self.approval = approval
        self.store = store
        self.patch_engine = patch_engine or ASTSafePatchEngine()
        self.snapshot_manager = snapshot_manager

    def context(self, target_path: str, max_files: int = 8, max_chars_per_file: int = 4000) -> dict:
        target=self.workspace.resolve(target_path)
        if is_protected_core_path(target) or is_sensitive_path(target):
            return {'ok':False,'blocked':True,'error':'Cross-file self-improvement context is unavailable for protected or sensitive targets.'}
        if not target.exists() or not target.is_file():
            return {'ok':False,'error':'Target file does not exist.'}
        max_files=max(1,min(int(max_files),20)); max_chars_per_file=max(500,min(int(max_chars_per_file),12000))
        target_text=target.read_text(encoding='utf-8',errors='replace')
        imports=[]; symbols=[]
        if target.suffix.lower()=='.py':
            try:
                tree=ast.parse(target_text)
                for node in tree.body:
                    if isinstance(node,ast.Import): imports.extend(alias.name for alias in node.names)
                    elif isinstance(node,ast.ImportFrom) and node.module: imports.append(node.module)
                    elif isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)): symbols.append(node.name)
            except SyntaxError:
                pass
        roots=[root for root in self.workspace.roots if target == root or root in target.parents]
        root=max(roots,key=lambda x:len(x.parts)) if roots else self.workspace.roots[0]
        module_name=target.stem
        needles={module_name,*symbols}
        related=[]
        candidates=0
        for path in root.rglob('*'):
            if len(related)>=max_files or candidates>=1500: break
            if not path.is_file() or path==target or is_sensitive_path(path): continue
            if path.stat().st_size>750_000: continue
            if target.suffix and path.suffix.lower()!=target.suffix.lower(): continue
            candidates+=1
            try: text=path.read_text(encoding='utf-8',errors='ignore')
            except Exception: continue
            score=0; reasons=[]
            if path.parent==target.parent:
                score+=1; reasons.append('same_directory')
            hits=[needle for needle in needles if needle and needle in text]
            if hits:
                score+=3+min(len(hits),3); reasons.append('references_target_symbols')
            import_hits=[name for name in imports if name and (name in text or path.stem==name.rsplit('.',1)[-1])]
            if import_hits:
                score+=2; reasons.append('related_import')
            if score<=0: continue
            related.append({'path':str(path),'score':score,'reasons':reasons,'content':text[:max_chars_per_file]})
        related.sort(key=lambda x:(-x['score'],x['path']))
        return {
            'ok':True,'target':str(target),'target_content':target_text[:max_chars_per_file],
            'imports':sorted(set(imports))[:50],'symbols':symbols[:100],
            'related_files':related[:max_files],
            'bounded':True,
        }

    def propose(self, target_path: str, new_content: str, title: str, rationale: str, tests: list[str] | None = None) -> dict:
        if len(new_content) > MAX_PROPOSAL_CHARS:
            raise ValueError(f'Improvement proposal exceeds {MAX_PROPOSAL_CHARS} character limit.')
        target = self.workspace.resolve(target_path)
        protected_core = is_protected_core_path(target)
        sensitive_target = is_sensitive_path(target)
        if protected_core or sensitive_target:
            return {
                'ok': False,
                'blocked': True,
                'sensitive': True,
                'protected_core': protected_core,
                'error': (
                    'Self-improvement proposals cannot target Living Assistant security/core files.'
                    if protected_core else
                    'Self-improvement proposals cannot target credential or secret-bearing files.'
                ),
            }
        old = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        patch = self.patch_engine.analyze(old, new_content, target)
        if not patch.get('ok'):
            return {'ok': False, 'blocked': True, 'ast_guard': True, **patch}
        created = self.store.create(
            title=title, rationale=rationale, target_path=str(target), base_sha256=_sha(old.encode()),
            proposed_content=new_content, diff=patch['diff'], tests=tests or [],
        )
        created['patch_analysis'] = {k: v for k, v in patch.items() if k != 'diff'}
        return created

    def apply(self, proposal_id: str) -> dict:
        item = self.store.get(proposal_id)
        if not item:
            return {'ok': False, 'error': 'Unknown proposal id'}
        if item['status'] != 'pending':
            return {'ok': False, 'error': f"Proposal is {item['status']}"}
        target = self.workspace.resolve(item['target_path'])
        if is_protected_core_path(target):
            return {'ok': False, 'manual_required': True, 'error': 'Living Assistant core/config/scripts cannot be auto-applied. Proposals may be evaluated, but promotion requires a human-managed edit/release.'}
        current = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        if _sha(current.encode()) != item['base_sha256']:
            return {'ok': False, 'conflict': True, 'error': 'Target changed since proposal creation; regenerate the proposal.'}
        patch = self.patch_engine.analyze(current, item['proposed_content'], target)
        if not patch.get('ok'):
            return {'ok': False, 'blocked': True, 'ast_guard': True, **patch}
        req = self.approval.request(f'Apply improvement {proposal_id} to {target}', item['rationale'], 'SELF_MODIFICATION')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        backup_root = self.workspace.roots[0] / '.living-assistant-backups' / proposal_id
        backup_root.mkdir(parents=True, exist_ok=True)
        snapshot_id = None
        if self.snapshot_manager is not None:
            try:
                snapshot_id = self.snapshot_manager.create_for_path(target, f'Apply improvement {proposal_id}')['snapshot_id']
            except Exception as exc:
                return {'ok': False, 'blocked': True, 'error': f'Pre-change workspace snapshot failed: {exc}'}
        if target.exists():
            (backup_root / target.name).write_text(current, encoding='utf-8')
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + '.living-assistant-tmp')
        temp.write_text(item['proposed_content'], encoding='utf-8')
        temp.replace(target)
        self.store.set_status(proposal_id, 'applied')
        return {'ok': True, 'path': str(target), 'backup_dir': str(backup_root), 'tests': item.get('tests', []), 'snapshot_id': snapshot_id}


    def rollback(self, proposal_id: str) -> dict:
        item = self.store.get(proposal_id)
        if not item:
            return {'ok': False, 'error': 'Unknown proposal id'}
        if item['status'] != 'applied':
            return {'ok': False, 'error': f"Proposal is {item['status']}; only applied proposals can be rolled back."}
        target = self.workspace.resolve(item['target_path'])
        backup_root = self.workspace.roots[0] / '.living-assistant-backups' / proposal_id
        backup = backup_root / target.name
        if not backup.exists():
            return {'ok': False, 'error': 'Rollback backup is missing.'}
        expected_applied_sha=_sha(item['proposed_content'].encode())
        current = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        if _sha(current.encode()) != expected_applied_sha:
            return {'ok': False, 'conflict': True, 'error': 'Target changed after the improvement was applied; refusing to overwrite subsequent edits.'}
        req = self.approval.request(f'Rollback improvement {proposal_id} on {target}', 'Restore the pre-improvement backup.', 'SELF_MODIFICATION')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        # Re-check after approval because the file may have changed while a human
        # reviewed the request. Never let rollback overwrite a concurrent edit.
        current = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        if _sha(current.encode()) != expected_applied_sha:
            return {'ok': False, 'conflict': True, 'error': 'Target changed during rollback approval; refusing to overwrite subsequent edits.'}
        (backup_root / ('post-apply-' + target.name)).write_text(current, encoding='utf-8')
        target.write_text(backup.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')
        self.store.set_status(proposal_id, 'rolled_back')
        return {'ok': True, 'path': str(target), 'status': 'rolled_back'}

    def reject(self, proposal_id: str) -> dict:
        if not self.store.get(proposal_id):
            return {'ok': False, 'error': 'Unknown proposal id'}
        self.store.set_status(proposal_id, 'rejected')
        return {'ok': True, 'id': proposal_id}
