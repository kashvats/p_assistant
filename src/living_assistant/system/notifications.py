from __future__ import annotations
from pathlib import Path
import datetime as dt
import hashlib, json, os, platform, shutil, subprocess, threading, uuid
from living_assistant.core.config import data_dir
from living_assistant.core.storage_utils import atomic_write_json
from living_assistant.security.security_utils import redact_secrets


class Notifier:
    def __init__(self, quiet_provider=None, queue_path: Path | None = None, approval_sound_enabled: bool = True):
        self.quiet_provider = quiet_provider
        self.approval_sound_enabled = bool(approval_sound_enabled)
        self.queue_path = queue_path or (data_dir() / 'notification_queue.json')
        self._lock = threading.RLock()
        if not self.queue_path.exists():
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.queue_path, [])

    def _load_queue(self) -> list[dict]:
        with self._lock:
            try:
                value = json.loads(self.queue_path.read_text(encoding='utf-8'))
                return value if isinstance(value, list) else []
            except Exception:
                return []

    def _save_queue(self, items: list[dict]):
        with self._lock:
            atomic_write_json(self.queue_path, items[-200:])

    def is_quiet(self) -> bool:
        try:
            return bool(self.quiet_provider and self.quiet_provider())
        except Exception:
            return False

    def _enqueue(self, title: str, message: str) -> dict:
        with self._lock:
            items = self._load_queue()
            digest = hashlib.sha256(f'{title}\0{message}'.encode()).hexdigest()
            if any(x.get('digest') == digest for x in items):
                return {'ok': True, 'queued': True, 'deduplicated': True}
            item = {'id': uuid.uuid4().hex[:12], 'title': title, 'message': message, 'digest': digest,
                    'created_at': dt.datetime.now().isoformat(timespec='seconds')}
            items.append(item)
            self._save_queue(items)
            return {'ok': True, 'queued': True, 'id': item['id']}

    def _send_now(self, title: str, message: str) -> dict:
        system = platform.system()
        try:
            if system == 'Darwin' and shutil.which('osascript'):
                # Do not interpolate notification text into AppleScript source. Text travels
                # only through environment variables, preventing quote/backslash injection.
                env = os.environ.copy(); env['LA_TITLE'] = title; env['LA_MSG'] = message
                script = 'set t to system attribute "LA_TITLE"\nset m to system attribute "LA_MSG"\ndisplay notification m with title t'
                subprocess.run(['osascript', '-e', script], timeout=5, env=env, check=False)
                return {'ok': True, 'backend': 'osascript'}
            if system == 'Linux' and shutil.which('notify-send'):
                subprocess.run(['notify-send', title, message], timeout=5, check=False)
                return {'ok': True, 'backend': 'notify-send'}
            if system == 'Windows':
                powershell = shutil.which('powershell') or shutil.which('pwsh')
                if powershell:
                    script = (
                        'Add-Type -AssemblyName System.Windows.Forms; '
                        '$n=New-Object System.Windows.Forms.NotifyIcon; '
                        '$n.Icon=[System.Drawing.SystemIcons]::Information; '
                        '$n.BalloonTipTitle=$env:LA_TITLE; $n.BalloonTipText=$env:LA_MSG; '
                        '$n.Visible=$true; $n.ShowBalloonTip(5000); Start-Sleep -Seconds 1; $n.Dispose()'
                    )
                    env = os.environ.copy(); env['LA_TITLE'] = title; env['LA_MSG'] = message
                    subprocess.run([powershell, '-NoProfile', '-Command', script], timeout=8, env=env, check=False)
                    return {'ok': True, 'backend': 'powershell'}
        except Exception as e:
            return {'ok': False, 'error': redact_secrets(e, 800)}
        print(f'[{title}] {message}')
        return {'ok': True, 'backend': 'console'}

    def _play_sound(self, kind: str) -> dict:
        if kind != 'approval' or not self.approval_sound_enabled:
            return {'ok': True, 'suppressed': True}
        if self.is_quiet():
            return {'ok': True, 'suppressed': True, 'quiet': True}
        system = platform.system()
        try:
            if system == 'Windows':
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return {'ok': True, 'backend': 'winsound'}
            if system == 'Darwin':
                sound = Path('/System/Library/Sounds/Glass.aiff')
                player = shutil.which('afplay')
                if player and sound.exists():
                    subprocess.run([player, str(sound)], timeout=3, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {'ok': True, 'backend': 'afplay'}
            if system == 'Linux':
                canberra = shutil.which('canberra-gtk-play')
                if canberra:
                    subprocess.run([canberra, '-i', 'message'], timeout=3, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {'ok': True, 'backend': 'canberra-gtk-play'}
                pulse = shutil.which('paplay')
                sound = Path('/usr/share/sounds/freedesktop/stereo/message.oga')
                if pulse and sound.exists():
                    subprocess.run([pulse, str(sound)], timeout=3, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {'ok': True, 'backend': 'paplay'}
        except Exception as exc:
            return {'ok': False, 'error': redact_secrets(exc, 500)}
        try:
            print('\a', end='', flush=True)
            return {'ok': True, 'backend': 'terminal-bell'}
        except Exception as exc:
            return {'ok': False, 'error': redact_secrets(exc, 500)}

    def send(self, title: str, message: str, urgent: bool = False, sound: str | None = None) -> dict:
        title = redact_secrets(title, 120); message = redact_secrets(message, 800)
        if not urgent and self.is_quiet():
            return self._enqueue(title, message)
        result = self._send_now(title, message)
        if sound:
            result = dict(result)
            result['sound'] = self._play_sound(sound)
        return result

    def queued(self) -> list[dict]:
        return self._load_queue()

    def flush(self, max_items: int = 10) -> dict:
        if self.is_quiet():
            return {'ok': True, 'flushed': 0, 'quiet': True}
        with self._lock:
            items = self._load_queue(); sent = 0; remaining = []
            for item in items:
                if sent >= max(1, min(int(max_items), 50)):
                    remaining.append(item); continue
                result = self._send_now(str(item.get('title', 'Living Assistant')), str(item.get('message', '')))
                if result.get('ok'):
                    sent += 1
                else:
                    remaining.append(item)
            self._save_queue(remaining)
        return {'ok': True, 'flushed': sent, 'remaining': len(remaining)}
