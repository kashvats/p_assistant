from living_assistant.approval import ApprovalStore, ApprovalManager

class Notifier:
    def __init__(self): self.messages=[]
    def send(self,title,message): self.messages.append((title,message))


def test_noninteractive_approval_notifies(tmp_path):
    store=ApprovalStore(tmp_path/'a.sqlite3'); n=Notifier()
    mgr=ApprovalManager(interactive=False,store=store,notifier=n)
    result=mgr.request('run thing','because','EXECUTE')
    assert result['pending'] is True
    assert n.messages and 'EXECUTE' in n.messages[0][1]
