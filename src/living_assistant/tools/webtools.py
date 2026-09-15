from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse
import os
import httpx
from .base import Tool
from ..workspace import Workspace
from ..security_policy import sanitize_external_observation
from ..quarantine import QuarantineVault, is_risky_download, download_risk_reasons
from ..approval import ApprovalManager

IMAGE_TYPES = {'image/jpeg','.jpg','image/png','.png','image/webp','.webp','image/gif','.gif','image/svg+xml','.svg'}


def _https_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in {'https','http'} and bool(p.netloc) and (p.hostname or '').lower() not in {'169.254.169.254','metadata.google.internal'}
    except Exception:
        return False


def build_web_tools(workspace: Workspace, config: dict, approval: ApprovalManager | None = None,
                    quarantine: QuarantineVault | None = None) -> list[Tool]:
    policy = config.get('policy', {})
    dcfg = config.get('downloads', {})
    max_mb = int(policy.get('max_download_mb', 25)); max_bytes = max_mb * 1024 * 1024
    max_text = int(policy.get('max_web_text_chars', 120000))
    quarantine = quarantine or QuarantineVault()

    def web_fetch(url: str):
        if not _https_url(url): return {'ok':False,'error':'Only http/https URLs are allowed.'}
        with httpx.Client(follow_redirects=True, timeout=20.0, headers={'User-Agent':'LivingAssistant/0.6'}) as c:
            with c.stream('GET', url) as r:
                r.raise_for_status(); ctype = r.headers.get('content-type',''); buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes: return {'ok':False,'error':f'Response exceeded {max_mb} MB limit.'}
                final_url = str(r.url); encoding = r.encoding or 'utf-8'
        if not any(x in ctype for x in ('text','json','xml','html')):
            return {'ok':False,'error':f'Non-text content type {ctype}; use download_url.'}
        text = bytes(buf).decode(encoding, errors='replace')
        return {'ok':True,'url':final_url,'content_type':ctype,'content':sanitize_external_observation(text, max_text)}

    def _stream_download(url: str, dest: Path) -> tuple[int,str,str]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(follow_redirects=True, timeout=30.0, headers={'User-Agent':'LivingAssistant/0.6'}) as c:
            with c.stream('GET', url) as r:
                r.raise_for_status(); ctype = r.headers.get('content-type','').split(';')[0].strip().lower(); total = 0
                final_url = str(r.url)
                with open(dest, 'wb') as f:
                    for chunk in r.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            f.close(); dest.unlink(missing_ok=True)
                            raise ValueError(f'Download exceeded {max_mb} MB limit.')
                        f.write(chunk)
        return total, ctype, final_url

    def download_url(url: str, destination: str):
        if not _https_url(url): return {'ok':False,'error':'Only http/https URLs are allowed.'}
        dest = workspace.resolve(destination)
        # Download first to quarantine temp so remote MIME type can influence release.
        item_id, temp = quarantine.reserve(url, dest.name)
        try:
            total, ctype, final_url = _stream_download(url, temp)
        except Exception as e:
            temp.unlink(missing_ok=True); return {'ok':False,'error':str(e)}
        risky = is_risky_download(dest.name, ctype)
        quarantine_non_image = bool(dcfg.get('quarantine_all_non_images', False)) and not ctype.startswith('image/')
        if (bool(dcfg.get('quarantine_risky_files', True)) and risky) or quarantine_non_image:
            item = quarantine.register(item_id,temp,final_url,ctype,original_name=dest.name,risk_reasons=download_risk_reasons(dest.name,ctype))
            return {'ok':True,'quarantined':True,'item':item,
                    'message':'Downloaded into quarantine and not released/executed.'}
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp.replace(dest)
        return {'ok':True,'path':str(dest),'bytes':total,'content_type':ctype,'quarantined':False}

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
        key = os.environ.get('SERPER_API_KEY')
        if not key: return {'ok':False,'error':'SERPER_API_KEY is not configured. Direct image download still works.'}
        with httpx.Client(timeout=20.0) as c:
            r = c.post('https://google.serper.dev/images', headers={'X-API-KEY':key,'Content-Type':'application/json'},
                       json={'q':query,'num':max(1,min(num,10))}); r.raise_for_status()
            return {'ok':True,'results':[{'title':x.get('title'),'imageUrl':x.get('imageUrl'),'link':x.get('link'),'source':x.get('source')} for x in r.json().get('images',[])[:max(1,min(num,10))]]}

    def web_search(query: str, num: int = 5):
        key = os.environ.get('SERPER_API_KEY')
        if not key: return {'ok':False,'error':'SERPER_API_KEY is not configured.'}
        with httpx.Client(timeout=20.0) as c:
            r = c.post('https://google.serper.dev/search', headers={'X-API-KEY':key,'Content-Type':'application/json'},
                       json={'q':query,'num':max(1,min(num,10))}); r.raise_for_status()
            return {'ok':True,'results':[{'title':x.get('title'),'link':x.get('link'),'snippet':x.get('snippet')} for x in r.json().get('organic',[])[:max(1,min(num,10))]]}

    return [
        Tool('web_fetch','Fetch a web page as untrusted observation text with size/time limits.',{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},web_fetch),
        Tool('download_url','Download a URL. Risky executables/scripts are automatically quarantined and never executed.',{'type':'object','properties':{'url':{'type':'string'},'destination':{'type':'string'}},'required':['url','destination']},download_url),
        Tool('quarantine_list','List downloaded files currently tracked by the quarantine vault.',{'type':'object','properties':{}},quarantine_list),
        Tool('quarantine_release','Release a quarantined file into the approved workspace. Requires explicit approval.',{'type':'object','properties':{'item_id':{'type':'string'},'destination':{'type':'string'}},'required':['item_id','destination']},quarantine_release),
        Tool('image_search','Search the web for image URLs using configured search provider.',{'type':'object','properties':{'query':{'type':'string'},'num':{'type':'integer','default':5}},'required':['query']},image_search),
        Tool('web_search','Search the web using configured search provider.',{'type':'object','properties':{'query':{'type':'string'},'num':{'type':'integer','default':5}},'required':['query']},web_search),
    ]
