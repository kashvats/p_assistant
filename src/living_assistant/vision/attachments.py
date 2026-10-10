"""Images the user attaches to a conversation (pastes, uploads, screen captures).

Stored once under the data directory, named by content hash, so a follow-up
question ("what does the red box say?") can look at the same image again.
"""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from living_assistant.core.config import data_dir

MAX_BYTES = 20 * 2**20
_ID = re.compile(r"^img_[0-9a-f]{16}$")


def root() -> Path:
    path = data_dir() / "attachments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(data: bytes, name: str = "") -> dict:
    """Validate and store an image; returns its id and size. Raises ValueError for non-images."""
    from PIL import Image, UnidentifiedImageError

    if not data:
        raise ValueError("The image is empty.")
    if len(data) > MAX_BYTES:
        raise ValueError(f"The image is larger than {MAX_BYTES // 2**20} MB.")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        width, height = img.size
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("That file is not an image the assistant can read.") from exc
    image_id = "img_" + hashlib.sha256(data).hexdigest()[:16]
    ext = (img.format or "png").lower().replace("jpeg", "jpg")
    target = root() / f"{image_id}.{ext}"
    if not target.exists():
        target.write_bytes(data)
    return {"id": image_id, "name": str(name or target.name)[:200], "width": width, "height": height,
            "bytes": len(data), "format": ext}


def path_of(image_id: str) -> Path | None:
    if not _ID.match(str(image_id or "")):
        return None
    matches = sorted(root().glob(f"{image_id}.*"))
    return matches[0] if matches else None


def load(image_id: str) -> bytes:
    path = path_of(image_id)
    if path is None:
        raise KeyError(f"No attached image {image_id!r}.")
    return path.read_bytes()


def read_ref(ref: str, workspace) -> bytes:
    """An attached image id (img_…) or an image file inside the workspace."""
    ref = str(ref or "").strip()
    if ref.startswith("img_"):
        return load(ref)
    path = workspace.resolve(ref)
    if not path.is_file():
        raise FileNotFoundError(f"No image at {ref}.")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"The image is larger than {MAX_BYTES // 2**20} MB.")
    return path.read_bytes()
