from living_assistant.workspace import Workspace
from living_assistant.tools.filesystem import build_filesystem_tools


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_preview_write_diff(tmp_path):
    root = tmp_path/'ws'; root.mkdir()
    (root/'a.txt').write_text('old\n', encoding='utf-8')
    ws = Workspace([root])
    tool = get_tool(build_filesystem_tools(ws), 'preview_write_file')
    result = tool.handler(path='a.txt', content='new\n')
    assert '-old' in result['diff']
    assert '+new' in result['diff']
    assert (root/'a.txt').read_text() == 'old\n'


def test_write_returns_diff(tmp_path):
    root = tmp_path/'ws'; root.mkdir()
    ws = Workspace([root])
    tool = get_tool(build_filesystem_tools(ws), 'write_file')
    result = tool.handler(path='b.txt', content='hello\n')
    assert result['ok']
    assert '+hello' in result['diff']
