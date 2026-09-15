from __future__ import annotations
from pathlib import Path
import datetime as dt
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .config import data_dir
from .storage_utils import atomic_write_json


def _parse_hhmm(value: str) -> dt.time:
    try:
        h, m = [int(x) for x in value.strip().split(':', 1)]
        return dt.time(hour=h, minute=m)
    except Exception as exc:
        raise ValueError('Time must use HH:MM in 24-hour format.') from exc


class PersonalState:
    """Small persistent store for focus/quiet-hour/personal operating preferences."""
    def __init__(self, path: Path | None = None, timezone: str = 'local', defaults: dict | None = None):
        self.path = path or (data_dir() / 'personal_state.json')
        self.timezone_name = timezone or 'local'
        defaults = defaults or {}
        quiet = defaults.get('quiet_hours', {})
        if not self.path.exists():
            self._save({
                'quiet_hours': {'enabled': bool(quiet.get('enabled', False)), 'start': str(quiet.get('start', '22:00')), 'end': str(quiet.get('end', '07:00'))},
                'focus': {'enabled': False, 'until': None, 'label': None},
                'briefings': {'last_morning': None, 'last_evening': None},
            })

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            data = {}
        data.setdefault('quiet_hours', {'enabled': False, 'start': '22:00', 'end': '07:00'})
        data.setdefault('focus', {'enabled': False, 'until': None, 'label': None})
        data.setdefault('briefings', {'last_morning': None, 'last_evening': None})
        return data

    def _save(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path, data)

    def tzinfo(self):
        if self.timezone_name in {'', 'local', None}:
            return dt.datetime.now().astimezone().tzinfo
        try:
            return ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError:
            return dt.datetime.now().astimezone().tzinfo

    def now(self) -> dt.datetime:
        return dt.datetime.now(self.tzinfo())

    def status(self, now: dt.datetime | None = None) -> dict:
        data = self._load()
        current = now or self.now()
        focus = data['focus']
        if focus.get('enabled') and focus.get('until'):
            try:
                until = dt.datetime.fromisoformat(focus['until'])
                if until.tzinfo is None and current.tzinfo is not None:
                    until = until.replace(tzinfo=current.tzinfo)
                elif until.tzinfo is not None and current.tzinfo is None:
                    until = until.replace(tzinfo=None)
                if current >= until:
                    focus = {'enabled': False, 'until': None, 'label': None}
                    data['focus'] = focus
                    self._save(data)
            except Exception:
                pass
        return {
            'timezone': self.timezone_name,
            'quiet_hours': data['quiet_hours'],
            'focus': focus,
            'quiet_now': self.is_quiet(current, _data=data),
        }

    def set_quiet_hours(self, start: str, end: str, enabled: bool = True) -> dict:
        _parse_hhmm(start); _parse_hhmm(end)
        data = self._load()
        data['quiet_hours'] = {'enabled': bool(enabled), 'start': start, 'end': end}
        self._save(data)
        return data['quiet_hours']

    def set_quiet_enabled(self, enabled: bool) -> dict:
        data = self._load(); data['quiet_hours']['enabled'] = bool(enabled); self._save(data)
        return data['quiet_hours']

    def start_focus(self, minutes: int | None = None, label: str | None = None, now: dt.datetime | None = None) -> dict:
        current = now or self.now()
        until = None
        if minutes is not None:
            minutes = max(1, min(int(minutes), 24 * 60))
            until = (current + dt.timedelta(minutes=minutes)).isoformat(timespec='seconds')
        data = self._load()
        data['focus'] = {'enabled': True, 'until': until, 'label': label}
        self._save(data)
        return data['focus']

    def stop_focus(self) -> dict:
        data = self._load(); data['focus'] = {'enabled': False, 'until': None, 'label': None}; self._save(data)
        return data['focus']

    def is_quiet(self, now: dt.datetime | None = None, _data: dict | None = None) -> bool:
        data = _data or self._load()
        current = now or self.now()
        focus = data.get('focus', {})
        if focus.get('enabled'):
            if focus.get('until'):
                try:
                    until = dt.datetime.fromisoformat(focus['until'])
                    if until.tzinfo is None and current.tzinfo is not None:
                        until = until.replace(tzinfo=current.tzinfo)
                    elif until.tzinfo is not None and current.tzinfo is None:
                        until = until.replace(tzinfo=None)
                    if current < until:
                        return True
                except Exception:
                    return True
            else:
                return True
        q = data.get('quiet_hours', {})
        if not q.get('enabled'):
            return False
        start = _parse_hhmm(str(q.get('start', '22:00')))
        end = _parse_hhmm(str(q.get('end', '07:00')))
        t = current.timetz().replace(tzinfo=None)
        if start == end:
            return True
        if start < end:
            return start <= t < end
        return t >= start or t < end

    def briefing_last(self, kind: str) -> str | None:
        return self._load().get('briefings', {}).get(f'last_{kind}')

    def mark_briefing(self, kind: str, date_value: dt.date | str):
        if kind not in {'morning', 'evening'}:
            raise ValueError('Briefing kind must be morning or evening.')
        data = self._load(); data['briefings'][f'last_{kind}'] = str(date_value); self._save(data)
