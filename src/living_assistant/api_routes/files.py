"""Files in chat: upload any supported file, and serve attached or workspace files to the chat UIs.

Uploads are the raw request body (no multipart), so a large video does not pass
through base64. Serving is limited to attached files and files inside the allowed
workspace roots; only images, video, audio and PDFs are shown inline, everything
else (html, svg, scripts, office files) is sent as a download so it cannot run in
the app's origin.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.core import chat_files
from living_assistant.core.workspace import WorkspaceViolation

router = APIRouter(tags=["files"])


@router.post("/files/upload")
async def file_upload(request: Request, name: str = Query(min_length=1, max_length=200),
                      authorization: str | None = Header(default=None)):
    authorize(authorization)
    return await chat_files.save_upload(request, name)


def _resolve(ref: str):
    try:
        return chat_files.resolve(ref, runtime().workspace)
    except WorkspaceViolation:
        raise HTTPException(status_code=403, detail="That file is outside the assistant's workspace.")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/files/content")
def file_content(ref: str = Query(min_length=1, max_length=2000), download: bool = False,
                 token: str | None = Query(default=None), authorization: str | None = Header(default=None)):
    """An attached file (file_…/img_…) or a workspace file, for <img>/<video>/<iframe> or download."""
    authorize(authorization, token=token)
    path, name = _resolve(ref)
    kind = chat_files.kind_of(name) if chat_files.kind_of(name) != "other" else chat_files.kind_of(path.name)
    inline = kind in chat_files.INLINE_KINDS and not download
    return FileResponse(path, filename=name, content_disposition_type="inline" if inline else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300",
                                 # Downloads must never render in the app's origin; inline media is displayed
                                 # by the browser's own viewers (a CSP sandbox would block the PDF viewer).
                                 **({} if inline else {"Content-Security-Policy": "sandbox"})})


@router.get("/files/info")
def file_info(ref: str = Query(min_length=1, max_length=2000), authorization: str | None = Header(default=None)):
    authorize(authorization)
    path, name = _resolve(ref)
    return chat_files.media_item(path, name, ref=ref if ref.startswith(("file_", "img_")) else str(path))


@router.get("/files/preview")
def file_preview(ref: str = Query(min_length=1, max_length=2000), sheet: str | None = None,
                 limit: int = Query(default=200, ge=1, le=2000), authorization: str | None = Header(default=None)):
    """Rows of a CSV/XLSX, or the text of a PDF/document/text file, for showing in chat."""
    authorize(authorization)
    path, name = _resolve(ref)
    kind = chat_files.kind_of(name)
    try:
        if kind == "table":
            return {"kind": kind, "name": name, **chat_files.table_preview(path, limit, sheet)}
        if kind in ("pdf", "document", "text"):
            described = chat_files.describe(path, name, max_chars=20000)
            return {"kind": kind, "name": name, **{k: described.get(k) for k in ("text", "page", "pages", "pdf_pages", "error")}}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read {name}: {str(exc)[:300]}")
    raise HTTPException(status_code=400, detail="No preview for this kind of file.")
