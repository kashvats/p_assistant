from __future__ import annotations

from hashlib import blake2b
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from living_assistant.security.security_policy import sanitize_external_observation
from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger("living_assistant.system.article_extractor")


class ArticleExtractor:
    """Robust web article and documentation text extractor powered by Trafilatura with metadata extraction,

    boilerplate removal, and disk caching.
    """

    def __init__(self, cache_ttl_seconds: float = 86400.0) -> None:
        self.cache_ttl = cache_ttl_seconds

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        include_comments: bool = False,
        output_format: str = "txt",
        max_text_chars: int = 120_000,
    ) -> dict[str, Any]:
        """Extract clean text, headline, author, date, and metadata from raw HTML content."""
        if not html_content or not html_content.strip():
            return {
                "ok": False,
                "error": "HTML content must not be empty.",
                "title": None,
                "text": "",
                "metadata": {},
            }

        # Check disk cache if available
        cache_key = None
        disk_cache = None
        try:
            from living_assistant.system.disk_cache import get_disk_cache
            disk_cache = get_disk_cache()
            digest = blake2b(html_content.encode("utf-8", errors="ignore"), digest_size=16).hexdigest()
            cache_key = f"article:{output_format}:{int(include_comments)}:{digest}"
            cached_res = disk_cache.get("doc_parsing", cache_key)
            if cached_res is not None and isinstance(cached_res, dict) and cached_res.get("ok"):
                return cached_res
        except Exception:
            disk_cache = None

        try:
            import trafilatura
            # Extract main text body
            extracted_text = trafilatura.extract(
                html_content,
                url=url,
                output_format=output_format,
                include_comments=include_comments,
                include_tables=True,
                include_links=True,
                favor_recall=True,
            )

            # Extract rich metadata
            meta = trafilatura.extract_metadata(html_content, default_url=url)
            meta_dict = {}
            if meta:
                meta_dict = {
                    "title": meta.title,
                    "author": meta.author,
                    "date": meta.date,
                    "description": meta.description,
                    "sitename": meta.sitename,
                    "url": meta.url or url,
                    "categories": meta.categories or [],
                    "tags": meta.tags or [],
                    "license": meta.license,
                }
        except Exception as exc:
            logger.warning("Trafilatura extraction failed, attempting fallback: %s", redact_secrets(exc))
            extracted_text = None
            meta_dict = {}

        # Fallback if trafilatura returned empty (e.g. non-article page or plain HTML)
        if not extracted_text or not extracted_text.strip():
            extracted_text = self._fallback_html_strip(html_content)

        # Sanitize untrusted web content for LLM safety
        sanitized_text = sanitize_external_observation(extracted_text, max_chars=max_text_chars)
        title = meta_dict.get("title") or self._extract_title_tag(html_content)

        word_count = len(extracted_text.split()) if extracted_text else 0
        result = {
            "ok": True,
            "title": title,
            "text": sanitized_text,
            "metadata": meta_dict,
            "word_count": word_count,
            "url": url,
        }

        if disk_cache is not None and cache_key is not None:
            try:
                disk_cache.set("doc_parsing", cache_key, result, expire=self.cache_ttl)
            except Exception:
                pass

        return result

    @staticmethod
    def _extract_title_tag(html: str) -> str | None:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            clean = re.sub(r"\s+", " ", match.group(1)).strip()
            return clean[:200] if clean else None
        return None

    @staticmethod
    def _fallback_html_strip(html: str) -> str:
        # Strip script and style blocks
        text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Unescape basic entities and normalize whitespace
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


_GLOBAL_EXTRACTOR: ArticleExtractor | None = None


def get_article_extractor() -> ArticleExtractor:
    """Singleton getter for ArticleExtractor."""
    global _GLOBAL_EXTRACTOR
    if _GLOBAL_EXTRACTOR is None:
        _GLOBAL_EXTRACTOR = ArticleExtractor()
    return _GLOBAL_EXTRACTOR
