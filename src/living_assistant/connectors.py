from __future__ import annotations

from pathlib import Path
from typing import Any
import base64
import json
import os
import re
import secrets
import threading
import time
import urllib.parse

import httpx

from .approval import ApprovalManager
from .config import data_dir
from .connector_credentials import CredentialStore
from .connector_oauth import OAuthManager
from .security_policy import sanitize_external_observation
from .security_utils import redact_secrets
from .storage_utils import atomic_write_json

KINDS={'mail','calendar','files','contacts','messaging','productivity','developer','custom'}
_SECRET_KEY_RE=re.compile(r'(?i)(password|passwd|pwd|token|secret|api[_-]?key|client[_-]?secret|private[_-]?key)')
_SECRET_VALUE_RE=re.compile(
    r'(?i)(?:'
    r'\bgh[pousr]_[A-Za-z0-9]{20,}\b|'
    r'\bgithub_pat_[A-Za-z0-9_]{20,}\b|'
    r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b|'
    r'\bsk-(?:live-|test-)?[A-Za-z0-9_-]{20,}\b|'
    r'\bAIza[0-9A-Za-z_-]{20,}\b|'
    r'\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}'
    r')'
)

PROVIDER_ACTIONS: dict[str,dict[str,dict[str,Any]]] = {
 'google': {
   'gmail.list': {'cap':'mail.read','write':False}, 'gmail.get': {'cap':'mail.read','write':False},
   'gmail.send': {'cap':'mail.send','write':True},
   'calendar.list': {'cap':'calendar.read','write':False}, 'calendar.create': {'cap':'calendar.write','write':True},
   'drive.list': {'cap':'files.read','write':False},
 },
 'microsoft': {
   'mail.list': {'cap':'mail.read','write':False}, 'mail.get': {'cap':'mail.read','write':False},
   'mail.send': {'cap':'mail.send','write':True},
   'calendar.list': {'cap':'calendar.read','write':False}, 'calendar.create': {'cap':'calendar.write','write':True},
   'drive.list': {'cap':'files.read','write':False},
 },
 'github': {
   'pr.list': {'cap':'pr.read','write':False}, 'pr.get': {'cap':'pr.read','write':False},
   'pr.files': {'cap':'pr.read','write':False}, 'pr.review': {'cap':'pr.review','write':True},
 },
 'telegram': {'messages.updates': {'cap':'messages.read','write':False}, 'messages.send': {'cap':'messages.send','write':True}},
 'discord': {'messages.list': {'cap':'messages.read','write':False}, 'messages.send': {'cap':'messages.send','write':True}},
 'notion': {'search': {'cap':'pages.read','write':False}, 'page.get': {'cap':'pages.read','write':False}, 'page.create': {'cap':'pages.write','write':True}},
 'obsidian': {'notes.search': {'cap':'notes.read','write':False}, 'notes.read': {'cap':'notes.read','write':False}, 'notes.write': {'cap':'notes.write','write':True}},
}

DEFAULT_SCOPES={
 'google': {
   'mail.read':'https://www.googleapis.com/auth/gmail.readonly','mail.send':'https://www.googleapis.com/auth/gmail.send',
   'calendar.read':'https://www.googleapis.com/auth/calendar.readonly','calendar.write':'https://www.googleapis.com/auth/calendar.events',
   'files.read':'https://www.googleapis.com/auth/drive.readonly',
 },
 'microsoft': {
   'mail.read':'Mail.Read','mail.send':'Mail.Send','calendar.read':'Calendars.Read','calendar.write':'Calendars.ReadWrite','files.read':'Files.Read',
 },
 'github': {'pr.read':'repo','pr.review':'repo'},
}


def _safe_settings(settings: dict | None) -> dict:
    settings=dict(settings or {})
    def walk(value, path='settings'):
        if isinstance(value, dict):
            for key, child in value.items():
                if _SECRET_KEY_RE.search(str(key)):
                    raise ValueError(f'Secrets may not be stored in connector settings: {path}.{key}')
                walk(child, f'{path}.{key}')
        elif isinstance(value, list):
            for i, child in enumerate(value): walk(child, f'{path}[{i}]')
        elif isinstance(value, str):
            redacted = redact_secrets(value)
            if redacted != value or _SECRET_VALUE_RE.search(value):
                raise ValueError(f'Credential/secret values may not be stored in connector settings: {path}')
    walk(settings)
    raw=json.dumps(settings)
    if len(raw)>20000: raise ValueError('Connector settings are too large.')
    return settings


