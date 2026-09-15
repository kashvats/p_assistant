from living_assistant.workspace import Workspace
from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.tools.desktop import build_desktop_tools


def test_clipboard_read_noninteractive_queues_approval(tmp_path):
    wsroot = tmp_path/'ws'; wsroot.mkdir()
    ws = Workspace([wsroot])
    store = ApprovalStore(tmp_path/'a.sqlite3')
    approval = ApprovalManager(interactive=False, store=store)
    tool = next(t for t in build_desktop_tools(ws, approval) if t.name == 'clipboard_read')
    result = tool.handler()
    assert result['approval_required']
    assert len(store.list('pending')) == 1
