from __future__ import annotations
from pathlib import Path
import json, time
from .config import data_dir
from .storage_utils import atomic_write_json
from .security_policy import classify_command

class ProjectGroupRegistry:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / 'project_groups.json')
        if not self.path.exists(): atomic_write_json(self.path, {})

    def _load(self):
        try: return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception: return {}

    def _save(self, data): atomic_write_json(self.path, data)

    def add(self, name: str, projects: list[str], stop_reverse: bool = True) -> dict:
        clean = [x.strip() for x in projects if x.strip()]
        if not clean: raise ValueError('At least one project is required.')
        data = self._load()
        data[name] = {'projects': clean, 'stop_reverse': bool(stop_reverse), 'updated_at': time.time()}
        self._save(data)
        return {'name': name, **data[name]}

    def list(self) -> dict: return self._load()
    def get(self, name: str) -> dict | None:
        item = self._load().get(name)
        return {'name': name, **item} if item else None
    def remove(self, name: str) -> bool:
        data = self._load(); ok = name in data; data.pop(name, None); self._save(data); return ok

class ProjectGroupController:
    def __init__(self, groups, projects, processes, approvals):
        self.groups = groups; self.projects = projects; self.processes = processes; self.approvals = approvals

    def plan(self, group_name: str) -> dict:
        group = self.groups.get(group_name)
        if not group: return {'ok': False, 'error': 'Unknown group.'}
        plan = []
        for name in group['projects']:
            p = self.projects.get(name)
            if not p: return {'ok': False, 'error': f'Unknown project in group: {name}'}
            cmd = p.get('start_command')
            if not cmd: return {'ok': False, 'error': f'Project has no start command: {name}'}
            d = classify_command(cmd, True)
            if not d.allowed: return {'ok': False, 'error': f'Blocked project command for {name}: {d.reason}'}
            plan.append({'project': name, 'command': cmd, 'path': p['path']})
        return {'ok': True, 'group': group_name, 'plan': plan}

    def start(self, group_name: str) -> dict:
        planned = self.plan(group_name)
        if not planned.get('ok'): return planned
        action = 'Start project group %s: %s' % (group_name, '; '.join(x['project'] + '=' + x['command'] for x in planned['plan']))
        req = self.approvals.request(action, 'Starting multiple registered project services.', 'EXECUTE')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        results = []
        for entry in planned['plan']:
            p = self.projects.get(entry['project'])
            results.append(self.processes.start(
                p['start_command'], p['path'], name=p['name'], project=p['name'],
                auto_restart=bool(p.get('auto_restart')), max_restarts=int(p.get('max_restarts',3)), health_url=p.get('health_url')
            ))
        return {'ok': all(x.get('ok') for x in results), 'group': group_name, 'results': results}

    def stop(self, group_name: str) -> dict:
        group = self.groups.get(group_name)
        if not group: return {'ok': False, 'error': 'Unknown group.'}
        project_order = list(group['projects'])
        if group.get('stop_reverse', True): project_order.reverse()
        active = self.processes.list()
        results = []
        for project in project_order:
            for item in active:
                if item.get('project') == project and item.get('running'):
                    results.append({'project': project, 'process_id': item['id'], **self.processes.stop(item['id'])})
        return {'ok': all(x.get('ok') for x in results) if results else True, 'group': group_name, 'results': results}
