from __future__ import annotations

import re
import time
from pathlib import Path

from living_assistant.core.config import project_root
from living_assistant.core.workspace import Workspace
from living_assistant.integrations.openmontage import OpenMontageAdapter
from living_assistant.security.security_utils import redact_secrets, url_network_scope

from .base import Tool

_FORMATS = {"video", "audio_only", "subtitles_only", "metadata_only"}
_RESOLUTIONS = {"360p", "480p", "720p", "1080p"}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:48] or "video"


def build_media_tools(workspace: Workspace, config: dict) -> list[Tool]:
    mcfg = config.get("media", {}) or {}
    downloader = OpenMontageAdapter(
        path=mcfg.get("openmontage_path") or project_root() / "external-components" / "openmontage",
    )
    timeout = float(mcfg.get("video_download_timeout_seconds", 900))

    def download_video(
        url: str,
        format: str = "video",
        max_resolution: str = "720p",
        max_duration_seconds: int = 1800,
        destination: str = "downloads/videos",
    ):
        url = str(url or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            return {"ok": False, "error": "Only http/https video URLs are supported."}
        scope, _ = url_network_scope(url, resolve=False)
        if scope != "public":
            return {"ok": False, "error": "Video downloads are limited to public internet hosts."}
        if format not in _FORMATS:
            return {"ok": False, "error": f"format must be one of {sorted(_FORMATS)}"}
        if max_resolution not in _RESOLUTIONS:
            return {"ok": False, "error": f"max_resolution must be one of {sorted(_RESOLUTIONS)}"}

        folder = workspace.resolve(Path(destination) / f"{time.strftime('%Y%m%d-%H%M%S')}-{_slug(url.split('//', 1)[-1])}")
        folder.mkdir(parents=True, exist_ok=True)
        result = downloader.download_video(
            url,
            str(folder),
            fmt=format,
            max_resolution=max_resolution,
            max_duration_seconds=max(1, min(int(max_duration_seconds), 6 * 3600)),
            timeout=timeout,
        )
        if not result.get("ok"):
            try:
                folder.rmdir()
            except OSError:
                pass
            return {"ok": False, "error": redact_secrets(str(result.get("error") or "Download failed."), 2000)}

        data = result.get("data") or {}
        meta = data.get("metadata") or {}
        title = str(meta.get("title") or "")
        labelled: dict[str, str] = {}
        for key, label in (("video_path", "video_with_audio"), ("audio_path", "audio_track"), ("subtitle_path", "subtitles")):
            if not data.get(key):
                continue
            src = Path(data[key])
            target = src.with_name(f"{_slug(title) if title else src.stem}{src.suffix}")
            if src.exists() and not target.exists():
                src.rename(target)
                src = target
            labelled[label] = str(src)
        renamed = list(labelled.values())
        if not renamed:
            try:
                folder.rmdir()
            except OSError:
                pass
        return {
            "ok": True,
            "platform": data.get("platform"),
            "title": title,
            "duration_seconds": meta.get("duration"),
            "uploader": meta.get("uploader"),
            "files": labelled,
            "note": "video_with_audio is the complete playable file; audio_track is a separately extracted WAV copy of its sound." if "video_with_audio" in labelled else None,
            "folder": str(folder) if renamed else None,
        }

    return [
        Tool(
            "download_video",
            (
                "Download a video, its audio, or its subtitles from YouTube, Shorts, Instagram, TikTok, Vimeo, "
                "X/Twitter and 1000+ other sites (universal video downloader, yt-dlp). "
                "Use metadata_only to look up a video's title/length without downloading."
            ),
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Video page URL, e.g. a YouTube link."},
                    "format": {"type": "string", "enum": sorted(_FORMATS), "default": "video"},
                    "max_resolution": {"type": "string", "enum": sorted(_RESOLUTIONS), "default": "720p"},
                    "max_duration_seconds": {"type": "integer", "default": 1800},
                    "destination": {"type": "string", "default": "downloads/videos"},
                },
                "required": ["url"],
            },
            download_video,
        ),
    ]
