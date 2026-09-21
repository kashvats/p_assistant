from __future__ import annotations
from .. import __version__
from pathlib import Path
from urllib.parse import urljoin
from collections import deque
import datetime as dt
import os
import sqlite3
import threading
import time
import httpx
from .base import Tool
from ..workspace import Workspace
from ..security_policy import sanitize_external_observation
from ..security_utils import url_network_scope, safe_display_url, redact_secrets
from ..quarantine import QuarantineVault, is_risky_download, download_risk_reasons
from ..approval import ApprovalManager
from ..browser import BrowserController
from ..config import data_dir

IMAGE_TYPES = {'image/jpeg','.jpg','.jpeg','image/png','.png','image/webp','.webp','image/gif','.gif','image/svg+xml','.svg'}
IMAGE_CONTENT_EXTENSIONS = {
    'image/jpeg': ('.jpg', {'.jpg', '.jpeg'}),
    'image/png': ('.png', {'.png'}),
    'image/webp': ('.webp', {'.webp'}),
    'image/gif': ('.gif', {'.gif'}),
    'image/svg+xml': ('.svg', {'.svg'}),
}
MAX_REDIRECTS = 5


class _NetworkGate(Exception):
    def __init__(self, result: dict):
        super().__init__(result.get('error') or result.get('message') or 'Network access blocked')
        self.result = result


