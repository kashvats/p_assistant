from __future__ import annotations

import base64
import hashlib
import http.server
import secrets
import socketserver
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass

import httpx

from living_assistant.connectors.connector_credentials import CredentialStore
from living_assistant.security.security_utils import redact_secrets

GOOGLE_AUTHORIZE='https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN='https://oauth2.googleapis.com/token'
GITHUB_DEVICE='https://github.com/login/device/code'
GITHUB_TOKEN='https://github.com/login/oauth/access_token'


@dataclass
class OAuthManager:
    credentials: CredentialStore
    timeout: float = 20.0
    client: httpx.Client | None = None

    def _client(self):
        return self.client or httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False)

    def _post(self, url: str, **kwargs) -> dict:
        own = self.client is None
        c = self._client()
        try:
            r = c.post(url, **kwargs)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                raise RuntimeError('OAuth provider returned an invalid response.')
            return data
        finally:
            if own: c.close()

    @staticmethod
    def _pkce() -> tuple[str,str]:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
        return verifier, challenge

    def google_authorization_url(self, connector: dict, redirect_uri: str, scopes: list[str]) -> tuple[str,str,str]:
        client_id = self.credentials.env(connector,'CLIENT_ID')
        if not client_id:
            raise RuntimeError(f"{self.credentials.prefix_for(connector)}_CLIENT_ID is required.")
        state = secrets.token_urlsafe(24)
        verifier, challenge = self._pkce()
        q = urllib.parse.urlencode({
            'client_id':client_id,'redirect_uri':redirect_uri,'response_type':'code',
            'scope':' '.join(scopes),'access_type':'offline','prompt':'consent','state':state,
            'code_challenge':challenge,'code_challenge_method':'S256',
        })
        return f'{GOOGLE_AUTHORIZE}?{q}', state, verifier

    def google_exchange(self, connector: dict, code: str, redirect_uri: str, verifier: str) -> dict:
        client_id = self.credentials.env(connector,'CLIENT_ID')
        if not client_id: raise RuntimeError('Google client id is not configured.')
        form={'client_id':client_id,'code':code,'redirect_uri':redirect_uri,'grant_type':'authorization_code','code_verifier':verifier}
        client_secret=self.credentials.env(connector,'CLIENT_SECRET')
        if client_secret: form['client_secret']=client_secret
        data=self._post(GOOGLE_TOKEN,data=form)
        now=time.time(); data['expires_at']=now+int(data.get('expires_in',3600))-60; data['provider']='google'; data['created_at']=now
        self.credentials.save_bundle(connector,data)
        return {'ok':True,'provider':'google','scope':data.get('scope'),'expires_at':data.get('expires_at')}

    def google_login(self, connector: dict, scopes: list[str], timeout_seconds: int=180) -> dict:
        result: dict[str,str] = {}
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                q=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                result['code']=(q.get('code') or [''])[0]; result['state']=(q.get('state') or [''])[0]; result['error']=(q.get('error') or [''])[0]
                body=b'Living Assistant authorization received. You can close this tab.'
                self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self,*_args): return
        with socketserver.TCPServer(('127.0.0.1',0),Handler) as server:
            server.timeout=0.5
            redirect=f'http://127.0.0.1:{server.server_address[1]}/oauth/callback'
            url,state,verifier=self.google_authorization_url(connector,redirect,scopes)
            webbrowser.open(url)
            deadline=time.monotonic()+max(30,timeout_seconds)
            while time.monotonic()<deadline and not (result.get('code') or result.get('error')):
                server.handle_request()
            if result.get('error'): raise RuntimeError(f"Google authorization failed: {result['error']}")
            if not result.get('code'): raise TimeoutError('Timed out waiting for Google authorization callback.')
            if not secrets.compare_digest(result.get('state',''),state): raise RuntimeError('OAuth state mismatch.')
            return self.google_exchange(connector,result['code'],redirect,verifier)

    def microsoft_begin_device(self, connector: dict, scopes: list[str]) -> dict:
        client_id=self.credentials.env(connector,'CLIENT_ID')
        tenant=(connector.get('settings') or {}).get('tenant','common')
        if not client_id: raise RuntimeError(f"{self.credentials.prefix_for(connector)}_CLIENT_ID is required.")
        url=f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode'
        data=self._post(url,data={'client_id':client_id,'scope':' '.join(scopes)})
        return data

    def microsoft_poll_device(self, connector: dict, device: dict) -> dict:
        client_id=self.credentials.env(connector,'CLIENT_ID'); tenant=(connector.get('settings') or {}).get('tenant','common')
        if not client_id: raise RuntimeError('Microsoft client id is not configured.')
        url=f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
        deadline=time.monotonic()+int(device.get('expires_in',900)); interval=max(1,int(device.get('interval',5)))
        own=self.client is None; c=self._client()
        try:
            while time.monotonic()<deadline:
                r=c.post(url,data={'grant_type':'urn:ietf:params:oauth:grant-type:device_code','client_id':client_id,'device_code':device['device_code']})
                try: data=r.json()
                except Exception: data={}
                if r.status_code<400 and data.get('access_token'):
                    now=time.time(); data['expires_at']=now+int(data.get('expires_in',3600))-60; data['provider']='microsoft'; data['created_at']=now
                    self.credentials.save_bundle(connector,data)
                    return {'ok':True,'provider':'microsoft','scope':data.get('scope'),'expires_at':data.get('expires_at')}
                err=data.get('error')
                if err=='authorization_pending': time.sleep(interval); continue
                if err=='slow_down': interval+=5; time.sleep(interval); continue
                raise RuntimeError(f'Microsoft authorization failed: {err or r.status_code}')
            raise TimeoutError('Microsoft device authorization expired.')
        finally:
            if own:c.close()

    def github_begin_device(self, connector: dict, scopes: list[str]) -> dict:
        client_id=self.credentials.env(connector,'CLIENT_ID')
        if not client_id: raise RuntimeError(f"{self.credentials.prefix_for(connector)}_CLIENT_ID is required.")
        return self._post(GITHUB_DEVICE,headers={'Accept':'application/json'},data={'client_id':client_id,'scope':' '.join(scopes)})

    def github_poll_device(self, connector: dict, device: dict) -> dict:
        client_id=self.credentials.env(connector,'CLIENT_ID')
        if not client_id: raise RuntimeError('GitHub client id is not configured.')
        deadline=time.monotonic()+int(device.get('expires_in',900)); interval=max(1,int(device.get('interval',5)))
        own=self.client is None; c=self._client()
        try:
            while time.monotonic()<deadline:
                r=c.post(GITHUB_TOKEN,headers={'Accept':'application/json'},data={'client_id':client_id,'device_code':device['device_code'],'grant_type':'urn:ietf:params:oauth:grant-type:device_code'})
                data=r.json()
                if data.get('access_token'):
                    now=time.time(); data['provider']='github'; data['created_at']=now
                    if data.get('expires_in'): data['expires_at']=now+int(data['expires_in'])-60
                    self.credentials.save_bundle(connector,data)
                    return {'ok':True,'provider':'github','scope':data.get('scope'),'expires_at':data.get('expires_at')}
                err=data.get('error')
                if err=='authorization_pending': time.sleep(interval); continue
                if err=='slow_down': interval+=5; time.sleep(interval); continue
                raise RuntimeError(f'GitHub authorization failed: {err or "unknown error"}')
            raise TimeoutError('GitHub device authorization expired.')
        finally:
            if own:c.close()

    def refresh(self, connector: dict) -> str | None:
        bundle=self.credentials.load_bundle(connector)
        refresh=bundle.get('refresh_token')
        if not refresh: return None
        provider=connector.get('provider')
        client_id=self.credentials.env(connector,'CLIENT_ID')
        if not client_id: return None
        if provider=='google':
            form={'client_id':client_id,'refresh_token':refresh,'grant_type':'refresh_token'}
            secret=self.credentials.env(connector,'CLIENT_SECRET')
            if secret: form['client_secret']=secret
            data=self._post(GOOGLE_TOKEN,data=form)
        elif provider=='microsoft':
            tenant=(connector.get('settings') or {}).get('tenant','common')
            scopes=(connector.get('settings') or {}).get('oauth_scopes') or []
            data=self._post(f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token',data={'client_id':client_id,'refresh_token':refresh,'grant_type':'refresh_token','scope':' '.join(scopes)})
        else:
            return None
        now=time.time(); data.setdefault('refresh_token',refresh); data['expires_at']=now+int(data.get('expires_in',3600))-60; data['provider']=provider; data['created_at']=now
        self.credentials.save_bundle(connector,data)
        return data.get('access_token')
