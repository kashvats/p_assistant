from living_assistant.browser import safe_browser_url


def test_browser_url_policy():
    assert safe_browser_url('https://example.com')
    assert safe_browser_url('http://localhost:3000')
    assert not safe_browser_url('file:///etc/passwd')
    assert not safe_browser_url('javascript:alert(1)')
