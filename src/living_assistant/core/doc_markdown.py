"""Documents as Markdown for the model: PDFs and HTML papers converted once, cached, read by section.

Markdown keeps what plain text loses - headings and, above all, tables, which is where papers
report their numbers. A PDF is converted once (pymupdf4llm, layout analysis, no OCR) and the
result is cached; conversion takes seconds to a minute, so it runs in one background worker and
readers get the fast plain text until the Markdown is ready. ``sections`` then lets a reader pick
the parts that matter (abstract, method, experiments/results, limitations, conclusion) instead
of cutting the document blindly, and skips the reference list.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import queue
import re
import threading
from pathlib import Path

from living_assistant.core.config import data_dir

_LOCK = threading.Lock()
_QUEUE: queue.Queue = queue.Queue()
_PENDING: set[str] = set()
_WORKER: threading.Thread | None = None


def cache_path(path: Path) -> Path:
    """Attachments cache beside themselves (file_x.pdf -> file_x.md); other files by path, size and mtime."""
    path = Path(path)
    if path.parent.name == "attachments" and path.stem.startswith(("file_", "img_")):
        return path.with_name(f"{path.stem}.llm.md")
    st = path.stat()
    key = hashlib.sha1(f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:20]
    folder = data_dir() / "md_cache"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key}.md"


def cached(path: Path) -> str | None:
    try:
        target = cache_path(path)
        return target.read_text(encoding="utf-8") if target.is_file() else None
    except OSError:
        return None


def plain_text(path: Path) -> str:
    """Fast text of a PDF (well under a second), with page markers."""
    import pymupdf

    with pymupdf.open(str(path)) as doc:
        return "\n\n".join(f"--- page {i + 1} ---\n{page.get_text('text').strip()}" for i, page in enumerate(doc))


def convert_pdf(path: Path) -> str:
    """PDF -> Markdown with tables (slow: layout analysis). Cached; falls back to plain text if the converter is missing."""
    path = Path(path)
    hit = cached(path)
    if hit is not None:
        return hit
    try:
        import pymupdf4llm

        md = pymupdf4llm.to_markdown(str(path), show_progress=False, use_ocr=False)
    except TypeError:  # older pymupdf4llm without use_ocr
        import pymupdf4llm

        md = pymupdf4llm.to_markdown(str(path), show_progress=False)
    except Exception:
        md = plain_text(path)
    md = re.sub(r"\n{4,}", "\n\n\n", md).strip() + "\n"
    try:
        cache_path(path).write_text(md, encoding="utf-8")
    except OSError:
        pass
    return md


def convert_later(path: Path) -> None:
    """Queue a PDF for background conversion (one worker, so conversions never compete with each other)."""
    global _WORKER
    key = str(Path(path).resolve())
    with _LOCK:
        if key in _PENDING or cached(Path(path)) is not None:
            return
        _PENDING.add(key)
        _QUEUE.put(Path(path))
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_work, name="pdf-to-markdown", daemon=True)
            _WORKER.start()


def _work() -> None:
    while True:
        try:
            path = _QUEUE.get(timeout=60)
        except queue.Empty:
            return
        try:
            convert_pdf(path)
        except Exception:
            pass
        finally:
            with _LOCK:
                _PENDING.discard(str(path.resolve()))


# ---- HTML (arXiv full texts) ----------------------------------------------------------------

def html_to_markdown(html: str) -> str:
    """Headings, paragraphs, lists and tables of an HTML article as Markdown; scripts, navigation and styling dropped."""
    h = re.sub(r"(?is)<(script|style|nav|header|footer|svg|button)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r'(?is)<math[^>]*alttext="([^"]*)"[^>]*>.*?</math>', lambda m: f" ${html_lib.unescape(m.group(1))}$ ", h)
    h = re.sub(r"(?is)<math[^>]*>.*?</math>", " ", h)
    h = re.sub(r"(?is)<table[^>]*>(.*?)</table>", lambda m: "\n\n" + _table(m.group(1)) + "\n\n", h)
    for level in range(1, 7):
        h = re.sub(rf"(?is)<h{level}[^>]*>(.*?)</h{level}>", lambda m, l=level: f"\n\n{'#' * l} {_inline(m.group(1))}\n\n", h)
    h = re.sub(r"(?is)<li[^>]*>(.*?)</li>", lambda m: f"\n- {_inline(m.group(1))}", h)
    h = re.sub(r"(?is)<figcaption[^>]*>(.*?)</figcaption>", lambda m: f"\n\n*{_inline(m.group(1))}*\n\n", h)
    h = re.sub(r"(?i)</(p|div|section|article|blockquote)>|<br\s*/?>", "\n\n", h)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", h))
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def _inline(fragment: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _table(inner: str) -> str:
    rows = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", inner):
        cells = [_inline(c).replace("|", "/") for c in re.findall(r"(?is)<t[hd][^>]*>(.*?)</t[hd]>", row)]
        if any(cells):
            rows.append(cells)
    if not rows:
        return _inline(inner)
    width = max(len(r) for r in rows)
    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + "---|" * width)
    caption = re.search(r"(?is)<caption[^>]*>(.*?)</caption>", inner)
    return (f"*{_inline(caption.group(1))}*\n\n" if caption else "") + "\n".join(lines)


# ---- reading by section ---------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$|^\*\*(\d+(?:\.\d+)*\.?\s+[A-Z][^*]{2,80})\*\*\s*$", re.M)
_SKIP = re.compile(r"reference|bibliograph|acknowledg|checklist|broader impact|author contribution", re.I)
_PRIORITY = [
    (re.compile(r"abstract", re.I), 3000),
    (re.compile(r"result|experiment|evaluation|benchmark|ablation|performance|comparison|empirical", re.I), 7000),
    (re.compile(r"limitation|future work|discussion|threats", re.I), 2500),
    (re.compile(r"conclusion|summary", re.I), 2000),
    (re.compile(r"method|approach|framework|architecture|design|setup|implementation|dataset|data", re.I), 3500),
    (re.compile(r"introduction|background|related", re.I), 1500),
]


def sections(md: str) -> list[tuple[str, str]]:
    """(heading, body) pairs in document order; text before the first heading is ('', text)."""
    marks = [(m.start(), (m.group(2) or m.group(3) or "").strip()) for m in _HEADING.finditer(md)]
    if not marks:
        return [("", md)]
    out = [("", md[: marks[0][0]])] if marks[0][0] > 0 else []
    for i, (pos, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(md)
        body = md[pos:end].split("\n", 1)[1] if "\n" in md[pos:end] else ""
        out.append((title, body))
    return out


def focused(md: str, limit: int = 16000) -> str:
    """The parts of a paper that carry its findings, within ``limit`` characters, in document order:
    abstract, results/experiments (tables included), limitations, conclusion, method, then introduction.
    Falls back to beginning + end when the document has no headings."""
    parts = sections(md)
    usable = [(i, t, b) for i, (t, b) in enumerate(parts) if not _SKIP.search(t or "")]
    if len(usable) <= 1:
        text = md
        refs = re.search(r"\n\s*#*\s*(references|bibliography)\s*\n", text[len(text) // 2:], re.I)
        if refs:
            text = text[: len(text) // 2 + refs.start()]
        return text if len(text) <= limit else text[: int(limit * 0.6)] + "\n\n[...]\n\n" + text[-int(limit * 0.4):]
    chosen: dict[int, str] = {}
    budget = limit
    if usable[0][1] == "" and usable[0][2].strip():  # title, authors, often the abstract
        head = usable[0][2].strip()[:2500]
        chosen[usable[0][0]] = head
        budget -= len(head)
    for pattern, cap in _PRIORITY:
        for i, title, body in usable:
            if budget <= 0:
                break
            if i in chosen or not pattern.search(title or ""):
                continue
            take = body.strip()[: min(cap, budget)]
            chosen[i] = f"## {title}\n{take}"
            budget -= len(take) + len(title) + 4
    return "\n\n".join(chosen[i] for i in sorted(chosen)).strip()


# ---- every uploaded file as Markdown ---------------------------------------------------------

def to_markdown(path: Path, name: str = "", kind: str = "", *, wait: bool = False) -> tuple[str, str]:
    """(markdown, how) for any supported file. Slow conversions (PDF layout, image OCR) are cached; with
    ``wait=False`` a PDF not converted yet returns its fast plain text and is converted in the background."""
    path = Path(path)
    name = name or path.name
    ext = Path(name).suffix.lower() or path.suffix.lower()
    if kind == "pdf" or ext == ".pdf":
        hit = cached(path)
        if hit is not None:
            return hit, "markdown (converted, tables kept)"
        if wait:
            return convert_pdf(path), "markdown (converted, tables kept)"
        convert_later(path)
        return plain_text(path), "plain text (Markdown conversion running in the background)"
    if ext == ".docx":
        return _docx(path), "markdown"
    if ext == ".pptx":
        return _pptx(path), "markdown"
    if ext in (".csv", ".tsv", ".xlsx", ".xlsm", ".xls"):
        return _spreadsheet(path), "markdown summary"
    if ext in (".html", ".htm"):
        return html_to_markdown(path.read_text(encoding="utf-8", errors="replace")), "markdown"
    if ext == ".json":
        import json

        raw = path.read_text(encoding="utf-8", errors="replace")
        try:
            return FENCE + "json\n" + json.dumps(json.loads(raw), indent=2, ensure_ascii=False)[:200_000] + "\n" + FENCE + "\n", "formatted JSON"
        except ValueError:
            return raw, "text"
    code = {".py": "python", ".js": "javascript", ".ts": "typescript", ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
            ".toml": "toml", ".ini": "ini", ".xml": "xml", ".css": "css"}.get(ext)
    if code:
        return f"{FENCE}{code}\n{path.read_text(encoding='utf-8', errors='replace')}\n{FENCE}\n", "code"
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"):
        return _image_text(path), "OCR text"
    return path.read_text(encoding="utf-8", errors="replace"), "text"


FENCE = "`" * 3


def _cells(xml: str, cell_tag: str) -> list[str]:
    return [re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", c))).strip().replace("|", "/")
            for c in re.findall(rf"(?s)<{cell_tag}[ >].*?</{cell_tag}>", xml)]


def _md_table(rows: list[list[str]]) -> str:
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + "---|" * width)
    return "\n".join(lines)


def _docx(path: Path) -> str:
    """Word: headings (Heading styles / Title), list items, tables; in document order."""
    import zipfile

    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    body = xml.split("<w:body>", 1)[-1]
    out = []
    for chunk in re.split(r"(?s)(<w:tbl>.*?</w:tbl>)", body):
        if chunk.startswith("<w:tbl>"):
            out.append(_md_table([_cells(r, "w:tc") for r in re.findall(r"(?s)<w:tr[ >].*?</w:tr>", chunk)]))
            continue
        for para in re.findall(r"(?s)<w:p[ >].*?</w:p>", chunk):
            text = html_lib.unescape("".join(re.findall(r"(?s)<w:t(?: [^>]*)?>(.*?)</w:t>", para))).strip()
            if not text:
                continue
            style = re.search(r'<w:pStyle w:val="([^"]+)"', para)
            level = re.search(r"[Hh]eading\s*(\d)", style.group(1)) if style else None
            if style and style.group(1).lower() == "title":
                out.append(f"# {text}")
            elif level:
                out.append(f"{'#' * min(6, int(level.group(1)) + 1)} {text}")
            elif "<w:numPr" in para:
                out.append(f"- {text}")
            else:
                out.append(text)
    return "\n\n".join(x for x in out if x).strip() + "\n"


def _pptx(path: Path) -> str:
    """PowerPoint: one section per slide (title first), bullet text and tables; speaker notes when present."""
    import zipfile

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        out = []
        for n in slides:
            number = re.search(r"(\d+)\.xml$", n).group(1)
            xml = z.read(n).decode("utf-8", "replace")
            parts = []
            for chunk in re.split(r"(?s)(<a:tbl>.*?</a:tbl>)", xml):
                if chunk.startswith("<a:tbl>"):
                    parts.append(_md_table([_cells(r, "a:tc") for r in re.findall(r"(?s)<a:tr[ >].*?</a:tr>", chunk)]))
                    continue
                for para in re.findall(r"(?s)<a:p>.*?</a:p>", chunk):
                    text = html_lib.unescape("".join(re.findall(r"(?s)<a:t>(.*?)</a:t>", para))).strip()
                    if text:
                        parts.append(f"- {text}")
            title = parts[0][2:] if parts and parts[0].startswith("- ") else ""
            out.append(f"## Slide {number}{': ' + title if title else ''}\n" + "\n".join(parts[1:] if title else parts))
            notes = f"ppt/notesSlides/notesSlide{number}.xml"
            if notes in names:
                note = " ".join(html_lib.unescape(t) for t in re.findall(r"(?s)<a:t>(.*?)</a:t>", z.read(notes).decode("utf-8", "replace")))
                note = re.sub(r"\s+", " ", note).strip()
                if note and not note.isdigit():
                    out.append(f"*Speaker notes:* {note}")
    return "\n\n".join(out).strip() + "\n"


def _spreadsheet(path: Path, max_sheets: int = 6, rows: int = 15) -> str:
    """A table as a model reads it best: per sheet, its size, columns and types, the first rows, numeric statistics."""
    import pandas as pd

    ext = path.suffix.lower()
    if ext in (".csv", ".tsv"):
        frames = {path.name: pd.read_csv(path, sep="\t" if ext == ".tsv" else None, engine="python", on_bad_lines="skip")}
    else:
        book = pd.ExcelFile(path)
        frames = {s: book.parse(s) for s in book.sheet_names[:max_sheets]}
        if len(book.sheet_names) > max_sheets:
            frames[f"(+{len(book.sheet_names) - max_sheets} more sheets not shown)"] = pd.DataFrame()
    out = []
    for sheet, df in frames.items():
        if df.empty and not len(df.columns):
            out.append(f"## {sheet}\n(empty)")
            continue
        cols = "\n".join(f"- `{c}` ({t}, {int(df[c].isna().sum())} empty)" for c, t in list(df.dtypes.items())[:80])
        head = _md_table([[str(c) for c in df.columns]] + [["" if (isinstance(v, float) and v != v) else str(v)[:60] for v in r]
                                                           for r in df.head(rows).itertuples(index=False, name=None)])
        stats = ""
        numeric = df.select_dtypes("number")
        if not numeric.empty:
            d = numeric.describe().T.round(4)
            stats = "\n\n**Numeric summary**\n\n" + _md_table([["column"] + [str(c) for c in d.columns]]
                                                               + [[str(i)] + [f"{v:g}" for v in row] for i, row in d.iterrows()])
        out.append(f"## {sheet}\n{df.shape[0]} rows x {df.shape[1]} columns\n\n**Columns**\n{cols}\n\n"
                   f"**First {min(rows, len(df))} rows**\n\n{head}{stats}")
    return "\n\n".join(out).strip() + "\n"


def _image_text(path: Path) -> str:
    """Exact text in an image (on-device OCR), cached; what the image shows is described per question by the vision model."""
    hit = cached(path)
    if hit is not None:
        return hit
    try:
        from living_assistant.vision import ocr

        lines = ocr.ocr_lines(path.read_bytes()) if ocr.available() else []
    except Exception:
        lines = []
    md = ("## Text in the image (OCR)\n\n" + "\n".join(lines) + "\n") if lines else "(no text found in the image)\n"
    try:
        cache_path(path).write_text(md, encoding="utf-8")
    except OSError:
        pass
    return md
