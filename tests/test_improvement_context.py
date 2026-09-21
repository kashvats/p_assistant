from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.improvements import ImprovementEngine, ImprovementStore
from living_assistant.tools.improvementtools import build_improvement_tools
from living_assistant.workspace import Workspace


def engine(tmp_path):
    root=tmp_path/'project'; root.mkdir()
    ws=Workspace([root])
    approvals=ApprovalManager(interactive=False,store=ApprovalStore(tmp_path/'approvals.sqlite3'))
    return root, ImprovementEngine(ws,approvals,ImprovementStore(tmp_path/'improvements.sqlite3'))


def test_improvement_context_finds_imports_and_callers(tmp_path):
    root,e=engine(tmp_path)
    (root/'helper.py').write_text('def normalize(value):\n    return value.strip()\n')
    (root/'service.py').write_text('from helper import normalize\n\ndef process(value):\n    return normalize(value)\n')
    (root/'api.py').write_text('from service import process\n\ndef endpoint(v):\n    return process(v)\n')
    result=e.context('service.py')
    assert result['ok'] is True
    paths={item['path'].split('/')[-1] for item in result['related_files']}
    assert 'helper.py' in paths
    assert 'api.py' in paths
    assert 'helper' in result['imports'] and 'process' in result['symbols']


def test_improvement_context_is_exposed_as_tool(tmp_path):
    root,e=engine(tmp_path); (root/'a.py').write_text('x=1\n')
    tools={t.name:t for t in build_improvement_tools(e)}
    assert 'improvement_context' in tools
    assert tools['improvement_context'].handler('a.py')['ok'] is True
