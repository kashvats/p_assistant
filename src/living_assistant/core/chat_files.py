"""Files in chat: what the user attaches (images, video, audio, PDFs, tables, documents)
and what the assistant shows (downloads and other workspace files).

Attached files are stored once under the data directory, named by content hash
(``file_<sha16>.<ext>``, images keep their ``img_`` ids from ``vision.attachments``)
with a small JSON sidecar holding the original name. ``describe`` turns a file into
text the chat model can use: PDF text, a table's shape/columns/first rows, a video's
metadata plus a few frames for the vision model. Everything read out of a file is
untrusted content, never instructions.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
from pathlib import Path

from living_assistant.core.config import data_dir

MAX_BYTES = {"video": 500 * 2**20, "audio": 200 * 2**20}
DEFAULT_MAX_BYTES = 50 * 2**20
KINDS = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"},
    "video": {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"},
    "audio": {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"},
    "pdf": {".pdf"},
    "table": {".csv", ".tsv", ".xlsx", ".xlsm", ".xls"},
    "document": {".docx", ".pptx"},
    "text": {".txt", ".md", ".json", ".log", ".xml", ".yaml", ".yml", ".py", ".js", ".ts", ".html", ".css", ".ini", ".toml", ".sql"},
}
EXT_KIND = {ext: kind for kind, exts in KINDS.items() for ext in exts}
# Served inline in the browser. Anything that could run script (html, svg, xml) is sent as a download.
INLINE_KINDS = {"image", "video", "audio", "pdf"}
_ID = re.compile(r"^file_[0-9a-f]{16}$")
FILE_MARKER = re.compile(r"\[file (file_[0-9a-f]{16})(?: ([^\]\n]{1,160}))?\]")


def root() -> Path:
    path = data_dir() / "attachments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def kind_of(name: str) -> str:
    return EXT_KIND.get(Path(str(name or "")).suffix.lower(), "other")


def safe_name(name: str) -> str:
    """A display name that fits in a marker: no brackets, newlines or path parts."""
    base = Path(str(name or "").replace("\\", "/")).name
    return re.sub(r"[\[\]\r\n\t]+", " ", base).strip()[:160] or "file"


async def save_upload(request, name: str) -> dict:
    """Store a raw-body upload (``POST /files/upload``), refusing anything over the size limit while it streams."""
    from fastapi import HTTPException

    limit = max(MAX_BYTES.values())
    too_big = HTTPException(status_code=413, detail=f"Files are limited to {limit // 2**20} MB.")
    if int(request.headers.get("content-length") or 0) > limit:
        raise too_big
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise too_big
        chunks.append(chunk)
    try:
        return save(b"".join(chunks), name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def save(data: bytes, name: str = "") -> dict:
    """Store an attached file. Images go through the image store (validated, ``img_`` id)."""
    name = safe_name(name)
    kind = kind_of(name)
    if not data:
        raise ValueError("The file is empty.")
    limit = MAX_BYTES.get(kind, DEFAULT_MAX_BYTES)
    if len(data) > limit:
        raise ValueError(f"{name} is larger than {limit // 2**20} MB.")
    if kind == "image" or (kind == "other" and data[:8].startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8"))):
        from living_assistant.vision import attachments

        saved = attachments.save(data, name)
        return {**saved, "kind": "image", "name": name, "marker": f"[image {saved['id']}]"}
    file_id = "file_" + hashlib.sha256(data).hexdigest()[:16]
    ext = Path(name).suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,6}", Path(name).suffix.lower()) else ".bin"
    target = root() / f"{file_id}{ext}"
    if not target.exists():
        target.write_bytes(data)
    info = {"id": file_id, "name": name, "kind": kind, "bytes": len(data),
            "mime": mimetypes.guess_type(name)[0] or "application/octet-stream"}
    (root() / f"{file_id}.json").write_text(json.dumps(info), encoding="utf-8")
    if kind == "pdf":  # convert to Markdown once, in the background, so later reads get tables and headings
        from living_assistant.core import doc_markdown

        doc_markdown.convert_later(target)
    return {**info, "marker": f"[file {file_id} {name}]"}


def path_of(file_id: str) -> Path | None:
    if not _ID.match(str(file_id or "")):
        return None
    matches = [p for p in sorted(root().glob(f"{file_id}.*")) if p.suffix != ".json" and not p.name.endswith(".llm.md")]
    return matches[0] if matches else None


def info(file_id: str) -> dict | None:
    path = path_of(file_id)
    if path is None:
        return None
    try:
        meta = json.loads((root() / f"{file_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {"id": file_id, "name": path.name, "kind": kind_of(path.name), "bytes": path.stat().st_size}
    return meta


def resolve(ref: str, workspace=None) -> tuple[Path, str]:
    """(path, display name) for an attached id (``file_…``/``img_…``) or a workspace path."""
    ref = str(ref or "").strip()
    if ref.startswith("file_"):
        path = path_of(ref)
        if path is None:
            raise FileNotFoundError(f"No attached file {ref}.")
        return path, (info(ref) or {}).get("name") or path.name
    if ref.startswith("img_"):
        from living_assistant.vision import attachments

        path = attachments.path_of(ref)
        if path is None:
            raise FileNotFoundError(f"No attached image {ref}.")
        return path, path.name
    if workspace is None:
        raise FileNotFoundError(f"{ref} is not an attached file.")
    path = workspace.resolve(ref)  # raises WorkspaceViolation outside the allowed roots
    if path.is_dir():
        raise FileNotFoundError(f"'{ref}' is a directory, not a file. Use list_files to inspect directory contents.")
    if not path.is_file():
        raise FileNotFoundError(f"No file at {ref}.")
    return path, path.name


# ---- reading files for the model --------------------------------------------------------

def describe(path: Path, name: str = "", max_chars: int = 8000, page: int = 1) -> dict:
    """Text the chat model can use, plus facts about the file. ``page`` pages through long text."""
    name = name or path.name
    kind = kind_of(name) if kind_of(name) != "other" else kind_of(path.name)
    out = {"name": name, "kind": kind, "bytes": path.stat().st_size}
    try:
        if kind in ("pdf", "document", "table", "text"):
            # Every readable file is given to the model as Markdown (tables, headings kept); see doc_markdown.
            from living_assistant.core import doc_markdown

            md, how = doc_markdown.to_markdown(path, name, kind)
            out.update(_paged(md, max_chars, page), format=how)
            if kind == "pdf":
                out.update(_pdf_facts(path))
            elif kind == "table":
                out.update({k: v for k, v in _table(path).items() if k != "text"})
        elif kind in ("video", "audio"):
            out.update(media_info(path))
        elif kind != "image":
            out["text"] = "Binary file; its contents cannot be read as text."
    except Exception as exc:  # a damaged or unusual file must not break the chat turn
        out["error"] = f"Could not read {name}: {str(exc)[:300]}"
    return out


def _paged(text: str, max_chars: int, page: int) -> dict:
    pages = max(1, -(-len(text) // max_chars))
    page = min(max(1, int(page)), pages)
    return {"text": text[(page - 1) * max_chars: page * max_chars], "page": page, "pages": pages, "chars": len(text)}


def _pdf_facts(path: Path) -> dict:
    import pymupdf

    with pymupdf.open(str(path)) as doc:
        pages = doc.page_count
        sample = "".join(doc[i].get_text("text") for i in range(min(3, pages)))
    out = {"pdf_pages": pages}
    if len(re.sub(r"\s", "", sample)) < 20:
        out["note"] = "The PDF has almost no text layer (probably scanned); use read_image_text on rendered pages for OCR."
    return out


def _pdf(path: Path, max_chars: int, page: int) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    texts = []
    for i, p in enumerate(reader.pages):
        texts.append(f"--- page {i + 1} ---\n{(p.extract_text() or '').strip()}")
    text = "\n\n".join(texts)
    out = {"pdf_pages": len(reader.pages), **_paged(text, max_chars, page)}
    if len(re.sub(r"--- page \d+ ---|\s", "", text)) < 20:
        out["note"] = "The PDF has almost no text layer (probably scanned); use read_image_text on rendered pages for OCR."
    return out


def load_table(path: Path, sheet: str | int | None = None):
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        return pd.read_csv(path, sep="\t" if suffix == ".tsv" else None, engine="python", on_bad_lines="skip")
    return pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)


def _table(path: Path) -> dict:
    df = load_table(path)
    sheets = None
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        import pandas as pd

        sheets = pd.ExcelFile(path).sheet_names
    numeric = df.select_dtypes("number")
    summary = numeric.describe().round(4).to_string() if not numeric.empty else ""
    return {"rows": int(df.shape[0]), "columns": [str(c) for c in df.columns][:200],
            "dtypes": {str(c): str(t) for c, t in list(df.dtypes.items())[:200]},
            "text": "First rows:\n" + df.head(20).to_string(max_colwidth=60)[:6000]
                    + (f"\n\nNumeric summary:\n{summary[:3000]}" if summary else ""),
            **({"sheets": sheets} if sheets else {})}


def table_preview(path: Path, limit: int = 200, sheet: str | None = None) -> dict:
    df = load_table(path, sheet)
    head = df.head(limit)
    rows = [[None if (isinstance(v, float) and v != v) else (v if isinstance(v, (int, float, bool)) else str(v)) for v in row]
            for row in head.itertuples(index=False, name=None)]
    return {"columns": [str(c) for c in df.columns], "rows": rows, "total_rows": int(df.shape[0])}


def _office_text(path: Path) -> str:
    """Text of a .docx/.pptx without extra dependencies (they are zipped XML)."""
    import zipfile

    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if re.match(r"word/document\.xml$|ppt/slides/slide\d+\.xml$", n)]
        parts = []
        for n in sorted(names, key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)) if re.search(r"\d+\.xml$", n) else 0):
            xml = z.read(n).decode("utf-8", "replace")
            xml = re.sub(r"</w:p>|</a:p>", "\n", xml)
            parts.append(re.sub(r"<[^>]+>", "", xml))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip()


def _ffmpeg(tool: str = "ffmpeg") -> str | None:
    return shutil.which(tool)


def media_info(path: Path) -> dict:
    probe = _ffmpeg("ffprobe")
    if not probe:
        return {"note": "ffprobe is not installed, so only the file size is known."}
    run = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height",
                          "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    data = json.loads(run.stdout or "{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    out = {"duration_seconds": round(float((data.get("format") or {}).get("duration") or 0), 2),
           "streams": [s.get("codec_type") for s in streams]}
    if video:
        out.update(width=video.get("width"), height=video.get("height"), video_codec=video.get("codec_name"))
    return out


def video_frames(path: Path, count: int = 3) -> list[bytes]:
    """A few evenly spaced frames (JPEG) so the vision model can see what a video shows."""
    ffmpeg = _ffmpeg()
    duration = media_info(path).get("duration_seconds") or 0
    if not ffmpeg or duration <= 0:
        return []
    frames = []
    for i in range(count):
        at = duration * (i + 0.5) / count
        run = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{at:.2f}", "-i", str(path), "-frames:v", "1",
                              "-vf", "scale='min(1024,iw)':-2", "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
                             capture_output=True, timeout=60)
        if run.returncode == 0 and run.stdout:
            frames.append(run.stdout)
    return frames


# ---- showing files in chat ----------------------------------------------------------------

def media_item(path: Path, name: str = "", ref: str | None = None, caption: str = "") -> dict:
    """What a chat UI needs to show a file: a ref it can fetch (attachment id or workspace path) and its kind."""
    name = name or path.name
    return {"ref": ref or str(path), "name": name, "kind": kind_of(name) if kind_of(name) != "other" else kind_of(path.name),
            "bytes": path.stat().st_size, **({"caption": caption[:300]} if caption else {})}


def media_from_result(result, workspace=None, limit: int = 6) -> list[dict]:
    """Files a tool produced or asked to show: an explicit ``media`` list, or a downloaded ``path``."""
    if not isinstance(result, dict) or result.get("ok") is False or result.get("quarantined"):
        return []
    items = []
    for item in result.get("media") or []:
        if not isinstance(item, dict) or not item.get("ref"):
            continue
        try:  # re-check every ref: only attached files and workspace files may be shown
            path, name = resolve(str(item["ref"]), workspace)
        except Exception:
            continue
        items.append(media_item(path, item.get("name") or name, ref=str(item["ref"]) if str(item["ref"]).startswith(("file_", "img_")) else str(path),
                                caption=str(item.get("caption") or "")))
    if not items:
        for key in ("path", "file", "saved_to", "destination"):
            value = result.get(key)
            if isinstance(value, str) and value and workspace is not None:
                try:
                    path = workspace.resolve(value)
                except Exception:
                    continue
                if path.is_file() and kind_of(path.name) != "other":
                    items.append(media_item(path, ref=str(path)))
                    break
    return items[:limit]
