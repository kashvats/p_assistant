import living_assistant.security_sensors as ss
from living_assistant.daemon import NervousSystem
from living_assistant.memory import MemoryStore
from living_assistant.security_sensors import SecuritySensorPlatform


class Guardian:
    def __init__(self): self.rows=[]
    def record_finding(self, kind, severity, title, details):
        self.rows.append((kind, severity, title, details))
        return {'id': str(len(self.rows)), '_new': True}
    def findings(self, status='open', limit=200): return []


class Processes:
    def list(self): return []


class Watches:
    def poll(self, **kwargs): return []
    def rebaseline(self): return {'refreshed': 0, 'missing': []}


class Note:
    def flush(self, **kwargs): return {'ok': True}
    def send(self, *args, **kwargs): return {'ok': True}
    def is_quiet(self): return False


def _windows_events():
    return [
        {'kind':'process_create','pid':77,'image':'C:/Windows/System32/powershell.exe','parent_image':'C:/Office/WINWORD.EXE','command_line':'powershell -enc abc','time':'2026-01-01T00:00:00Z'},
        {'kind':'dns_query','pid':77,'query_name':'example.test','time':'2026-01-01T00:00:01Z'},
        {'kind':'network_connect','pid':77,'destination_ip':'203.0.113.10','time':'2026-01-01T00:00:02Z'},
    ]


def test_periodic_scan_uses_windows_eventlog_collector(tmp_path, monkeypatch):
    monkeypatch.setattr(ss.platform, 'system', lambda: 'Windows')
    calls=[]
    monkeypatch.setattr(ss, 'collect_windows_eventlog', lambda minutes, max_events, include_security: calls.append((minutes,max_events,include_security)) or {'ok':True,'available':True,'events':_windows_events(),'errors':[]})
    sensor=SecuritySensorPlatform({'security_sensors':{'enabled':True}}, guardian=Guardian(), db_path=tmp_path/'sensor.sqlite3')
    emitted=sensor.periodic_scan()
    assert calls and calls[0][2] is True
    assert any(e['kind']=='security_correlated_chain' for e in emitted)


def test_daemon_invokes_security_sensor_periodic_scan(tmp_path):
    class Sensor:
        def __init__(self): self.calls=0
        def periodic_scan(self): self.calls += 1; return [{'kind':'security_correlated_chain','severity':'high','signals':['windows_eventlog']}]

    sensor=Sensor()
    ns=NervousSystem(
        {
            'daemon':{'alert_on_new_listening_port':False,'watch_files':False},
            'routines':{'enabled':False},
            'security_guardian':{'enabled':False},
            'security_sensors':{'enabled':True,'scan_interval_seconds':60},
        },
        MemoryStore(tmp_path/'memory.sqlite3'), Processes(), Watches(), Note(), security_sensors=sensor,
    )
    ns.power_monitor.observe=lambda:{'resumed':False}
    events=ns.tick()
    assert sensor.calls == 1
    assert any(e['kind']=='security_correlated_chain' for e in events)
