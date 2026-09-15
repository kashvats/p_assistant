from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import hashlib, json, mimetypes, time, uuid
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def is_risky_download(filename: str, content_type: str | None = None) -> bool:
    ext = Path(filename).suffix.lower()
    ctype = (content_type or '').split(';')[0].strip().lower()
    return ext in DANGEROUS_EXTENSIONS or ctype in EXECUTABLE_CONTENT_TYPES

@dataclass
class QuarantineVault:
    root: Path | None = None

    def __post_init__(self):
        self.root = self.root or (data_dir() / 'quarantine')
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / 'index.json'
        if not self.index_path.exists():
            self.index_path.write_text('{}', encoding='utf-8')

    def _load(self) -> dict:
        try:
            return json.loads(self.index_path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _save(self, data: dict):
        self.index_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def reserve(self, source_url: str, suggested_name: str | None = None) -> tuple[str, Path]:
        item_id = uuid.uuid4().hex[:12]
        parsed = urlparse(source_url)
        name = suggested_name or Path(parsed.path).name or f'download-{item_id}'
        # Never trust path components from remote input.
        name = Path(name).name.replace('\x00', '') or f'download-{item_id}'
        return item_id, self.root / f'{item_id}-{name}'

    def register(self, item_id: str, path: Path, source_url: str, content_type: str | None = None) -> dict:
        data = self._load()
        item = {
            'id': item_id,
            'path': str(path),
            'filename': path.name,
            'source_url': source_url,
            'content_type': content_type,
            'bytes': path.stat().st_size,
            'sha256': sha256_file(path),
            'created_at': time.time(),
            'status': 'quarantined',
        }
        data[item_id] = item
        self._save(data)
        return item

    def list(self) -> list[dict]:
        return sorted(self._load().values(), key=lambda x: x.get('created_at', 0), reverse=True)

    def get(self, item_id: str) -> dict | None:
        return self._load().get(item_id)

    def mark_released(self, item_id: str, destination: str):
        data = self._load()
        if item_id in data:
            data[item_id]['status'] = 'released'
            data[item_id]['released_to'] = destination
            data[item_id]['released_at'] = time.time()
            self._save(data)
