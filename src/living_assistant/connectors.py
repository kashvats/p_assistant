from __future__ import annotations
from pathlib import Path
import json, time
from .config import data_dir

KINDS={'mail','calendar','files','contacts','custom'}

class ConnectorRegistry:
    """Stores connector metadata only. Credentials must remain in env/OS secret storage."""
    def __init__(self,path: Path | None=None):
        self.path=path or (data_dir()/'connectors.json')
        if not self.path.exists(): self.path.write_text('{}',encoding='utf-8')

    def _load(self):
        try: return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception: return {}
    def _save(self,data): self.path.write_text(json.dumps(data,indent=2),encoding='utf-8')

    def add(self,name: str,kind: str,provider: str,capabilities: list[str],env_prefix: str | None=None,enabled: bool=True) -> dict:
        if kind not in KINDS: raise ValueError(f'kind must be one of {sorted(KINDS)}')
        data=self._load(); data[name]={
            'kind':kind,'provider':provider,'capabilities':sorted(set(capabilities)),
            'env_prefix':env_prefix,'enabled':bool(enabled),'updated_at':time.time(),
        }; self._save(data); return {'name':name,**data[name]}
    def list(self): return self._load()
    def remove(self,name: str) -> bool:
        data=self._load(); ok=name in data; data.pop(name,None); self._save(data); return ok
    def set_enabled(self,name: str,enabled: bool) -> bool:
        data=self._load()
        if name not in data: return False
        data[name]['enabled']=bool(enabled); data[name]['updated_at']=time.time(); self._save(data); return True
