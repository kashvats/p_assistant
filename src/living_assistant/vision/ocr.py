"""Fast on-device OCR (RapidOCR): exact characters, ordered top-to-bottom, left-to-right."""
from __future__ import annotations

import io
import threading

_ENGINE = None
_LOCK = threading.Lock()


def available() -> bool:
    try:
        import rapidocr  # noqa: F401
        return True
    except ImportError:
        return False


def ocr_lines(image: bytes, min_score: float = 0.5, max_lines: int = 400) -> list[str]:
    global _ENGINE
    from PIL import Image
    from rapidocr import RapidOCR

    with _LOCK:
        if _ENGINE is None:
            _ENGINE = RapidOCR()
        img = Image.open(io.BytesIO(image)).convert("RGB")
        result = _ENGINE(img)
    rows = []
    for box, text, score in zip(result.boxes if result.boxes is not None else [], result.txts or (), result.scores or ()):
        if score >= min_score and str(text).strip():
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            rows.append((min(ys), min(xs), max(ys) - min(ys), str(text).strip()))
    # Group into lines: boxes whose tops are within half a text height are on the same line.
    rows.sort()
    lines: list[list[tuple]] = []
    for row in rows:
        if lines and abs(row[0] - lines[-1][0][0]) < max(6.0, row[2] * 0.5):
            lines[-1].append(row)
        else:
            lines.append([row])
    return [" ".join(r[3] for r in sorted(line, key=lambda r: r[1])) for line in lines][:max_lines]
