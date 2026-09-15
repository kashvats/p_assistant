from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from .workspace import Workspace
from .approval import ApprovalManager
from .security_policy import sanitize_external_observation


def safe_browser_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in {'http','https'} and bool(p.netloc) and (p.hostname or '').lower() not in {'169.254.169.254','metadata.google.internal'}
    except Exception:
        return False

@dataclass
class BrowserController:
    workspace: Workspace
    approval: ApprovalManager
    headless: bool = False

    def _playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError as e:
            raise RuntimeError('Browser automation is optional. Install with: pip install -e ".[browser]" && playwright install chromium') from e

    def snapshot(self, url: str, screenshot: str | None = None, max_chars: int = 40000) -> dict:
        if not safe_browser_url(url): return {'ok': False, 'error': 'Only http/https URLs are allowed.'}
        sync_playwright = self._playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            text = page.locator('body').inner_text(timeout=10000)[:max_chars]
            title = page.title()
            final_url = page.url
            shot = None
            if screenshot:
                target = self.workspace.resolve(screenshot)
                target.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(target), full_page=True)
                shot = str(target)
            browser.close()
            return {'ok': True, 'title': title, 'url': final_url, 'text': sanitize_external_observation(text, max_chars), 'screenshot': shot}

    def interact(self, url: str, action: str, selector: str, value: str | None = None) -> dict:
        if not safe_browser_url(url): return {'ok': False, 'error': 'Only http/https URLs are allowed.'}
        if action not in {'click','fill'}: return {'ok': False, 'error': 'Only click/fill are supported.'}
        summary = f'Browser {action} on {url} selector={selector!r}'
        req = self.approval.request(summary, 'Browser interaction can change external account/site state.', 'NETWORK_ACTION')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        sync_playwright = self._playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            loc = page.locator(selector).first
            if action == 'click': loc.click(timeout=10000)
            else: loc.fill(value or '', timeout=10000)
            page.wait_for_timeout(750)
            raw = page.locator('body').inner_text()[:20000]
            result = {'ok': True, 'url': page.url, 'title': page.title(), 'text': sanitize_external_observation(raw, 20000)}
            browser.close()
            return result
