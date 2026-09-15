from __future__ import annotations
from pathlib import Path
import datetime as dt
import hashlib, json, os, platform, shutil, subprocess, uuid
from .config import data_dir

class Notifier:
    def __init__(self, quiet_provider=None, queue_path: Path | None = None):
        self.quiet_provider = quiet_provider
        self.queue_path = queue_path or (data_dir() / 'notification_queue.json')
        if not self.queue_path.exists():
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            self.queue_path.write_text('[]', encoding='utf-8')

    def _load_queue(self) -> list[dict]:
        try: return json.loads(self.queue_path.read_text(encoding='utf-8'))
        except Exception: return []

    def _save_queue(self, items: list[dict]):
        self.queue_path.write_text(json.dumps(items[-200:], indent=2), encoding='utf-8')

    def is_quiet(self) -> bool:
        try: return bool(self.quiet_provider and self.quiet_provider())
        except Exception: return False

    def _enqueue(self, title: str, message: str) -> dict:
        items=self._load_queue()
        digest=hashlib.sha256(f'{title}\0{message}'.encode()).hexdigest()
        if any(x.get('digest')==digest for x in items):
            return {'ok': True, 'queued': True, 'deduplicated': True}
        item={'id':uuid.uuid4().hex[:12],'title':title,'message':message,'digest':digest,'created_at':dt.datetime.now().isoformat(timespec='seconds')}
        items.append(item); self._save_queue(items)
        return {'ok': True, 'queued': True, 'id': item['id']}

    def _send_now(self, title: str, message: str) -> dict:
        system = platform.system()
        try:
            if system == 'Darwin' and shutil.which('osascript'):
                safe_t = title.replace('"', '\\"'); safe_m = message.replace('"', '\\"')
                subprocess.run(['osascript','-e',f'display notification "{safe_m}" with title "{safe_t}"'], timeout=5)
                return {'ok': True, 'backend': 'osascript'}
            if system == 'Linux' and shutil.which('notify-send'):
                subprocess.run(['notify-send',title,message], timeout=5)
                return {'ok': True, 'backend': 'notify-send'}
            if system == 'Windows' and shutil.which('powershell'):
                script=(
                    'Add-Type -AssemblyName System.Windows.Forms; '
                    '$n=New-Object System.Windows.Forms.NotifyIcon; '
                    '$n.Icon=[System.Drawing.SystemIcons]::Information; '
                    '$n.BalloonTipTitle=$env:LA_TITLE; $n.BalloonTipText=$env:LA_MSG; '
                    '$n.Visible=$true; $n.ShowBalloonTip(5000); Start-Sleep -Seconds 1; $n.Dispose()'
                )
                env=os.environ.copy(); env['LA_TITLE']=title; env['LA_MSG']=message
                subprocess.run(['powershell','-NoProfile','-Command',script], timeout=8, env=env)
                return {'ok': True, 'backend': 'powershell'}
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        print(f'[{title}] {message}')
        return {'ok': True, 'backend': 'console'}

    def send(self, title: str, message: str, urgent: bool = False) -> dict:
        title=str(title)[:120]; message=str(message)[:800]
        if not urgent and self.is_quiet():
            return self._enqueue(title,message)
        return self._send_now(title,message)

    def queued(self) -> list[dict]:
        return self._load_queue()

    def flush(self, max_items: int = 10) -> dict:
        if self.is_quiet(): return {'ok': True, 'flushed': 0, 'quiet': True}
        items=self._load_queue(); sent=0; remaining=[]
        for item in items:
            if sent >= max(1,min(int(max_items),50)):
                remaining.append(item); continue
            result=self._send_now(str(item.get('title','Living Assistant')),str(item.get('message','')))
            if result.get('ok'): sent += 1
            else: remaining.append(item)
        self._save_queue(remaining)
        return {'ok': True, 'flushed': sent, 'remaining': len(remaining)}
