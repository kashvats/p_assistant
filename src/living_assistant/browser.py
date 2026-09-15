from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import re, shutil
from .workspace import Workspace
from .approval import ApprovalManager
from .security_policy import sanitize_external_observation
from .config import data_dir

BLOCKED_HOSTS = {'169.254.169.254', 'metadata.google.internal', '100.100.100.200'}

def safe_browser_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in {'http','https'} and bool(p.netloc) and (p.hostname or '').lower() not in BLOCKED_HOSTS
    except Exception:
        return False

def _safe_name(name: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_.-]+', '-', name).strip('-._')[:80]
    if not cleaned:
        raise ValueError('Session name must contain letters or numbers.')
    return cleaned

@dataclass
class BrowserController:
    workspace: Workspace
    approval: ApprovalManager
    headless: bool = False
    _sessions: dict = field(default_factory=dict, init=False, repr=False)

    def _playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError as e:
            raise RuntimeError('Browser automation is optional. Install with: pip install -e ".[browser]" && playwright install chromium') from e

    def snapshot(self, url: str, screenshot: str | None = None, max_chars: int = 40000) -> dict:
        if not safe_browser_url(url):
            return {'ok': False, 'error': 'Only safe http/https URLs are allowed.'}
        sync_playwright = self._playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            text = page.locator('body').inner_text(timeout=10000)[:max_chars]
            title = page.title(); final_url = page.url; shot = None
            if screenshot:
                target = self.workspace.resolve(screenshot); target.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(target), full_page=True); shot = str(target)
            browser.close()
            return {'ok': True, 'title': title, 'url': final_url, 'text': sanitize_external_observation(text, max_chars), 'screenshot': shot}

    def interact(self, url: str, action: str, selector: str, value: str | None = None) -> dict:
        if not safe_browser_url(url):
            return {'ok': False, 'error': 'Only safe http/https URLs are allowed.'}
        if action not in {'click','fill'}:
            return {'ok': False, 'error': 'Only click/fill are supported.'}
        summary = f'Browser {action} on {url} selector={selector!r}'
        req = self.approval.request(summary, 'Browser interaction can change external account/site state.', 'NETWORK_ACTION')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        sync_playwright = self._playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page(); page.goto(url, wait_until='domcontentloaded', timeout=30000)
            loc = page.locator(selector).first
            if action == 'click': loc.click(timeout=10000)
            else: loc.fill(value or '', timeout=10000)
            page.wait_for_timeout(750)
            raw = page.locator('body').inner_text()[:20000]
            result = {'ok': True, 'url': page.url, 'title': page.title(), 'text': sanitize_external_observation(raw, 20000)}
            browser.close(); return result

    def start_session(self, name: str, url: str, persistent: bool = False, allowed_hosts: list[str] | None = None) -> dict:
        if not safe_browser_url(url):
            return {'ok': False, 'error': 'Only safe http/https URLs are allowed.'}
        key = _safe_name(name)
        if key in self._sessions:
            return {'ok': False, 'error': 'A live session with that name already exists.'}
        host = (urlparse(url).hostname or '').lower()
        hosts = {host}
        for item in allowed_hosts or []:
            item = item.strip().lower()
            if item: hosts.add(item)
        if persistent:
            req = self.approval.request(
                f'Create persistent isolated browser profile {key} for {sorted(hosts)}',
                'Persistent browser profiles store site state/cookies in an assistant-only directory.',
                'SENSITIVE_PERSISTENCE',
            )
            if not req.get('allowed'):
                return {'ok': False, 'approval_required': True, **req}
        sync_playwright = self._playwright(); pw = sync_playwright().start()
        browser = None
        if persistent:
            profile_dir = data_dir() / 'browser_profiles' / key
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = pw.chromium.launch_persistent_context(str(profile_dir), headless=self.headless, accept_downloads=False)
        else:
            profile_dir = None
            browser = pw.chromium.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        self._sessions[key] = {'pw':pw, 'browser':browser, 'context':context, 'page':page, 'persistent':persistent, 'allowed_hosts':hosts, 'profile_dir':str(profile_dir) if profile_dir else None}
        return {'ok': True, 'name': key, 'url': page.url, 'title': page.title(), 'persistent': persistent, 'allowed_hosts': sorted(hosts)}

    def list_sessions(self) -> list[dict]:
        out=[]
        for name,s in self._sessions.items():
            page=s['page']
            out.append({'name':name,'url':page.url,'persistent':s['persistent'],'allowed_hosts':sorted(s['allowed_hosts']),'profile_dir':s['profile_dir']})
        return out

    def _session(self, name: str):
        key=_safe_name(name)
        if key not in self._sessions:
            raise KeyError('Unknown/live browser session.')
        return key,self._sessions[key]

    def snapshot_session(self, name: str, screenshot: str | None = None, max_chars: int = 40000) -> dict:
        try: key,s=self._session(name)
        except KeyError as e: return {'ok':False,'error':str(e)}
        page=s['page']
        req=self.approval.request(f'Read rendered content from browser session {key} at {page.url}',
                                  'Named browser sessions may contain authenticated or private account data.',
                                  'SENSITIVE_READ')
        if not req.get('allowed'):return {'ok':False,'approval_required':True,**req}
        text=page.locator('body').inner_text(timeout=10000)[:max_chars]; shot=None
        if screenshot:
            target=self.workspace.resolve(screenshot); target.parent.mkdir(parents=True,exist_ok=True); page.screenshot(path=str(target),full_page=True); shot=str(target)
        return {'ok':True,'name':key,'title':page.title(),'url':page.url,'text':sanitize_external_observation(text,max_chars),'screenshot':shot}

    def navigate_session(self, name: str, url: str) -> dict:
        if not safe_browser_url(url): return {'ok':False,'error':'Only safe http/https URLs are allowed.'}
        try:key,s=self._session(name)
        except KeyError as e:return {'ok':False,'error':str(e)}
        host=(urlparse(url).hostname or '').lower()
        if host not in s['allowed_hosts']:
            return {'ok':False,'blocked':True,'error':f'Host {host} is outside this session scope. Start a new session or explicitly include it.'}
        s['page'].goto(url,wait_until='domcontentloaded',timeout=30000)
        return {'ok':True,'name':key,'url':s['page'].url,'title':s['page'].title()}

    def interact_session(self, name: str, action: str, selector: str, value: str | None = None) -> dict:
        if action not in {'click','fill'}: return {'ok':False,'error':'Only click/fill are supported.'}
        try:key,s=self._session(name)
        except KeyError as e:return {'ok':False,'error':str(e)}
        page=s['page']; summary=f'Browser session {key}: {action} selector={selector!r} on {page.url}'
        req=self.approval.request(summary,'Browser interaction can change external account/site state.','NETWORK_ACTION')
        if not req.get('allowed'):return {'ok':False,'approval_required':True,**req}
        loc=page.locator(selector).first
        if action=='click':loc.click(timeout=10000)
        else:loc.fill(value or '',timeout=10000)
        page.wait_for_timeout(500)
        current_host=(urlparse(page.url).hostname or '').lower()
        if current_host not in s['allowed_hosts']:
            try: page.go_back(wait_until='domcontentloaded',timeout=10000)
            except Exception: pass
            return {'ok':False,'blocked_navigation':True,'error':f'Interaction navigated outside allowed host scope to {current_host}.'}
        return {'ok':True,'name':key,'url':page.url,'title':page.title()}

    def close_session(self, name: str, delete_profile: bool = False) -> dict:
        try:key,s=self._session(name)
        except KeyError as e:return {'ok':False,'error':str(e)}
        profile=s.get('profile_dir')
        try:s['context'].close()
        except Exception:pass
        try:
            if s.get('browser'):s['browser'].close()
        except Exception:pass
        try:s['pw'].stop()
        except Exception:pass
        self._sessions.pop(key,None)
        deleted=False
        if delete_profile and profile:
            req=self.approval.request(f'Delete persistent browser profile {profile}','This deletes stored isolated browser site state.','DESTRUCTIVE_LOCAL')
            if req.get('allowed'):
                shutil.rmtree(profile,ignore_errors=True);deleted=True
        return {'ok':True,'name':key,'profile_deleted':deleted}
