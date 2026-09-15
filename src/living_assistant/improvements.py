from __future__ import annotations
from pathlib import Path
import sqlite3, hashlib, difflib, json, datetime as dt, uuid
from .config import data_dir
from .workspace import Workspace
from .approval import ApprovalManager

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

PROTECTED_CORE_NAMES = {'security_policy.py','security_guardian.py','approval.py','improvements.py','evaluation.py','sandbox.py','canary.py','workspace.py','quarantine.py','assistant.yaml'}
MAX_PROPOSAL_CHARS = 2_000_000

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class ImprovementStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / 'assistant.sqlite3')
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
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
    def __init__(self, workspace: Workspace, approval: ApprovalManager, store: ImprovementStore):
        self.workspace = workspace
        self.approval = approval
        self.store = store

    def propose(self, target_path: str, new_content: str, title: str, rationale: str, tests: list[str] | None = None) -> dict:
        if len(new_content) > MAX_PROPOSAL_CHARS:
            raise ValueError(f'Improvement proposal exceeds {MAX_PROPOSAL_CHARS} character limit.')
        target = self.workspace.resolve(target_path)
        old = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        diff = ''.join(difflib.unified_diff(old.splitlines(True), new_content.splitlines(True), fromfile=str(target), tofile=str(target)))
        return self.store.create(
            title=title, rationale=rationale, target_path=str(target), base_sha256=_sha(old.encode()),
            proposed_content=new_content, diff=diff, tests=tests or [],
        )

    def apply(self, proposal_id: str) -> dict:
        item = self.store.get(proposal_id)
        if not item:
            return {'ok': False, 'error': 'Unknown proposal id'}
        if item['status'] != 'pending':
            return {'ok': False, 'error': f"Proposal is {item['status']}"}
        target = self.workspace.resolve(item['target_path'])
        if target.name in PROTECTED_CORE_NAMES:
            return {'ok': False, 'manual_required': True, 'error': 'Security-critical assistant core files cannot be auto-applied. Review and edit manually.'}
        current = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        if _sha(current.encode()) != item['base_sha256']:
            return {'ok': False, 'conflict': True, 'error': 'Target changed since proposal creation; regenerate the proposal.'}
        req = self.approval.request(f'Apply improvement {proposal_id} to {target}', item['rationale'], 'SELF_MODIFICATION')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        backup_root = self.workspace.roots[0] / '.living-assistant-backups' / proposal_id
        backup_root.mkdir(parents=True, exist_ok=True)
        if target.exists():
            (backup_root / target.name).write_text(current, encoding='utf-8')
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + '.living-assistant-tmp')
        temp.write_text(item['proposed_content'], encoding='utf-8')
        temp.replace(target)
        self.store.set_status(proposal_id, 'applied')
        return {'ok': True, 'path': str(target), 'backup_dir': str(backup_root), 'tests': item.get('tests', [])}


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
        req = self.approval.request(f'Rollback improvement {proposal_id} on {target}', 'Restore the pre-improvement backup.', 'SELF_MODIFICATION')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        current = target.read_text(encoding='utf-8', errors='replace') if target.exists() else ''
        (backup_root / ('post-apply-' + target.name)).write_text(current, encoding='utf-8')
        target.write_text(backup.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')
        self.store.set_status(proposal_id, 'rolled_back')
        return {'ok': True, 'path': str(target), 'status': 'rolled_back'}

    def reject(self, proposal_id: str) -> dict:
        if not self.store.get(proposal_id):
            return {'ok': False, 'error': 'Unknown proposal id'}
        self.store.set_status(proposal_id, 'rejected')
        return {'ok': True, 'id': proposal_id}
