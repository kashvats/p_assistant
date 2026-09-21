from living_assistant.tools.filesystem import build_filesystem_tools
from living_assistant.workspace import Workspace


def handlers(root):
    return {t.name:t.handler for t in build_filesystem_tools(Workspace([root]))}


def test_search_files_supports_regex_and_extension_filter(tmp_path):
    root=tmp_path/'ws'; root.mkdir()
    (root/'alpha.py').write_text('def camera_feed_42():\n    pass\n')
    (root/'alpha.txt').write_text('camera_feed_42')
    tools=handlers(root)
    result=tools['search_files'](r'camera_feed_\d+', '.', 50, True, ['py'])
    assert len(result)==1
    assert result[0]['path'].endswith('alpha.py') and result[0]['match']=='content'


def test_search_files_rejects_invalid_regex(tmp_path):
    root=tmp_path/'ws'; root.mkdir(); (root/'a.txt').write_text('hello')
    result=handlers(root)['search_files']('[', '.', 50, True, None)
    assert result['ok'] is False and 'Invalid search regex' in result['error']


def test_search_files_skips_binary_content(tmp_path):
    root=tmp_path/'ws'; root.mkdir()
    (root/'blob.bin').write_bytes(b'needle\\x00\\x01\\x02' + bytes(range(64)))
    assert handlers(root)['search_files']('needle')==[]


def test_search_files_keeps_sensitive_content_excluded(tmp_path):
    root=tmp_path/'ws'; root.mkdir()
    (root/'.env').write_text('SECRET_NEEDLE=1')
    assert handlers(root)['search_files']('SECRET_NEEDLE')==[]
