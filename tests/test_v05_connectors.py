from living_assistant.connectors import ConnectorRegistry


def test_connector_registry_stores_metadata_not_secret(tmp_path):
    r=ConnectorRegistry(tmp_path/'connectors.json')
    item=r.add('work-mail','mail','future-gmail',['read','draft'],'WORK_MAIL')
    assert item['env_prefix']=='WORK_MAIL'
    raw=(tmp_path/'connectors.json').read_text()
    assert 'password' not in raw.lower()
    assert r.set_enabled('work-mail',False)
