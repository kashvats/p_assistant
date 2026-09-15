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
