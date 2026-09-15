from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse
import os, mimetypes, re
import httpx
from .base import Tool
from ..workspace import Workspace
from ..security_policy import sanitize_external_observation

IMAGE_TYPES = {"image/jpeg":".jpg","image/png":".png","image/webp":".webp","image/gif":".gif","image/svg+xml":".svg"}

def _https_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in {"https", "http"} and bool(p.netloc)
    except Exception:
        return False

def build_web_tools(workspace: Workspace, config: dict) -> list[Tool]:
    policy = config.get("policy", {})
    max_mb = int(policy.get("max_download_mb", 25))
    max_bytes = max_mb * 1024 * 1024
    max_text = int(policy.get("max_web_text_chars", 120000))

    def web_fetch(url: str):
        if not _https_url(url):
            return {"ok":False,"error":"Only http/https URLs are allowed."}
        with httpx.Client(follow_redirects=True, timeout=20.0, headers={"User-Agent":"LivingAssistant/0.1"}) as c:
            with c.stream("GET", url) as r:
                r.raise_for_status()
                ctype = r.headers.get("content-type","")
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        return {"ok":False,"error":f"Response exceeded {max_mb} MB limit."}
        if "text" not in ctype and "json" not in ctype and "xml" not in ctype and "html" not in ctype:
            return {"ok":False,"error":f"Non-text content type {ctype}; use download_url."}
        text = bytes(buf).decode(r.encoding or "utf-8", errors="replace")
        return {"ok":True,"url":str(r.url),"content_type":ctype,"content":sanitize_external_observation(text, max_text)}

    def download_url(url: str, destination: str):
        if not _https_url(url):
            return {"ok":False,"error":"Only http/https URLs are allowed."}
        dest = workspace.resolve(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(follow_redirects=True, timeout=30.0, headers={"User-Agent":"LivingAssistant/0.1"}) as c:
            with c.stream("GET", url) as r:
                r.raise_for_status()
                ctype = r.headers.get("content-type","").split(";")[0].strip().lower()
                total = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            f.close()
                            dest.unlink(missing_ok=True)
                            return {"ok":False,"error":f"Download exceeded {max_mb} MB limit."}
                        f.write(chunk)
        return {"ok":True,"path":str(dest),"bytes":total,"content_type":ctype}

    def image_search(query: str, num: int = 5):
        key = os.environ.get("SERPER_API_KEY")
        if not key:
            return {"ok":False,"error":"SERPER_API_KEY is not configured. Direct image download still works."}
        with httpx.Client(timeout=20.0) as c:
            r = c.post("https://google.serper.dev/images", headers={"X-API-KEY":key,"Content-Type":"application/json"},
                       json={"q":query,"num":max(1,min(num,10))})
            r.raise_for_status()
            items = []
            for x in r.json().get("images", [])[:max(1,min(num,10))]:
                items.append({"title":x.get("title"),"imageUrl":x.get("imageUrl"),"link":x.get("link"),"source":x.get("source")})
            return {"ok":True,"results":items}

    def web_search(query: str, num: int = 5):
        key = os.environ.get("SERPER_API_KEY")
        if not key:
            return {"ok":False,"error":"SERPER_API_KEY is not configured."}
        with httpx.Client(timeout=20.0) as c:
            r = c.post("https://google.serper.dev/search", headers={"X-API-KEY":key,"Content-Type":"application/json"},
                       json={"q":query,"num":max(1,min(num,10))})
            r.raise_for_status()
            return {"ok":True,"results":[
                {"title":x.get("title"),"link":x.get("link"),"snippet":x.get("snippet")}
                for x in r.json().get("organic", [])[:max(1,min(num,10))]
            ]}

    return [
        Tool("web_fetch", "Fetch a web page as untrusted observation text with size/time limits.",
             {"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}, web_fetch),
        Tool("download_url", "Download a URL into the approved workspace. Never executes the downloaded file.",
             {"type":"object","properties":{"url":{"type":"string"},"destination":{"type":"string"}},"required":["url","destination"]}, download_url),
        Tool("image_search", "Search the web for image URLs using configured search provider.",
             {"type":"object","properties":{"query":{"type":"string"},"num":{"type":"integer","default":5}},"required":["query"]}, image_search),
        Tool("web_search", "Search the web using configured search provider.",
             {"type":"object","properties":{"query":{"type":"string"},"num":{"type":"integer","default":5}},"required":["query"]}, web_search),
    ]
