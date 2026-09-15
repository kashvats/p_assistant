from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import re, shutil
from .workspace import Workspace
from .approval import ApprovalManager
from .security_policy import sanitize_external_observation
from .security_utils import url_network_scope, safe_display_url, is_sensitive_path
from .config import data_dir

BLOCKED_HOSTS = {'169.254.169.254', 'metadata.google.internal', '100.100.100.200'}


def safe_browser_url(url: str) -> bool:
    """Syntactic/browser-scheme check. Runtime network scope is checked separately."""
    try:
        p = urlparse(url)
        return p.scheme in {'http','https'} and bool(p.netloc) and not (p.username or p.password) and (p.hostname or '').lower() not in BLOCKED_HOSTS
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

    def _authorize_url(self, url: str, purpose: str) -> dict:
        if not safe_browser_url(url):
            return {'ok': False, 'blocked': True, 'error': 'Only credential-free http/https URLs are allowed.'}
        scope, reason = url_network_scope(url, resolve=True)
        if scope == 'invalid':
            return {'ok': False, 'blocked': True, 'error': reason or 'URL could not be validated.'}
        host = (urlparse(url).hostname or '').lower()
        if scope == 'private':
            req = self.approval.request(
                f'{purpose} private/local browser target {safe_display_url(url)}',
                f'{reason or "Target is not public."} Browser access to local/private services can expose authenticated infrastructure.',
                'PRIVATE_NETWORK_ACCESS',
            )
            if not req.get('allowed'):
                return {'ok': False, 'approval_required': True, **req}
            return {'ok': True, 'scope': 'private', 'private_hosts': {host}}
        return {'ok': True, 'scope': 'public', 'private_hosts': set()}

    @staticmethod
    def _install_route_guard(context, private_hosts: set[str]):
        def guard(route):
            request_url = route.request.url
            try:
                parsed = urlparse(request_url)
                if parsed.scheme in {'data','blob','about'}:
                    return route.continue_()
                if parsed.scheme not in {'http','https'}:
                    return route.abort()
                host = (parsed.hostname or '').lower()
                scope, _reason = url_network_scope(request_url, resolve=True)
                if scope == 'invalid':
                    return route.abort()
                if scope == 'private' and host not in private_hosts:
                    return route.abort()
                return route.continue_()
            except Exception:
                return route.abort()
        context.route('**/*', guard)

    def _screenshot_target(self, path: str) -> tuple[Path | None, dict | None]:
        target = self.workspace.resolve(path)
        if is_sensitive_path(target):
            req = self.approval.request(
                f'Write browser screenshot to sensitive path {target}',
                'A screenshot would overwrite/create a path normally reserved for credentials or private keys.',
                'SENSITIVE_FILE_ACCESS',
            )
            if not req.get('allowed'):
                return None, {'ok': False, 'approval_required': True, **req}
        target.parent.mkdir(parents=True, exist_ok=True)
        return target, None

    def snapshot(self, url: str, screenshot: str | None = None, max_chars: int = 40000) -> dict:
        auth = self._authorize_url(url, 'Open')
        if not auth.get('ok'):
            return auth
        sync_playwright = self._playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=False)
            self._install_route_guard(context, set(auth.get('private_hosts') or set()))
            page = context.new_page()
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                final_scope, _ = url_network_scope(page.url, resolve=True)
                final_host = (urlparse(page.url).hostname or '').lower()
                if final_scope == 'private' and final_host not in set(auth.get('private_hosts') or set()):
                    return {'ok': False, 'blocked_navigation': True, 'error': 'Navigation redirected to an unapproved private/local host.'}
                text = page.locator('body').inner_text(timeout=10000)[:max_chars]
                title = page.title(); final_url = page.url; shot = None
                if screenshot:
                    target, error = self._screenshot_target(screenshot)
                    if error:
                        return error
                    page.screenshot(path=str(target), full_page=True); shot = str(target)
                return {'ok': True, 'title': title, 'url': final_url, 'text': sanitize_external_observation(text, max_chars), 'screenshot': shot}
            finally:
                browser.close()

    def interact(self, url: str, action: str, selector: str, value: str | None = None) -> dict:
        auth = self._authorize_url(url, 'Open')
        if not auth.get('ok'):
            return auth
        if action not in {'click','fill'}:
            return {'ok': False, 'error': 'Only click/fill are supported.'}
        summary = f'Browser {action} on {safe_display_url(url)} selector={selector!r}'
        req = self.approval.request(summary, 'Browser interaction can change external account/site state.', 'NETWORK_ACTION')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        sync_playwright = self._playwright()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(accept_downloads=False)
            self._install_route_guard(context, set(auth.get('private_hosts') or set()))
            page = context.new_page()
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                loc = page.locator(selector).first
                if action == 'click': loc.click(timeout=10000)
                else: loc.fill(value or '', timeout=10000)
                page.wait_for_timeout(750)
                final_scope, _ = url_network_scope(page.url, resolve=True)
                final_host = (urlparse(page.url).hostname or '').lower()
                if final_scope == 'private' and final_host not in set(auth.get('private_hosts') or set()):
                    return {'ok': False, 'blocked_navigation': True, 'error': 'Interaction navigated to an unapproved private/local host.'}
                raw = page.locator('body').inner_text()[:20000]
                return {'ok': True, 'url': page.url, 'title': page.title(), 'text': sanitize_external_observation(raw, 20000)}
            finally:
                browser.close()

    def start_session(self, name: str, url: str, persistent: bool = False, allowed_hosts: list[str] | None = None) -> dict:
        auth = self._authorize_url(url, 'Open')
        if not auth.get('ok'):
            return auth
        key = _safe_name(name)
        if key in self._sessions:
            return {'ok': False, 'error': 'A live session with that name already exists.'}
        host = (urlparse(url).hostname or '').lower()
        hosts = {host}
        private_hosts = set(auth.get('private_hosts') or set())
        for item in allowed_hosts or []:
            item = item.strip().lower().rstrip('.')
            if not item:
                continue
            if not re.fullmatch(r'[a-z0-9.:-]+', item, re.I):
                return {'ok': False, 'error': f'Invalid allowed host: {item!r}'}
            hosts.add(item)
            probe = f'http://{item}'
            scope, reason = url_network_scope(probe, resolve=True)
            if scope == 'invalid':
                return {'ok': False, 'blocked': True, 'error': f'Allowed host {item!r} could not be validated: {reason}'}
            if scope == 'private' and item not in private_hosts:
                req = self.approval.request(
                    f'Allow browser session {key} to access private/local host {item}',
                    'Adding a private host lets this browser session send requests to that local/LAN service.',
                    'PRIVATE_NETWORK_ACCESS',
                )
                if not req.get('allowed'):
                    return {'ok': False, 'approval_required': True, **req}
                private_hosts.add(item)
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
        try:
            if persistent:
                profile_dir = data_dir() / 'browser_profiles' / key
                profile_dir.mkdir(parents=True, exist_ok=True)
                context = pw.chromium.launch_persistent_context(str(profile_dir), headless=self.headless, accept_downloads=False)
            else:
                profile_dir = None
                browser = pw.chromium.launch(headless=self.headless)
                context = browser.new_context(accept_downloads=False)
            self._install_route_guard(context, private_hosts)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            final_host = (urlparse(page.url).hostname or '').lower()
            if final_host not in hosts:
                raise RuntimeError(f'Initial navigation redirected outside allowed host scope to {final_host}.')
            self._sessions[key] = {'pw':pw, 'browser':browser, 'context':context, 'page':page, 'persistent':persistent,
                                   'allowed_hosts':hosts, 'private_hosts':private_hosts,
                                   'profile_dir':str(profile_dir) if profile_dir else None}
            return {'ok': True, 'name': key, 'url': page.url, 'title': page.title(), 'persistent': persistent, 'allowed_hosts': sorted(hosts)}
        except Exception as exc:
            try:
                if browser: browser.close()
            except Exception: pass
            try: pw.stop()
            except Exception: pass
            return {'ok': False, 'error': str(exc)}

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
        req=self.approval.request(f'Read rendered content from browser session {key} at {safe_display_url(page.url)}',
                                  'Named browser sessions may contain authenticated or private account data.',
                                  'SENSITIVE_READ')
        if not req.get('allowed'):return {'ok':False,'approval_required':True,**req}
        text=page.locator('body').inner_text(timeout=10000)[:max_chars]; shot=None
        if screenshot:
            target,error=self._screenshot_target(screenshot)
            if error:return error
            page.screenshot(path=str(target),full_page=True); shot=str(target)
        return {'ok':True,'name':key,'title':page.title(),'url':page.url,'text':sanitize_external_observation(text,max_chars),'screenshot':shot}

    def navigate_session(self, name: str, url: str) -> dict:
        if not safe_browser_url(url): return {'ok':False,'error':'Only credential-free http/https URLs are allowed.'}
        try:key,s=self._session(name)
        except KeyError as e:return {'ok':False,'error':str(e)}
        host=(urlparse(url).hostname or '').lower()
        if host not in s['allowed_hosts']:
            return {'ok':False,'blocked':True,'error':f'Host {host} is outside this session scope. Start a new session or explicitly include it.'}
        scope,reason=url_network_scope(url,resolve=True)
        if scope=='invalid':return {'ok':False,'blocked':True,'error':reason or 'URL validation failed.'}
        if scope=='private' and host not in s.get('private_hosts',set()):
            return {'ok':False,'blocked':True,'error':'Private/local host was not approved for this browser session.'}
        s['page'].goto(url,wait_until='domcontentloaded',timeout=30000)
        final_host=(urlparse(s['page'].url).hostname or '').lower()
        if final_host not in s['allowed_hosts']:
            try:s['page'].go_back(wait_until='domcontentloaded',timeout=10000)
            except Exception:pass
            return {'ok':False,'blocked_navigation':True,'error':f'Navigation redirected outside allowed host scope to {final_host}.'}
        return {'ok':True,'name':key,'url':s['page'].url,'title':s['page'].title()}

    def interact_session(self, name: str, action: str, selector: str, value: str | None = None) -> dict:
        if action not in {'click','fill'}: return {'ok':False,'error':'Only click/fill are supported.'}
        try:key,s=self._session(name)
        except KeyError as e:return {'ok':False,'error':str(e)}
        page=s['page']; summary=f'Browser session {key}: {action} selector={selector!r} on {safe_display_url(page.url)}'
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
