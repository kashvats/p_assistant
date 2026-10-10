"""The local API boundary: answer only on loopback host names (plus ASSISTANT_ALLOWED_HOSTS), refuse
cross-origin browser calls from other sites, and require the local API token."""
from __future__ import annotations

import hmac
import os
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from living_assistant.security.api_auth import get_api_token

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}


def allowed_hostnames() -> set[str]:
    extra = {item.strip().lower() for item in os.environ.get("ASSISTANT_ALLOWED_HOSTS", "").split(",") if item.strip()}
    return LOCAL_HOSTS | extra


def host_only(value: str) -> str:
    try:
        cleaned = value.strip()
        if cleaned.startswith("[") and "]" in cleaned:
            return cleaned[1:cleaned.index("]")].lower()
        if cleaned.count(":") > 1:
            # Unbracketed IPv6 literal
            return cleaned.split("%")[0].lower()
        return (urlparse("//" + cleaned).hostname or "").lower()
    except Exception:
        return ""


def origin_is_local_or_same(origin: str, request_host: str) -> bool:
    try:
        parsed = urlparse(origin)
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in (allowed_hostnames() | {request_host})
    except Exception:
        return False


async def local_boundary(request: Request, call_next, label: str = "local assistant API"):
    host = host_only(request.headers.get("host", ""))
    if host not in allowed_hostnames():
        return JSONResponse({"detail": f"Invalid Host header for {label}."}, status_code=400)
    origin = request.headers.get("origin")
    if origin and not origin_is_local_or_same(origin, host):
        return JSONResponse({"detail": f"Cross-origin browser access to the {label} is blocked."}, status_code=403)

    if request.method == "OPTIONS":
        resp = Response(status_code=204)
        if origin and origin_is_local_or_same(origin, host):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Max-Age"] = "86400"
        return resp

    response = await call_next(request)
    if origin and origin_is_local_or_same(origin, host):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


def check_token(authorization: str | None = None, token_param: str | None = None) -> None:
    token = get_api_token()
    supplied = None
    if authorization:
        s = authorization.strip()
        if s.lower().startswith("bearer "):
            s = s[7:].strip()
        supplied = s
    elif token_param:
        supplied = token_param.strip()

    if not supplied or not hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid token")
