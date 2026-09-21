from __future__ import annotations
from pathlib import Path
import json, time
from concurrent.futures import ThreadPoolExecutor
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

    def add(self, name: str, projects: list[str], stop_reverse: bool = True,
            dependencies: dict[str, list[str]] | None = None, parallel_start: bool = False,
            max_parallel: int = 4) -> dict:
        clean = list(dict.fromkeys(x.strip() for x in projects if x.strip()))
        if not clean: raise ValueError('At least one project is required.')
        allowed=set(clean); deps={}
        for project, required in (dependencies or {}).items():
            project=str(project).strip()
            if project not in allowed: raise ValueError(f'Unknown dependency target: {project}')
            values=list(dict.fromkeys(str(x).strip() for x in (required or []) if str(x).strip()))
            unknown=[x for x in values if x not in allowed]
            if unknown: raise ValueError(f'Unknown dependencies for {project}: {", ".join(unknown)}')
            if project in values: raise ValueError(f'Project cannot depend on itself: {project}')
            if values: deps[project]=values
        data = self._load()
        data[name] = {
            'projects': clean, 'stop_reverse': bool(stop_reverse), 'dependencies': deps,
            'parallel_start': bool(parallel_start), 'max_parallel': max(1,min(int(max_parallel),16)),
            'updated_at': time.time(),
        }
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
        entries = {}
        order=list(group['projects'])
        for name in order:
            p = self.projects.get(name)
            if not p: return {'ok': False, 'error': f'Unknown project in group: {name}'}
            cmd = p.get('start_command')
            if not cmd: return {'ok': False, 'error': f'Project has no start command: {name}'}
            d = classify_command(cmd, True)
            if not d.allowed: return {'ok': False, 'error': f'Blocked project command for {name}: {d.reason}'}
            entries[name]={'project': name, 'command': cmd, 'path': p['path']}

        dependencies={name:list((group.get('dependencies') or {}).get(name,[])) for name in order}
        remaining=set(order); completed=set(); stages=[]
        while remaining:
            ready=[name for name in order if name in remaining and set(dependencies[name]).issubset(completed)]
            if not ready:
                blocked={name:dependencies[name] for name in order if name in remaining}
                return {'ok': False, 'error': 'Project-group dependency cycle detected.', 'blocked': blocked}
            stage=[entries[name] for name in ready]
            stages.append(stage); completed.update(ready); remaining.difference_update(ready)
        plan=[entry for stage in stages for entry in stage]
        return {
            'ok': True, 'group': group_name, 'plan': plan, 'stages': stages,
            'parallel_start': bool(group.get('parallel_start',False)),
            'max_parallel': max(1,min(int(group.get('max_parallel',4) or 4),16)),
        }

    def start(self, group_name: str) -> dict:
        planned = self.plan(group_name)
        if not planned.get('ok'): return planned
        action = 'Start project group %s: %s' % (group_name, '; '.join(x['project'] + '=' + x['command'] for x in planned['plan']))
        req = self.approvals.request(action, 'Starting multiple registered project services.', 'EXECUTE')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        results = []
        def launch(entry):
            p = self.projects.get(entry['project'])
            result=self.processes.start(
                p['start_command'], p['path'], name=p['name'], project=p['name'],
                auto_restart=bool(p.get('auto_restart')), max_restarts=int(p.get('max_restarts',3)), health_url=p.get('health_url'), env=p.get('env')
            )
            return {'project':entry['project'],**result}

        for stage_index, stage in enumerate(planned['stages']):
            if planned.get('parallel_start') and len(stage)>1:
                workers=min(planned.get('max_parallel',4),len(stage))
                with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='project-group') as pool:
                    stage_results=list(pool.map(launch,stage))
            else:
                stage_results=[launch(entry) for entry in stage]
            results.extend(stage_results)
            if not all(x.get('ok') for x in stage_results):
                remaining=[e['project'] for later in planned['stages'][stage_index+1:] for e in later]
                for project in remaining:
                    results.append({'ok':False,'project':project,'skipped':True,'error':'Dependency stage failed; project was not started.'})
                break
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