def build_web_tools(workspace: Workspace, config: dict, approval: ApprovalManager | None = None,
                    quarantine: QuarantineVault | None = None, browser: BrowserController | None = None) -> list[Tool]:
    policy = config.get('policy', {})
    dcfg = config.get('downloads', {})
    scfg = config.get('web_search', {})
    max_mb = int(policy.get('max_download_mb', 25)); max_bytes = max_mb * 1024 * 1024
    max_text = int(policy.get('max_web_text_chars', 120000))
    quarantine = quarantine or QuarantineVault()

    try:
        max_calls_per_minute = max(0, int(scfg.get('max_calls_per_minute', 20)))
        max_calls_per_day = max(0, int(scfg.get('max_calls_per_day', 0)))
    except (TypeError, ValueError):
        max_calls_per_minute = 20
        max_calls_per_day = 0
    search_calls = deque()
    search_budget_lock = threading.Lock()
    search_budget_db = data_dir() / 'assistant.sqlite3' if max_calls_per_day else None
    if search_budget_db is not None:
        with sqlite3.connect(search_budget_db, timeout=5.0) as conn:
            conn.execute('PRAGMA busy_timeout=5000')
            conn.execute(
                'CREATE TABLE IF NOT EXISTS search_budget ('
                'day TEXT PRIMARY KEY, calls INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)'
            )
            conn.commit()

    def _consume_search_budget() -> dict | None:
        now = time.monotonic()
        with search_budget_lock:
            if max_calls_per_minute:
                cutoff = now - 60.0
                while search_calls and search_calls[0] <= cutoff:
                    search_calls.popleft()
                if len(search_calls) >= max_calls_per_minute:
                    retry_after = max(1, int(60.0 - (now - search_calls[0])))
                    return {
                        'ok': False,
                        'rate_limited': True,
                        'retry_after_seconds': retry_after,
                        'error': f'Search budget exceeded: maximum {max_calls_per_minute} call(s) per minute.',
                    }

            if max_calls_per_day and search_budget_db is not None:
                day = dt.datetime.now(dt.timezone.utc).date().isoformat()
                updated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
                try:
                    with sqlite3.connect(search_budget_db, timeout=5.0, isolation_level=None) as conn:
                        conn.execute('PRAGMA busy_timeout=5000')
                        conn.execute('BEGIN IMMEDIATE')
                        row = conn.execute('SELECT calls FROM search_budget WHERE day=?', (day,)).fetchone()
                        calls = int(row[0]) if row else 0
                        if calls >= max_calls_per_day:
                            conn.rollback()
                            return {
                                'ok': False,
                                'rate_limited': True,
                                'error': f'Search budget exceeded: maximum {max_calls_per_day} call(s) per UTC day.',
                            }
                        if row:
                            conn.execute(
                                'UPDATE search_budget SET calls=?, updated_at=? WHERE day=?',
                                (calls + 1, updated_at, day),
                            )
                        else:
                            conn.execute(
                                'INSERT INTO search_budget(day,calls,updated_at) VALUES(?,?,?)',
                                (day, 1, updated_at),
                            )
                        conn.commit()
                except sqlite3.Error as exc:
                    return {
                        'ok': False,
                        'rate_limited': True,
                        'error': f'Search budget store unavailable: {redact_secrets(exc, 500)}',
                    }

            if max_calls_per_minute:
                search_calls.append(now)
        return None

    def _authorize_target(url: str, purpose: str) -> None:
        scope, reason = url_network_scope(url, resolve=True)
        if scope == 'invalid':
            raise _NetworkGate({'ok': False, 'blocked': True, 'error': reason or 'Invalid URL.'})
        if scope == 'private':
            if approval is None:
                raise _NetworkGate({'ok': False, 'blocked': True, 'error': 'Private/local network access requires explicit approval.'})
            req = approval.request(
                f'{purpose} private/local URL {safe_display_url(url)}',
                f'{reason or "Target is not public."} Access to loopback/LAN/private services can expose local infrastructure.',
                'PRIVATE_NETWORK_ACCESS',
            )
            if not req.get('allowed'):
                raise _NetworkGate({'ok': False, 'approval_required': True, **req})

    def _open_stream(client: httpx.Client, url: str, purpose: str) -> tuple[httpx.Response, str]:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            _authorize_target(current, purpose)
            request = client.build_request('GET', current)
            response = client.send(request, stream=True)
            if response.status_code in {301,302,303,307,308}:
                location = response.headers.get('location')
                response.close()
                if not location:
                    raise ValueError('Redirect response did not include a Location header.')
                current = urljoin(current, location)
                continue
            return response, current
        raise ValueError(f'Too many redirects (>{MAX_REDIRECTS}).')

    def web_fetch(url: str):
        try:
            with httpx.Client(timeout=20.0, headers={'User-Agent':f'LivingAssistant/{__version__}'}, trust_env=False) as c:
                r, _current = _open_stream(c, url, 'Fetch')
                try:
                    r.raise_for_status(); ctype = r.headers.get('content-type',''); buf = bytearray()
                    for chunk in r.iter_bytes():
                        buf += chunk
                        if len(buf) > max_bytes:
                            return {'ok':False,'error':f'Response exceeded {max_mb} MB limit.'}
                    final_url = str(r.url); encoding = r.encoding or 'utf-8'
                finally:
                    r.close()
        except _NetworkGate as gate:
            return gate.result
        except Exception as e:
            return {'ok': False, 'error': redact_secrets(e, 1000)}
        if not any(x in ctype for x in ('text','json','xml','html')):
            return {'ok':False,'error':f'Non-text content type {ctype}; use download_url.'}
        text = bytes(buf).decode(encoding, errors='replace')
        return {'ok':True,'url':final_url,'content_type':ctype,'content':sanitize_external_observation(text, max_text)}

    def _stream_download(url: str, dest: Path) -> tuple[int,str,str]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=30.0, headers={'User-Agent':f'LivingAssistant/{__version__}'}, trust_env=False) as c:
            r, _current = _open_stream(c, url, 'Download')
            try:
                r.raise_for_status(); ctype = r.headers.get('content-type','').split(';')[0].strip().lower(); total = 0
                final_url = str(r.url)
                with open(dest, 'wb') as f:
                    for chunk in r.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            f.close(); dest.unlink(missing_ok=True)
                            raise ValueError(f'Download exceeded {max_mb} MB limit.')
                        f.write(chunk)
            finally:
                r.close()
        return total, ctype, final_url

    def download_url(url: str, destination: str, _image_only: bool = False):
        dest = workspace.resolve(destination)
        item_id, temp = quarantine.reserve(url, dest.name)
        try:
            total, ctype, final_url = _stream_download(url, temp)
        except _NetworkGate as gate:
            temp.unlink(missing_ok=True); return gate.result
        except Exception as e:
            temp.unlink(missing_ok=True); return {'ok':False,'error':redact_secrets(e,1000)}

        if _image_only:
            image_type = IMAGE_CONTENT_EXTENSIONS.get(ctype)
            if image_type is None:
                temp.unlink(missing_ok=True)
                return {'ok':False,'error':f'URL did not return a supported image (content-type: {ctype or "unknown"}).'}
            canonical_ext, allowed_exts = image_type
            suffix = dest.suffix.lower()
            if suffix and suffix not in allowed_exts:
                temp.unlink(missing_ok=True)
                return {'ok':False,'error':f'Image content type {ctype} does not match destination extension {suffix}.'}
            if not suffix:
                dest = workspace.resolve(f'{destination}{canonical_ext}')
            # SVG is active XML content and can carry script/external references. Keep it quarantined.
            if ctype == 'image/svg+xml':
                item = quarantine.register(
                    item_id, temp, final_url, ctype, original_name=dest.name,
                    risk_reasons=['active_svg_image'],
                )
                return {'ok':True,'quarantined':True,'item':item,
                        'message':'SVG image downloaded into quarantine because SVG can contain active content.'}

        risky = is_risky_download(dest.name, ctype)
        quarantine_non_image = bool(dcfg.get('quarantine_all_non_images', False)) and not ctype.startswith('image/')
        if (bool(dcfg.get('quarantine_risky_files', True)) and risky) or quarantine_non_image:
            item = quarantine.register(item_id,temp,final_url,ctype,original_name=dest.name,risk_reasons=download_risk_reasons(dest.name,ctype))
            return {'ok':True,'quarantined':True,'item':item,
                    'message':'Downloaded into quarantine and not released/executed.'}
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp.replace(dest)
        return {'ok':True,'path':str(dest),'bytes':total,'content_type':ctype,'quarantined':False}

    def download_image(url: str, destination: str):
        return download_url(url, destination, _image_only=True)

    def quarantine_list(): return quarantine.list()

    def quarantine_release(item_id: str, destination: str):
        item = quarantine.get(item_id)
        if not item: return {'ok':False,'error':'Unknown quarantine item.'}
        if approval is None: return {'ok':False,'error':'Approval manager is required.'}
        target = workspace.resolve(destination)
        req = approval.request(f'Release quarantined file {item_id} -> {target}',
                               f"SHA256={item.get('sha256')} source={item.get('source_url')}", 'QUARANTINE_RELEASE')
        if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        verification=quarantine.verify(item_id)
        if not verification.get('ok'):
            return {'ok':False,'blocked':True,'error':'Quarantine artifact changed after registration; refusing release.','verification':verification}
        source = Path(item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target); quarantine.mark_released(item_id, str(target))
        return {'ok':True,'path':str(target),'sha256':item.get('sha256')}

    def image_search(query: str, num: int = 5):
        query = (query or '').strip()
        if not query:
            return {'ok': False, 'error': 'Image search query must not be empty.'}
        provider = str(scfg.get('provider', 'auto')).strip().lower()
        if provider not in {'auto', 'serper', 'browser', 'disabled'}:
            return {'ok': False, 'error': f'Unsupported web search provider: {provider!r}.'}
        if provider == 'disabled':
            return {'ok': False, 'disabled': True, 'error': 'Web search is disabled by configuration.'}
        try:
            requested = int(num)
            configured_max = int(scfg.get('max_results', 8))
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'Search result limits must be integers.'}
        limit = max(1, min(requested, max(1, min(configured_max, 10))))

        key = os.environ.get('SERPER_API_KEY')
        if provider == 'serper' and not key:
            return {'ok': False, 'provider': 'serper', 'error': 'SERPER_API_KEY is not configured.'}
        if provider == 'browser' and (browser is None or not callable(getattr(browser, 'search_images', None))):
            return {'ok': False, 'provider': 'browser', 'error': 'Browser image search provider is unavailable.'}
        if provider == 'auto' and not key and (browser is None or not callable(getattr(browser, 'search_images', None))):
            return {'ok': False, 'provider': 'browser', 'error': 'Browser image search provider is unavailable. Install/configure the browser extra or set SERPER_API_KEY.'}
        budget_error = _consume_search_budget()
        if budget_error:
            return budget_error

        serper_error = None
        if provider in {'auto', 'serper'} and key:
            try:
                timeout = max(1.0, float(scfg.get('serper_timeout_seconds', 15)))
                with httpx.Client(timeout=timeout, trust_env=False) as c:
                    r = c.post(
                        'https://google.serper.dev/images',
                        headers={'X-API-KEY': key, 'Content-Type': 'application/json'},
                        json={'q': query, 'num': limit},
                    )
                    r.raise_for_status()
                    results = []
                    for item in r.json().get('images', [])[:limit]:
                        results.append({
                            'title': sanitize_external_observation(str(item.get('title') or ''), 4000),
                            'imageUrl': str(item.get('imageUrl') or ''),
                            'link': str(item.get('link') or ''),
                            'source': sanitize_external_observation(str(item.get('source') or ''), 2000),
                        })
                    return {'ok': True, 'provider': 'serper', 'results': results}
            except Exception as exc:
                serper_error = redact_secrets(exc, 1000)
                if provider == 'serper':
                    return {'ok': False, 'provider': 'serper', 'error': f'Serper image search failed: {serper_error}'}

        if browser is None or not callable(getattr(browser, 'search_images', None)):
            message = 'Browser image search provider is unavailable.'
            if provider == 'auto' and not key:
                message += ' Install/configure the browser extra or set SERPER_API_KEY.'
            if serper_error:
                message += f' Serper fallback reason: {serper_error}'
            return {'ok': False, 'provider': 'browser', 'error': message}

        try:
            result = browser.search_images(query, limit)
        except Exception as exc:
            return {'ok': False, 'provider': 'browser', 'error': f'Browser image search failed: {redact_secrets(exc, 1000)}'}
        if not isinstance(result, dict):
            return {'ok': False, 'provider': 'browser', 'error': 'Browser image search provider returned an invalid response.'}
        if not result.get('ok'):
            output = dict(result)
            output['ok'] = False
            output.setdefault('provider', 'browser')
            if output.get('error'):
                output['error'] = redact_secrets(output['error'], 1000)
            return output

        cleaned = []
        for item in (result.get('results') or [])[:limit]:
            if not isinstance(item, dict):
                continue
            cleaned.append({
                'title': sanitize_external_observation(str(item.get('title') or ''), 4000),
                'imageUrl': str(item.get('imageUrl') or ''),
                'link': str(item.get('link') or ''),
                'source': sanitize_external_observation(str(item.get('source') or ''), 2000),
            })
        return {'ok': True, 'provider': str(result.get('provider') or 'browser'), 'results': cleaned}

    def web_search(query: str, num: int = 5):
        query = (query or '').strip()
        if not query:
            return {'ok': False, 'error': 'Search query must not be empty.'}
        provider = str(scfg.get('provider', 'auto')).strip().lower()
        if provider not in {'auto', 'serper', 'browser', 'disabled'}:
            return {'ok': False, 'error': f'Unsupported web search provider: {provider!r}.'}
        if provider == 'disabled':
            return {'ok': False, 'disabled': True, 'error': 'Web search is disabled by configuration.'}
        try:
            requested = int(num)
            configured_max = int(scfg.get('max_results', 8))
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'Search result limits must be integers.'}
        limit = max(1, min(requested, max(1, min(configured_max, 10))))

        key = os.environ.get('SERPER_API_KEY')
        if provider == 'serper' and not key:
            return {'ok': False, 'provider': 'serper', 'error': 'SERPER_API_KEY is not configured.'}
        if provider == 'browser' and (browser is None or not callable(getattr(browser, 'search_web', None))):
            return {'ok': False, 'provider': 'browser', 'error': 'Browser search provider is unavailable.'}
        if provider == 'auto' and not key and (browser is None or not callable(getattr(browser, 'search_web', None))):
            return {'ok': False, 'provider': 'browser', 'error': 'Browser search provider is unavailable. Install/configure the browser extra or set SERPER_API_KEY.'}
        budget_error = _consume_search_budget()
        if budget_error:
            return budget_error

        serper_error = None
        if provider in {'auto', 'serper'} and key:
            try:
                timeout = max(1.0, float(scfg.get('serper_timeout_seconds', 15)))
                with httpx.Client(timeout=timeout, trust_env=False) as c:
                    r = c.post(
                        'https://google.serper.dev/search',
                        headers={'X-API-KEY': key, 'Content-Type': 'application/json'},
                        json={'q': query, 'num': limit},
                    )
                    r.raise_for_status()
                    results = []
                    for item in r.json().get('organic', [])[:limit]:
                        results.append({
                            'title': sanitize_external_observation(str(item.get('title') or ''), 4000),
                            'link': str(item.get('link') or ''),
                            'snippet': sanitize_external_observation(str(item.get('snippet') or ''), 8000),
                        })
                    return {'ok': True, 'provider': 'serper', 'results': results}
            except Exception as exc:
                serper_error = redact_secrets(exc, 1000)
                if provider == 'serper':
                    return {'ok': False, 'provider': 'serper', 'error': f'Serper search failed: {serper_error}'}

        if browser is None or not callable(getattr(browser, 'search_web', None)):
            message = 'Browser search provider is unavailable.'
            if provider == 'auto' and not key:
                message += ' Install/configure the browser extra or set SERPER_API_KEY.'
            if serper_error:
                message += f' Serper fallback reason: {serper_error}'
            return {'ok': False, 'provider': 'browser', 'error': message}

        try:
            result = browser.search_web(query, limit)
        except Exception as exc:
            return {'ok': False, 'provider': 'browser', 'error': f'Browser search failed: {redact_secrets(exc, 1000)}'}
        if not isinstance(result, dict):
            return {'ok': False, 'provider': 'browser', 'error': 'Browser search provider returned an invalid response.'}
        if not result.get('ok'):
            output = dict(result)
            output['ok'] = False
            output.setdefault('provider', 'browser')
            if output.get('error'):
                output['error'] = redact_secrets(output['error'], 1000)
            return output

        cleaned = []
        for item in (result.get('results') or [])[:limit]:
            if not isinstance(item, dict):
                continue
            cleaned.append({
                'title': sanitize_external_observation(str(item.get('title') or ''), 4000),
                'link': str(item.get('link') or ''),
                'snippet': sanitize_external_observation(str(item.get('snippet') or ''), 8000),
            })
        return {'ok': True, 'provider': str(result.get('provider') or 'browser'), 'results': cleaned}

    return [
        Tool('web_fetch','Fetch a web page as untrusted observation text with size/time limits. Private/local targets require explicit approval, including redirects.',{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},web_fetch),
        Tool('download_url','Download a URL. Private/local targets require approval; risky executables/scripts are quarantined.',{'type':'object','properties':{'url':{'type':'string'},'destination':{'type':'string'}},'required':['url','destination']},download_url),
        Tool('download_image','Download a raster image URL into the workspace with content-type/extension validation. Missing extensions are inferred; SVG is quarantined as active content.',{'type':'object','properties':{'url':{'type':'string'},'destination':{'type':'string'}},'required':['url','destination']},download_image),
        Tool('quarantine_list','List downloaded files currently tracked by the quarantine vault.',{'type':'object','properties':{}},quarantine_list),
        Tool('quarantine_release','Release a quarantined file into the approved workspace. Requires explicit approval.',{'type':'object','properties':{'item_id':{'type':'string'},'destination':{'type':'string'}},'required':['item_id','destination']},quarantine_release),
        Tool('image_search','Search the web for image URLs using configured search provider.',{'type':'object','properties':{'query':{'type':'string'},'num':{'type':'integer','default':5}},'required':['query']},image_search),
        Tool('web_search','Search the web using configured search provider.',{'type':'object','properties':{'query':{'type':'string'},'num':{'type':'integer','default':5}},'required':['query']},web_search),
    ]
