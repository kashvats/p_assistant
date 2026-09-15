from living_assistant.browser import safe_browser_url, _safe_name


def test_metadata_blocked_and_local_allowed():
    assert not safe_browser_url('http://169.254.169.254/latest/meta-data')
    assert not safe_browser_url('http://metadata.google.internal/')
    assert safe_browser_url('http://127.0.0.1:3000')


def test_session_name_sanitized():
    assert _safe_name('Retail Eye / dev') == 'Retail-Eye-dev'
