from living_assistant.quarantine import QuarantineVault, download_risk_reasons


def test_quarantine_tracks_origin_hash_and_risk(tmp_path):
    q=QuarantineVault(tmp_path/'q')
    item_id,path=q.reserve('https://downloads.example.test/tool.exe','tool.exe')
    path.write_bytes(b'MZ-not-really-an-exe')
    item=q.register(item_id,path,'https://downloads.example.test/tool.exe','application/x-msdownload',original_name='tool.exe')
    assert item['source_host']=='downloads.example.test'
    assert item['original_filename']=='tool.exe'
    assert len(item['sha256'])==64
    assert item['risk_reasons']
    assert 'created_at_iso' in item
    q.record_scan(item_id,'demo',{'clean':True})
    assert q.get(item_id)['last_scan']['provider']=='demo'


def test_download_risk_reasons_explain_why():
    reasons=download_risk_reasons('setup.exe','application/octet-stream')
    assert any('extension' in x for x in reasons)


def test_quarantine_drops_signed_url_query(tmp_path):
    q=QuarantineVault(tmp_path/'q2')
    item_id,path=q.reserve('https://example.test/a.exe?token=secret','a.exe')
    path.write_bytes(b'x')
    item=q.register(item_id,path,'https://example.test/a.exe?token=secret&x=1','application/x-msdownload',original_name='a.exe')
    assert item['source_url']=='https://example.test/a.exe'
    assert 'secret' not in item['source_url']


def test_quarantine_verify_detects_post_registration_tampering(tmp_path):
    q=QuarantineVault(tmp_path/'q3')
    item_id,path=q.reserve('https://example.test/tool.exe','tool.exe')
    path.write_bytes(b'original')
    q.register(item_id,path,'https://example.test/tool.exe','application/x-msdownload',original_name='tool.exe')
    assert q.verify(item_id)['ok'] is True
    path.write_bytes(b'changed')
    result=q.verify(item_id)
    assert result['ok'] is False and result['changed'] is True