def _json_external(value: Any, limit: int=120000) -> str:
    text=json.dumps(value,ensure_ascii=False,default=str)
    return sanitize_external_observation(text,limit)


class ConnectorRegistry:
    """Stores non-secret connector metadata. Secrets remain in env/OS keyring."""
    def __init__(self,path: Path | None=None):
        self.path=path or (data_dir()/'connectors.json')
        if not self.path.exists(): atomic_write_json(self.path, {})

    def _load(self):
        try: return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception: return {}
    def _save(self,data): atomic_write_json(self.path, data)

    def add(self,name: str,kind: str,provider: str,capabilities: list[str],env_prefix: str | None=None,enabled: bool=True,settings: dict | None=None) -> dict:
        provider=provider.lower().strip()
        if kind not in KINDS: raise ValueError(f'kind must be one of {sorted(KINDS)}')
        # Preserve metadata-only custom/future providers from earlier releases; only
        # built-in providers receive executable actions and strict capability validation.
        allowed_caps={v['cap'] for v in PROVIDER_ACTIONS.get(provider,{}).values()}
        caps=sorted(set(capabilities))
        unknown=set(caps)-allowed_caps
        if provider in PROVIDER_ACTIONS and unknown: raise ValueError(f'Unsupported capabilities for {provider}: {sorted(unknown)}')
        if env_prefix is not None and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', env_prefix):
            raise ValueError('env_prefix must contain only letters, digits and underscores and start with a letter.')
        data=self._load(); data[name]={
            'kind':kind,'provider':provider,'capabilities':caps,'settings':_safe_settings(settings),
            'env_prefix':env_prefix,'enabled':bool(enabled),'updated_at':time.time(),
        }; self._save(data); return {'name':name,**data[name]}
    def list(self): return self._load()
    def get(self,name: str) -> dict | None:
        item=self._load().get(name); return {'name':name,**item} if item else None
    def remove(self,name: str) -> bool:
        data=self._load(); ok=name in data; data.pop(name,None); self._save(data); return ok
    def set_enabled(self,name: str,enabled: bool) -> bool:
        data=self._load()
        if name not in data: return False
        data[name]['enabled']=bool(enabled); data[name]['updated_at']=time.time(); self._save(data); return True


