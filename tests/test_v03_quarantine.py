from pathlib import Path
from living_assistant.quarantine import is_risky_download, QuarantineVault, sha256_file


def test_risky_download_detection():
    assert is_risky_download('setup.exe', 'application/octet-stream')
    assert is_risky_download('thing.bin', 'application/x-msdownload')
    assert not is_risky_download('photo.jpg', 'image/jpeg')


def test_quarantine_register(tmp_path):
    vault = QuarantineVault(tmp_path / 'q')
    item_id, path = vault.reserve('https://example.com/a.exe')
    path.write_bytes(b'abc')
    item = vault.register(item_id, path, 'https://example.com/a.exe', 'application/x-msdownload')
    assert item['status'] == 'quarantined'
    assert item['sha256'] == sha256_file(path)
    assert vault.get(item_id)['bytes'] == 3
