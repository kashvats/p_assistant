from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import datetime as dt
import hashlib, json, time, uuid
from .config import data_dir

DANGEROUS_EXTENSIONS = {
    '.exe','.msi','.msp','.bat','.cmd','.com','.scr','.ps1','.vbs','.js','.jse','.wsf',
    '.sh','.command','.app','.dmg','.pkg','.deb','.rpm','.apk','.jar','.dll','.so','.dylib'
}
EXECUTABLE_CONTENT_TYPES = {
    'application/x-msdownload','application/x-msdos-program','application/x-executable',
    'application/x-mach-binary','application/vnd.microsoft.portable-executable',
    'application/x-sh','application/java-archive','application/x-apple-diskimage'
}


def _sanitize_source_url(url: str) -> str:
    p=urlparse(url)
    host=p.hostname or ''
    if p.port:
        try: host=f'{host}:{p.port}'
        except ValueError: pass
    # Drop userinfo, query and fragment because signed URLs often contain credentials.
    return urlunparse((p.scheme,host,p.path,'','',''))


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def download_risk_reasons(filename: str,content_type: str|None=None) -> list[str]:
    ext=Path(filename).suffix.lower(); ctype=(content_type or '').split(';')[0].strip().lower(); reasons=[]
    if ext in DANGEROUS_EXTENSIONS: reasons.append(f'executable_or_script_extension:{ext}')
    if ctype in EXECUTABLE_CONTENT_TYPES: reasons.append(f'executable_content_type:{ctype}')
    return reasons


def is_risky_download(filename: str, content_type: str | None = None) -> bool:
    return bool(download_risk_reasons(filename,content_type))


@dataclass
class QuarantineVault:
    root: Path | None=None

    def __post_init__(self):
        self.root=self.root or (data_dir()/'quarantine'); self.root.mkdir(parents=True,exist_ok=True)
        self.index_path=self.root/'index.json'
        if not self.index_path.exists(): self.index_path.write_text('{}',encoding='utf-8')

    def _load(self) -> dict:
        try: return json.loads(self.index_path.read_text(encoding='utf-8'))
        except Exception: return {}

    def _save(self,data: dict): self.index_path.write_text(json.dumps(data,indent=2),encoding='utf-8')

    def reserve(self,source_url: str,suggested_name: str|None=None) -> tuple[str,Path]:
        item_id=uuid.uuid4().hex[:12]; parsed=urlparse(source_url)
        name=suggested_name or Path(parsed.path).name or f'download-{item_id}'
        name=Path(name).name.replace('\x00','') or f'download-{item_id}'
        return item_id,self.root/f'{item_id}-{name}'

    def register(self,item_id: str,path: Path,source_url: str,content_type: str|None=None,
                 original_name: str|None=None,risk_reasons: list[str]|None=None) -> dict:
        data=self._load(); source_url=_sanitize_source_url(source_url); parsed=urlparse(source_url); original_name=Path(original_name or path.name).name
        created_iso=dt.datetime.now().astimezone().isoformat(timespec='seconds')
        item={
            'id':item_id,'path':str(path),'stored_filename':path.name,'original_filename':original_name,
            'source_url':source_url,'source_scheme':parsed.scheme,'source_host':parsed.hostname,
            'content_type':content_type,'bytes':path.stat().st_size,'sha256':sha256_file(path),
            'risk_reasons':risk_reasons if risk_reasons is not None else download_risk_reasons(original_name,content_type),
            'created_at':time.time(),'created_at_iso':created_iso,'status':'quarantined',
            'scan_history':[],'release_history':[],
        }
        data[item_id]=item; self._save(data); return item

    def list(self) -> list[dict]:
        return sorted(self._load().values(),key=lambda x:x.get('created_at',0),reverse=True)

    def get(self,item_id: str) -> dict|None: return self._load().get(item_id)

    def verify(self,item_id: str) -> dict:
        item=self.get(item_id)
        if not item: return {'ok':False,'error':'Unknown quarantine item.'}
        p=Path(item['path'])
        if not p.exists(): return {'ok':False,'error':'Quarantine file is missing.'}
        current=sha256_file(p); expected=item.get('sha256')
        return {'ok':current==expected,'sha256':current,'expected_sha256':expected,'changed':current!=expected}

    def record_scan(self,item_id: str,provider: str,result: dict):
        data=self._load()
        if item_id not in data: return False
        p=Path(data[item_id]['path']); current_sha=sha256_file(p) if p.exists() else None
        data[item_id].setdefault('scan_history',[]).append({
            'provider':provider,'at':dt.datetime.now().astimezone().isoformat(timespec='seconds'),
            'sha256_at_scan':current_sha,'matches_original':current_sha==data[item_id].get('sha256'),
            'result':result,
        })
        data[item_id]['last_scan']=data[item_id]['scan_history'][-1]
        self._save(data); return True

    def mark_released(self,item_id: str,destination: str):
        data=self._load()
        if item_id in data:
            at=dt.datetime.now().astimezone().isoformat(timespec='seconds')
            data[item_id]['status']='released'; data[item_id]['released_to']=destination; data[item_id]['released_at']=time.time(); data[item_id]['released_at_iso']=at
            data[item_id].setdefault('release_history',[]).append({'destination':destination,'at':at})
            self._save(data)
