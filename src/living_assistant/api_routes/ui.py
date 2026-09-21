from __future__ import annotations

import mimetypes
from importlib import resources
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["ui"])

_WEBUI_ROOT = resources.files("living_assistant").joinpath("webui")
_ALLOWED_ASSET_ROOTS = {"src", "dist", "vendor"}
_ALLOWED_ASSET_SUFFIXES = {".js", ".css", ".map"}


def _security_headers() -> dict[str, str]:
    return {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    page = _WEBUI_ROOT.joinpath("index.html").read_text(encoding="utf-8")
    # The source index stays Vite-native (/src, /vendor, /dist). The packaged
    # Python service exposes the same local assets under a namespaced route.
    for prefix in ("src", "vendor", "dist"):
        page = page.replace(f'="/{prefix}/', f'="/dashboard-assets/{prefix}/')
    headers = _security_headers()
    headers.update(
        {
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'self'; img-src 'self' data:; "
                "connect-src 'self'; style-src 'self'; "
                "script-src 'self'; frame-ancestors 'none'; "
                "base-uri 'none'; object-src 'none'"
            ),
        }
    )
    return HTMLResponse(page, headers=headers)


@router.get("/dashboard-assets/{asset_path:path}")
def dashboard_asset(asset_path: str):
    """Serve only packaged, non-sensitive dashboard runtime assets."""
    path = PurePosixPath(asset_path)
    if (
        not asset_path
        or path.is_absolute()
        or ".." in path.parts
        or len(path.parts) < 2
        or path.parts[0] not in _ALLOWED_ASSET_ROOTS
        or path.suffix.lower() not in _ALLOWED_ASSET_SUFFIXES
    ):
        raise HTTPException(status_code=404, detail="Dashboard asset not found")

    target = _WEBUI_ROOT.joinpath(*path.parts)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Dashboard asset not found")

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = _security_headers()
    headers["Cache-Control"] = (
        "public, max-age=31536000, immutable"
        if path.parts[0] == "vendor"
        else "public, max-age=300"
    )
    return Response(target.read_bytes(), media_type=media_type, headers=headers)
