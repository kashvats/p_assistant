"""Vision models the assistant can run locally with llama.cpp (a model file + its image projector).

Nothing is tied to one model: the catalog lists tested candidates, and config can
add any other llama.cpp-compatible vision model (``vision.models`` in the config).
Files are downloaded from Hugging Face on first use, resumed if interrupted, and
checked against the SHA-256 Hugging Face publishes before they are used.

``mode`` says how a model shares the machine with the chat model:
    alongside  small enough to run next to the chat model (default: on the CPU)
    swap       needs the chat model paused while it runs (bigger, more capable)
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

import httpx

from living_assistant.core.config import data_dir

HF = "https://huggingface.co"


@dataclass(frozen=True)
class VisionModel:
    name: str
    repo: str
    file: str
    mmproj: str
    mode: str = "alongside"          # alongside | swap
    device: str = "cpu"              # cpu | gpu | auto
    context: int = 4096
    notes: str = ""
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    jinja: bool = True               # use the model's own chat template (False: pass --chat-template in extra_args)

    @property
    def folder(self) -> Path:
        return data_dir() / "models" / "vision" / self.repo.replace("/", "__")

    @property
    def model_path(self) -> Path:
        return self.folder / self.file

    @property
    def mmproj_path(self) -> Path:
        return self.folder / self.mmproj

    def downloaded(self) -> bool:
        return self.model_path.is_file() and self.mmproj_path.is_file()


CATALOG: dict[str, VisionModel] = {m.name: m for m in (
    VisionModel("qwen3-vl-2b", "Qwen/Qwen3-VL-2B-Instruct-GGUF", "Qwen3VL-2B-Instruct-Q4_K_M.gguf",
                "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf", notes="Qwen3-VL 2B, 4-bit"),
    VisionModel("qwen3-vl-4b", "Qwen/Qwen3-VL-4B-Instruct-GGUF", "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
                "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf", mode="swap", device="auto", notes="Qwen3-VL 4B, 4-bit"),
    VisionModel("qwen3-vl-8b", "Qwen/Qwen3-VL-8B-Instruct-GGUF", "Qwen3VL-8B-Instruct-Q4_K_M.gguf",
                "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf", mode="swap", device="auto", notes="Qwen3-VL 8B, 4-bit"),
    VisionModel("moondream2", "ggml-org/moondream2-20250414-GGUF", "moondream2-text-model-f16_ct-vicuna.gguf",
                "moondream2-mmproj-f16-20250414.gguf", context=2048,
                notes="Moondream2 (2025-04-14), f16. llama.cpp b11193 rejects its images (mtmd finds no media marker)."),
    VisionModel("smolvlm2-2.2b", "ggml-org/SmolVLM2-2.2B-Instruct-GGUF", "SmolVLM2-2.2B-Instruct-Q4_K_M.gguf",
                "mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf", notes="SmolVLM2 2.2B, 4-bit"),
    VisionModel("lfm2.5-vl-1.6b", "LiquidAI/LFM2.5-VL-1.6B-GGUF", "LFM2.5-VL-1.6B-Q4_K_M.gguf",
                "mmproj-LFM2.5-VL-1.6b-Q8_0.gguf", notes="Liquid LFM2.5-VL 1.6B, 4-bit"),
    VisionModel("internvl3.5-2b", "bartowski/OpenGVLab_InternVL3_5-2B-GGUF", "OpenGVLab_InternVL3_5-2B-Q4_K_M.gguf",
                "mmproj-OpenGVLab_InternVL3_5-2B-f16.gguf", notes="InternVL3.5 2B, 4-bit"),
)}


def catalog(config: dict | None = None) -> dict[str, VisionModel]:
    """Built-in candidates plus/overridden by ``vision.models`` from config."""
    models = dict(CATALOG)
    for name, spec in ((config or {}).get("models") or {}).items():
        base = models.get(name)
        fields = {k: v for k, v in (spec or {}).items() if k in VisionModel.__dataclass_fields__}
        if "extra_args" in fields:
            fields["extra_args"] = tuple(fields["extra_args"])
        if base is not None:
            models[name] = replace(base, **fields)
        elif {"repo", "file", "mmproj"} <= set(fields):
            models[name] = VisionModel(name=name, **fields)
    return models


def _expected_sha256(client: httpx.Client, repo: str, filename: str) -> str | None:
    try:
        tree = client.get(f"{HF}/api/models/{repo}/tree/main", timeout=30).json()
    except Exception:
        return None
    for item in tree if isinstance(tree, list) else []:
        if item.get("path") == filename:
            return ((item.get("lfs") or {}).get("oid")) or None
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(model: VisionModel, progress: Callable[[str, int, int], None] | None = None) -> VisionModel:
    """Fetch the model and projector if missing (resumable, SHA-256 verified)."""
    model.folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, headers={"User-Agent": "LivingAssistant"}, trust_env=True) as client:
        for filename in (model.file, model.mmproj):
            target = model.folder / filename
            if target.is_file():
                continue
            part = target.with_suffix(target.suffix + ".part")
            expected = _expected_sha256(client, model.repo, filename)
            done = part.stat().st_size if part.exists() else 0
            headers = {"Range": f"bytes={done}-"} if done else {}
            with client.stream("GET", f"{HF}/{model.repo}/resolve/main/{filename}", headers=headers, timeout=60) as r:
                if r.status_code == 416:  # already complete
                    pass
                else:
                    r.raise_for_status()
                    if done and r.status_code != 206:
                        done = 0  # server ignored the range; start over
                    total = done + int(r.headers.get("content-length") or 0)
                    with part.open("ab" if done else "wb") as fh:
                        for chunk in r.iter_bytes(1 << 20):
                            fh.write(chunk)
                            done += len(chunk)
                            if progress:
                                progress(filename, done, total)
            if expected and _sha256(part) != expected:
                part.unlink(missing_ok=True)
                raise RuntimeError(f"Checksum mismatch for {model.repo}/{filename}; the download was discarded.")
            os.replace(part, target)
    return model
