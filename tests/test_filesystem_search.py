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


def test_search_and_list_files_with_workspace_prefix(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    books = root / 'books'
    books.mkdir()
    (books / 'python_guide.pdf').write_bytes(b'%PDF-1.4 mock')
    (books / 'rust_guide.pdf').write_bytes(b'%PDF-1.4 mock')
    (root / 'single.pdf').write_bytes(b'%PDF-1.4 mock')

    tools = handlers(root)

    # list_files with workspace prefix and subpaths
    listed_ws = tools['list_files']('workspace')
    assert any(x['name'] == 'books' for x in listed_ws)
    assert any(x['name'] == 'single.pdf' for x in listed_ws)

    listed_books = tools['list_files']('workspace/books')
    assert len(listed_books) == 2
    assert {x['name'] for x in listed_books} == {'python_guide.pdf', 'rust_guide.pdf'}

    # search_files with path 'workspace/books'
    found = tools['search_files']('python', 'workspace/books')
    assert len(found) == 1
    assert found[0]['path'].endswith('python_guide.pdf')

    # search_files with glob pattern *.pdf
    all_pdfs = tools['search_files']('*.pdf', 'workspace/books')
    assert len(all_pdfs) == 2

    # search_files in workspace root finds files in books and root
    root_search = tools['search_files']('*.pdf', 'workspace')
    assert len(root_search) == 3


def test_read_file_directory_and_missing(tmp_path):
    root = tmp_path / 'workspace'; root.mkdir()
    books = root / 'books'; books.mkdir()
    (books / 'test.txt').write_text('content')

    tools = handlers(root)
    # Directory error
    res_dir = tools['read_file']('workspace/books')
    assert res_dir['ok'] is False and 'directory' in res_dir['error'].lower()

    # Missing file error
    res_miss = tools['read_file']('workspace/books/nope.txt')
    assert res_miss['ok'] is False and 'not found' in res_miss['error'].lower()

    # Valid read
    res_read = tools['read_file']('workspace/books/test.txt')
    assert res_read['content'] == 'content'


def test_edit_file_and_delete_file_tools(tmp_path):
    root = tmp_path / 'workspace'; root.mkdir()
    tools = handlers(root)

    # 1. Add file with write_file
    w_res = tools['write_file']('sample.txt', 'alpha\nbeta\ngamma')
    assert w_res['ok'] is True

    # 2. Edit file with edit_file
    e_res = tools['edit_file']('sample.txt', 'beta', 'delta')
    assert e_res['ok'] is True
    assert (root / 'sample.txt').read_text() == 'alpha\ndelta\ngamma'

    # 3. Edit with mismatched old_str returns error
    err_res = tools['edit_file']('sample.txt', 'nonexistent', 'something')
    assert err_res['ok'] is False
    assert 'not found' in err_res['error'].lower()

    # 4. Delete file with delete_file
    d_res = tools['delete_file']('sample.txt')
    assert d_res['ok'] is True
    assert not (root / 'sample.txt').exists()

    # 5. Delete directory recursively
    tools['write_file']('subdir/doc.txt', 'content')
    assert (root / 'subdir' / 'doc.txt').exists()
    d_dir = tools['delete_file']('subdir', recursive=True)
    assert d_dir['ok'] is True
    assert not (root / 'subdir').exists()

    # 6. Deleting workspace root is blocked
    d_root = tools['delete_file']('.')
    assert d_root['ok'] is False
    assert 'cannot delete workspace root' in d_root['error'].lower()


