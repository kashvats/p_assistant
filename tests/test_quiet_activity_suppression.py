from living_assistant.browser import BrowserController
from living_assistant.desktop_intelligence import DesktopController


class Approval:
    def request(self, *args, **kwargs):
        raise AssertionError('approval should not be reached while quiet mode blocks activity')


class Workspace:
    def resolve(self, path):
        raise AssertionError('workspace access should not be reached while quiet mode blocks activity')


def test_browser_activity_is_blocked_before_network_or_playwright():
    browser=BrowserController(Workspace(), Approval(), quiet_provider=lambda: True)
    for result in [
        browser.search_web('test'),
        browser.search_images('test'),
        browser.snapshot('https://example.com'),
        browser.interact('https://example.com','click','button'),
        browser.start_session('work','https://example.com'),
        browser.navigate_session('missing','https://example.com'),
        browser.interact_session('missing','click','button'),
        browser.snapshot_session('missing'),
    ]:
        assert result['blocked'] is True and result['quiet_mode'] is True


def test_browser_status_and_cleanup_paths_are_not_trapped_by_quiet_mode():
    browser=BrowserController(Workspace(), Approval(), quiet_provider=lambda: True)
    assert browser.list_sessions() == []
    out=browser.close_session('missing')
    assert out['ok'] is False and 'Unknown' in out['error']


def test_desktop_sensitive_observation_is_blocked_before_capture_or_approval():
    desktop=DesktopController(Workspace(), Approval(), {'desktop':{'vision_enabled':True,'vision_model':'vision'}}, quiet_provider=lambda: True)
    assert desktop.windows()['quiet_mode'] is True
    assert desktop.accessibility_tree()['quiet_mode'] is True
    assert desktop.screenshot()['quiet_mode'] is True
    assert desktop.analyze_screen()['quiet_mode'] is True
    # Non-observational status remains available during quiet/focus mode.
    assert 'platform' in desktop.status()
