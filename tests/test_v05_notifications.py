from living_assistant.notifications import Notifier


def test_quiet_notifications_queue_and_flush(tmp_path):
    quiet={'value':True}
    n=Notifier(lambda: quiet['value'], tmp_path/'queue.json')
    sent=[]
    n._send_now=lambda title,message: sent.append((title,message)) or {'ok':True,'backend':'test'}
    r=n.send('A','hello')
    assert r['queued'] is True and len(n.queued())==1 and sent==[]
    quiet['value']=False
    out=n.flush()
    assert out['flushed']==1 and sent==[('A','hello')] and n.queued()==[]


def test_windows_notification_uses_powershell_toast_backend(tmp_path, monkeypatch):
    import living_assistant.notifications as mod

    captured = {}
    monkeypatch.setattr(mod.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(mod.shutil, 'which', lambda name: 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe' if name == 'powershell' else None)

    def fake_run(args, **kwargs):
        captured['args'] = args
        captured['env'] = kwargs.get('env', {})
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(mod.subprocess, 'run', fake_run)
    notifier = Notifier(queue_path=tmp_path / 'q.json')
    result = notifier.send('Build finished', 'Project A is ready')

    assert result == {'ok': True, 'backend': 'powershell'}
    assert captured['args'][0].lower().endswith('powershell.exe')
    assert captured['env']['LA_TITLE'] == 'Build finished'
    assert captured['env']['LA_MSG'] == 'Project A is ready'
    # Notification text must not be interpolated into executable PowerShell source.
    script = captured['args'][-1]
    assert 'Build finished' not in script and 'Project A is ready' not in script