class ConnectorManager:
    def __init__(self, registry: ConnectorRegistry, approval: ApprovalManager, credentials: CredentialStore | None=None,
                 client: httpx.Client | None=None, max_external_chars: int=120000):
        self.registry=registry; self.approval=approval; self.credentials=credentials or CredentialStore(); self.client=client
        self.oauth=OAuthManager(self.credentials,client=client); self.max_external_chars=max_external_chars
        self._device_transactions: dict[str, dict[str, Any]] = {}
        self._device_transactions_lock = threading.Lock()

    def _client(self): return self.client or httpx.Client(timeout=20.0,trust_env=False,follow_redirects=False)
    def _request(self, method: str, url: str, *, headers: dict | None=None, params: dict | None=None, json_body: Any=None, data: Any=None) -> Any:
        own=self.client is None; c=self._client()
        try:
            r=c.request(method,url,headers=headers,params=params,json=json_body,data=data)
            if r.status_code>=400:
                raise RuntimeError(f'Provider request failed with HTTP {r.status_code}: {redact_secrets(r.text,500)}')
            if not r.content: return {'ok':True}
            ctype=r.headers.get('content-type','')
            return r.json() if 'json' in ctype or r.text.lstrip().startswith(('{','[')) else {'text':r.text[:self.max_external_chars]}
        finally:
            if own:c.close()

    def _token(self, c: dict, *, bot: bool=False) -> str:
        keys=('BOT_TOKEN','TOKEN','ACCESS_TOKEN') if bot else ('ACCESS_TOKEN','TOKEN')
        token=self.credentials.secret(c,*keys)
        bundle=self.credentials.load_bundle(c)
        # Refresh well before provider expiry so the refresh request itself and
        # the immediately following API call cannot straddle token expiration on
        # a slow network. OAuth token bundles already retain their provider expiry
        # metadata; this is only an admission safety window.
        refresh_skew_seconds = 120
        if token and bundle.get('access_token')==token and bundle.get('expires_at') and float(bundle['expires_at'])<=time.time()+refresh_skew_seconds:
            token=self.oauth.refresh(c)
        if not token: token=self.oauth.refresh(c)
        if not token: raise RuntimeError(f'No access token configured for {c["name"]}. Run `organism integration auth {c["name"]}` or configure the documented environment variable.')
        return token

    def status(self,name: str) -> dict:
        c=self.registry.get(name)
        if not c: return {'ok':False,'error':'Unknown connector.'}
        return {'ok':True,'connector':c,'credentials':self.credentials.status(c),'actions':sorted(PROVIDER_ACTIONS.get(c['provider'],{}))}

    def oauth_scopes(self,c: dict) -> list[str]:
        explicit=(c.get('settings') or {}).get('oauth_scopes')
        if isinstance(explicit,list) and explicit: return [str(x) for x in explicit]
        m=DEFAULT_SCOPES.get(c['provider'],{})
        scopes=sorted({m[cap] for cap in c.get('capabilities',[]) if cap in m})
        if c['provider']=='microsoft': scopes=sorted(set(scopes+['offline_access','openid','profile']))
        return scopes

    def _store_device_transaction(self, name: str, device: dict) -> str:
        transaction_id = secrets.token_urlsafe(24)
        expires_in = max(1, int(device.get('expires_in', 900) or 900))
        now = time.monotonic()
        record = {
            'name': name,
            'device': dict(device),
            'expires_at': now + expires_in,
        }
        with self._device_transactions_lock:
            expired = [key for key, value in self._device_transactions.items() if float(value.get('expires_at', 0)) <= now]
            for key in expired:
                self._device_transactions.pop(key, None)
            self._device_transactions[transaction_id] = record
        return transaction_id

    def _consume_device_transaction(self, name: str, transaction_id: str) -> dict | None:
        now = time.monotonic()
        with self._device_transactions_lock:
            record = self._device_transactions.pop(str(transaction_id), None)
        if not record or record.get('name') != name or float(record.get('expires_at', 0)) <= now:
            return None
        device = record.get('device')
        return dict(device) if isinstance(device, dict) else None

    def authorize(self,name: str) -> dict:
        c=self.registry.get(name)
        if not c: return {'ok':False,'error':'Unknown connector.'}
        try:
            scopes=self.oauth_scopes(c)
            if c['provider']=='google': return self.oauth.google_login(c,scopes)
            if c['provider']=='microsoft':
                device=self.oauth.microsoft_begin_device(c,scopes)
                transaction_id=self._store_device_transaction(name,device)
                return {'ok':True,'pending_device_auth':True,'transaction_id':transaction_id,'device':{k:device.get(k) for k in ('user_code','verification_uri','verification_uri_complete','expires_in','interval','message')}}
            if c['provider']=='github':
                device=self.oauth.github_begin_device(c,scopes)
                transaction_id=self._store_device_transaction(name,device)
                return {'ok':True,'pending_device_auth':True,'transaction_id':transaction_id,'device':{k:device.get(k) for k in ('user_code','verification_uri','expires_in','interval')}}
            return {'ok':False,'error':'This provider uses an environment/keyring token rather than OAuth login.'}
        except Exception as e: return {'ok':False,'error':redact_secrets(e,1000)}

    def finish_device_authorize(self,name: str,transaction_id: str, expires_in: int=900, interval: int=5) -> dict:
        c=self.registry.get(name)
        if not c: return {'ok':False,'error':'Unknown connector.'}
        device=self._consume_device_transaction(name, transaction_id)
        if device is None:
            return {'ok':False,'error':'Unknown, expired, or already-consumed device authorization transaction.'}
        try:
            if c['provider']=='microsoft': return self.oauth.microsoft_poll_device(c,device)
            if c['provider']=='github': return self.oauth.github_poll_device(c,device)
            return {'ok':False,'error':'Provider does not use device flow.'}
        except Exception as e: return {'ok':False,'error':redact_secrets(e,1000)}

    def call(self,name: str,action: str,params: dict | None=None) -> dict:
        c=self.registry.get(name); params=dict(params or {})
        if not c: return {'ok':False,'error':'Unknown connector.'}
        if not c.get('enabled',True): return {'ok':False,'blocked':True,'error':'Connector is disabled.'}
        spec=PROVIDER_ACTIONS.get(c['provider'],{}).get(action)
        if not spec: return {'ok':False,'error':f'Unsupported action for {c["provider"]}: {action}'}
        if spec['cap'] not in c.get('capabilities',[]): return {'ok':False,'blocked':True,'error':f'Connector lacks capability {spec["cap"]}.'}
        if spec.get('write'):
            # Keep approval records informative without persisting whole message bodies/documents.
            compact={}
            for k,v in params.items():
                if k.lower() in {'body','content','text'}:
                    compact[k]=f'<{len(str(v))} chars>'
                else:
                    compact[k]=str(v)[:240]
            safe=redact_secrets(json.dumps(compact,sort_keys=True,default=str),1200)
            req=self.approval.request(f'Connector {name}: {action} {safe}',f'External write/send action using provider {c["provider"]}.','CONNECTOR_WRITE')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        try:
            data=self._dispatch(c,action,params)
            return {'ok':True,'connector':name,'action':action,'untrusted_external':True,'data':_json_external(data,self.max_external_chars)}
        except Exception as e:
            return {'ok':False,'error':redact_secrets(e,1000)}

    def _dispatch(self,c: dict,action: str,p: dict) -> Any:
        return getattr(self,f"_{c['provider']}")(c,action,p)

    def _google(self,c,a,p):
        token=self._token(c); h={'Authorization':f'Bearer {token}'}
        if a=='gmail.list': return self._request('GET','https://gmail.googleapis.com/gmail/v1/users/me/messages',headers=h,params={'q':p.get('q'),'maxResults':min(int(p.get('limit',20)),100)})
        if a=='gmail.get': return self._request('GET',f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{urllib.parse.quote(str(p['id']),safe='')}",headers=h,params={'format':p.get('format','metadata')})
        if a=='gmail.send':
            from email.message import EmailMessage
            msg=EmailMessage(); msg['To']=p['to']; msg['Subject']=p.get('subject',''); msg.set_content(p.get('body',''))
            raw=base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip('=')
            return self._request('POST','https://gmail.googleapis.com/gmail/v1/users/me/messages/send',headers=h,json_body={'raw':raw})
        if a=='calendar.list': return self._request('GET','https://www.googleapis.com/calendar/v3/calendars/primary/events',headers=h,params={'timeMin':p.get('time_min'),'timeMax':p.get('time_max'),'maxResults':min(int(p.get('limit',20)),100),'singleEvents':'true','orderBy':'startTime'})
        if a=='calendar.create':
            body={'summary':p['title'],'start':{'dateTime':p['start']},'end':{'dateTime':p.get('end') or p['start']}}
            if p.get('description'): body['description']=p['description']
            return self._request('POST','https://www.googleapis.com/calendar/v3/calendars/primary/events',headers=h,json_body=body)
        if a=='drive.list': return self._request('GET','https://www.googleapis.com/drive/v3/files',headers=h,params={'q':p.get('q'),'pageSize':min(int(p.get('limit',20)),100),'fields':'files(id,name,mimeType,modifiedTime,webViewLink)'})
        raise ValueError(a)

    def _microsoft(self,c,a,p):
        token=self._token(c); h={'Authorization':f'Bearer {token}'}; base='https://graph.microsoft.com/v1.0/me'
        if a=='mail.list': return self._request('GET',base+'/messages',headers=h,params={'$top':min(int(p.get('limit',20)),100),'$search':p.get('q')})
        if a=='mail.get': return self._request('GET',base+f"/messages/{urllib.parse.quote(str(p['id']),safe='')}",headers=h)
        if a=='mail.send': return self._request('POST',base+'/sendMail',headers=h,json_body={'message':{'subject':p.get('subject',''),'body':{'contentType':'Text','content':p.get('body','')},'toRecipients':[{'emailAddress':{'address':p['to']}}]},'saveToSentItems':True})
        if a=='calendar.list': return self._request('GET',base+'/events',headers=h,params={'$top':min(int(p.get('limit',20)),100)})
        if a=='calendar.create': return self._request('POST',base+'/events',headers=h,json_body={'subject':p['title'],'start':{'dateTime':p['start'],'timeZone':p.get('timezone','UTC')},'end':{'dateTime':p.get('end') or p['start'],'timeZone':p.get('timezone','UTC')}})
        if a=='drive.list': return self._request('GET',base+'/drive/root/children',headers=h,params={'$top':min(int(p.get('limit',20)),100)})
        raise ValueError(a)

    def _github(self,c,a,p):
        token=self._token(c); h={'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
        repo=str(p.get('repo') or (c.get('settings') or {}).get('repo') or '')
        if '/' not in repo: raise ValueError('GitHub repo must be owner/name in action params or connector settings.')
        base=f'https://api.github.com/repos/{repo}'
        if a=='pr.list': return self._request('GET',base+'/pulls',headers=h,params={'state':p.get('state','open'),'per_page':min(int(p.get('limit',20)),100)})
        number=int(p['number'])
        if a=='pr.get': return self._request('GET',base+f'/pulls/{number}',headers=h)
        if a=='pr.files': return self._request('GET',base+f'/pulls/{number}/files',headers=h,params={'per_page':min(int(p.get('limit',100)),100)})
        if a=='pr.review': return self._request('POST',base+f'/pulls/{number}/reviews',headers=h,json_body={'body':p.get('body',''),'event':p.get('event','COMMENT')})
        raise ValueError(a)

    def _telegram(self,c,a,p):
        token=self._token(c,bot=True); base=f'https://api.telegram.org/bot{token}'
        if a=='messages.updates': return self._request('GET',base+'/getUpdates',params={'offset':p.get('offset'),'limit':min(int(p.get('limit',50)),100),'timeout':0})
        if a=='messages.send': return self._request('POST',base+'/sendMessage',json_body={'chat_id':p['chat_id'],'text':p['text']})
        raise ValueError(a)

    def _discord(self,c,a,p):
        token=self._token(c,bot=True); h={'Authorization':f'Bot {token}'}; channel=str(p.get('channel_id') or (c.get('settings') or {}).get('channel_id') or '')
        if not channel: raise ValueError('Discord channel_id is required.')
        url=f'https://discord.com/api/v10/channels/{urllib.parse.quote(channel,safe="")}/messages'
        if a=='messages.list': return self._request('GET',url,headers=h,params={'limit':min(int(p.get('limit',50)),100)})
        if a=='messages.send': return self._request('POST',url,headers=h,json_body={'content':p['text']})
        raise ValueError(a)

    def _notion(self,c,a,p):
        token=self._token(c); h={'Authorization':f'Bearer {token}','Notion-Version':'2026-03-11'}
        if a=='search': return self._request('POST','https://api.notion.com/v1/search',headers=h,json_body={'query':p.get('query',''),'page_size':min(int(p.get('limit',20)),100)})
        if a=='page.get': return self._request('GET',f"https://api.notion.com/v1/pages/{urllib.parse.quote(str(p['id']),safe='')}",headers=h)
        if a=='page.create':
            parent=p.get('parent_id') or (c.get('settings') or {}).get('parent_id')
            if not parent: raise ValueError('Notion parent_id is required.')
            title=p.get('title','Untitled')
            body={'parent':{'page_id':parent},'properties':{'title':{'title':[{'text':{'content':title}}]}}}
            return self._request('POST','https://api.notion.com/v1/pages',headers=h,json_body=body)
        raise ValueError(a)

    def _obsidian(self,c,a,p):
        root=Path(str((c.get('settings') or {}).get('vault_path',''))).expanduser().resolve()
        if not root.is_dir(): raise ValueError('Configured Obsidian vault_path does not exist.')
        def resolve(rel):
            target=(root/str(rel)).resolve()
            if target!=root and root not in target.parents: raise ValueError('Note path escapes the configured vault.')
            return target
        if a=='notes.search':
            q=str(p.get('query','')).lower(); out=[]
            for f in root.rglob('*.md'):
                if len(out)>=min(int(p.get('limit',20)),100): break
                try:
                    text=f.read_text(encoding='utf-8',errors='replace')
                    if q in f.name.lower() or q in text.lower(): out.append({'path':str(f.relative_to(root)),'preview':text[:500]})
                except OSError: pass
            return out
        if a=='notes.read':
            f=resolve(p['path']); return {'path':str(f.relative_to(root)),'content':f.read_text(encoding='utf-8',errors='replace')[:self.max_external_chars]}
        if a=='notes.write':
            f=resolve(p['path']); f.parent.mkdir(parents=True,exist_ok=True); f.write_text(str(p.get('content','')),encoding='utf-8'); return {'path':str(f.relative_to(root)),'bytes':f.stat().st_size}
        raise ValueError(a)
