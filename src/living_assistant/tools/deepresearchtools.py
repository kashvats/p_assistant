"""Long-form, cited research reports with GPT Researcher on the local model.

GPT Researcher plans sub-questions, researches each one, and writes a report with
citations. Here it runs on the assistant's own model endpoint with local
embeddings, and it gets its sources only through the assistant's search and page
reader: every researcher, including the nested ones deep mode creates, uses
``LivingAssistantRetriever``, which returns already-read pages. GPT Researcher
therefore never fetches pages itself, and the same network gates, search budget
and untrusted-content handling apply as everywhere else in the assistant.

Every page the retriever hands to GPT Researcher is also captured, so a research
run can be stored as evidence in a research project (see living_assistant.research).
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse

from .base import Tool
from .researchtools import _LOW_VALUE_HOSTS, _clean
from living_assistant.core.config import data_dir
from living_assistant.core.workspace import Workspace
from living_assistant.security.security_utils import redact_secrets

REPORT_TYPES = {"quick": None, "standard": "research_report", "detailed": "detailed_report", "deep": "deep"}
_RUN_LOCK = threading.Lock()  # one report at a time: the local model serves one request at a time anyway
# Pages read during the current research run (the list is shared by nested researchers and their threads).
_CAPTURE: contextvars.ContextVar[list | None] = contextvars.ContextVar("research_capture", default=None)


def make_retriever(search: Callable, extract: Callable, max_page_chars: int = 12000) -> type:
    """A GPT Researcher retriever backed by the assistant's web_search and page reader."""

    class LivingAssistantRetriever:
        requires_scraping = False  # results carry the page text already

        def __init__(self, query: str, query_domains: list[str] | None = None, **_kwargs):
            self.query = str(query or "")
            self.query_domains = list(query_domains or [])

        def search(self, max_results: int = 5) -> list[dict]:
            query = self.query
            if self.query_domains:
                query += " " + " OR ".join(f"site:{d}" for d in self.query_domains[:5])
            found = search(query, num=min(8, max(3, int(max_results) + 3)))
            if not isinstance(found, dict) or not found.get("ok"):
                return []
            picked, hosts = [], set()
            for item in found.get("results") or []:
                url = str(item.get("link") or item.get("url") or "")
                host = (urlparse(url).hostname or "").lower()
                if not url.startswith(("http://", "https://")) or host in hosts or any(b in host for b in _LOW_VALUE_HOSTS):
                    continue
                hosts.add(host)
                picked.append((url, _clean(str(item.get("title") or "")), _clean(str(item.get("snippet") or ""))))

            def read(entry):
                url, title, snippet = entry
                page = extract(url)
                if not isinstance(page, dict) or not page.get("ok"):
                    return None
                text = _clean(str(page.get("text") or ""))
                if len(text) < 200:
                    return None
                meta = page.get("metadata") or {}
                return {"href": str(page.get("url") or url), "url": str(page.get("url") or url),
                        "title": _clean(str(page.get("title") or title))[:200], "body": snippet,
                        "raw_content": text[:max_page_chars], "published": meta.get("date"), "query": self.query}

            with ThreadPoolExecutor(max_workers=4) as pool:
                pages = [p for p in pool.map(read, picked[: int(max_results) + 2]) if p]
            pages = pages[: int(max_results)]
            captured = _CAPTURE.get()
            if captured is not None:
                captured.extend(pages)
            return pages

    return LivingAssistantRetriever


def install_retriever(retriever: type) -> None:
    """Make every GPTResearcher (including nested deep-research ones) use ``retriever``."""
    import gpt_researcher.agent as agent

    if not hasattr(agent, "get_retrievers"):
        raise RuntimeError("gpt_researcher.agent.get_retrievers is missing; the retriever hook needs updating.")
    agent.get_retrievers = lambda headers, cfg: [retriever]


def _run_async(factory: Callable[[], Any]) -> Any:
    box: dict[str, Any] = {}
    ctx = contextvars.copy_context()  # carry the capture list into the research thread

    def target():
        loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            box["value"] = loop.run_until_complete(factory())
        except BaseException as exc:
            box["error"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=lambda: ctx.run(target), name="gpt-researcher", daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def researcher_config(base_url: str, model: str, api_key: str, context_tokens: int, embedding_model: str) -> dict:
    """GPT Researcher settings sized for one local model with a limited context window."""
    reply_tokens = max(1024, min(4000, context_tokens // 4))
    return {
        "RETRIEVER": "duckduckgo",  # never used: install_retriever replaces the retriever lookup
        "FAST_LLM": f"openai:{model}",
        "SMART_LLM": f"openai:{model}",
        "STRATEGIC_LLM": f"openai:{model}",
        "LLM_KWARGS": {"openai_api_base": base_url, "openai_api_key": api_key},
        "EMBEDDING": f"huggingface:{embedding_model}",
        "EMBEDDING_KWARGS": {"model_kwargs": {"device": "cpu"}},
        "FAST_TOKEN_LIMIT": min(2000, reply_tokens),
        "SMART_TOKEN_LIMIT": reply_tokens,
        "STRATEGIC_TOKEN_LIMIT": min(3000, reply_tokens),
        "SUMMARY_TOKEN_LIMIT": 600,
        "BROWSE_CHUNK_MAX_LENGTH": 4000,
        "MAX_SEARCH_RESULTS_PER_QUERY": 3,
        "MAX_ITERATIONS": 3,
        "MAX_SUBTOPICS": 3,
        "TOTAL_WORDS": 1000,
        "TEMPERATURE": 0.3,
        "CURATE_SOURCES": False,
        "DEEP_RESEARCH_BREADTH": 3,
        "DEEP_RESEARCH_DEPTH": 2,
        "DEEP_RESEARCH_CONCURRENCY": 1,
        "MAX_SCRAPER_WORKERS": 4,
        "MCP_STRATEGY": "disabled",
        "IMAGE_GENERATION_ENABLED": False,
        "VERBOSE": False,
    }


def make_research_runner(search: Callable, extract: Callable, gate: Callable, base_url: str, model: str,
                         api_key: str = "sk-local", context_tokens: int = 16384,
                         embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2") -> Callable[..., dict]:
    """``run(question, depth, source_urls)`` -> {report, sources, pages}. Pages are what was actually read."""
    retriever = make_retriever(search, extract)
    install_retriever(retriever)
    config = researcher_config(base_url, model, api_key, context_tokens, embedding_model)

    def run(question: str, depth: str = "standard", source_urls: list | None = None) -> dict:
        question = str(question or "").strip()
        if not question:
            return {"ok": False, "error": "A research question is required."}
        depth = str(depth or "standard").lower()
        if depth not in REPORT_TYPES:
            return {"ok": False, "error": f"depth must be one of {sorted(REPORT_TYPES)}."}
        sources = [str(u) for u in (source_urls or []) if str(u).startswith(("http://", "https://"))]
        for url in sources:  # GPT Researcher reads these itself, so they pass the gate first
            blocked = gate(url, "Research")
            if blocked:
                return blocked
        started = time.monotonic()
        if REPORT_TYPES[depth] is None:  # quick: read sources, no report writing
            pages = retriever(question).search(max_results=5)
            return {"ok": bool(pages), "question": question, "depth": depth, "report": "", "pages": pages,
                    "sources": [p["url"] for p in pages], "minutes": round((time.monotonic() - started) / 60, 1),
                    **({} if pages else {"error": "No readable sources found."})}
        cfg_path = data_dir() / "gpt_researcher.json"
        cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        captured: list = []

        async def go():
            from gpt_researcher import GPTResearcher

            researcher = GPTResearcher(query=question, report_type=REPORT_TYPES[depth], config_path=str(cfg_path),
                                       verbose=False, source_urls=sources or None, complement_source_urls=bool(sources))
            await researcher.conduct_research()
            report = await researcher.write_report()
            return report, list(dict.fromkeys(researcher.get_source_urls()))

        if not _RUN_LOCK.acquire(blocking=False):
            return {"ok": False, "busy": True, "error": "Another research report is being written; try again when it finishes."}
        token = _CAPTURE.set(captured)
        try:
            report, urls = _run_async(go)
        except Exception as exc:
            return {"ok": False, "error": f"Research failed: {redact_secrets(exc, 800)}", "pages": captured}
        finally:
            _CAPTURE.reset(token)
            _RUN_LOCK.release()
        seen, pages = set(), []
        for p in captured:
            if p["url"] not in seen:
                seen.add(p["url"])
                pages.append(p)
        report = str(report or "").strip()
        return {"ok": bool(report), "question": question, "depth": depth, "report": report, "sources": urls, "pages": pages,
                "minutes": round((time.monotonic() - started) / 60, 1),
                **({} if report else {"error": "The researcher returned an empty report."})}

    return run


def build_deep_research_tools(workspace: Workspace, search: Callable, extract: Callable, gate: Callable,
                              base_url: str, model: str, api_key: str = "sk-local", context_tokens: int = 16384,
                              embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
                              ingest: Callable[[str, dict], dict] | None = None,
                              runner: Callable[..., dict] | None = None) -> list[Tool]:
    """``ingest(project, result)`` stores a run's pages as evidence in a research project, when given."""
    run = runner or make_research_runner(search, extract, gate, base_url, model, api_key, context_tokens, embedding_model)

    def deep_research(question: str, depth: str = "standard", source_urls: list | None = None, output: str = "",
                      project: str = ""):
        result = run(question, depth, source_urls)
        stored = None
        if project and ingest is not None and result.get("pages"):
            try:
                stored = ingest(project, result)
            except Exception as exc:
                stored = {"ok": False, "error": redact_secrets(exc, 400)}
        if not result.get("ok"):
            return {**{k: v for k, v in result.items() if k != "pages"}, **({"project_knowledge": stored} if stored else {})}
        report = result["report"]
        report_file = None
        if report:
            slug = re.sub(r"[^a-z0-9]+", "-", result["question"].lower()).strip("-")[:60] or "report"
            try:
                target = workspace.resolve(output or f"research/{datetime.now():%Y%m%d-%H%M}-{slug}.md")
            except Exception as exc:
                return {"ok": False, "error": redact_secrets(exc, 300)}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(report + "\n", encoding="utf-8")
            report_file = str(target)
        return {
            "ok": True,
            "question": result["question"],
            "depth": result["depth"],
            "report_file": report_file,
            "sources": result["sources"][:40],
            "pages_read": len(result["pages"]),
            "minutes": result["minutes"],
            "report": report[:12000] + ("\n\n[... truncated; full report in report_file]" if len(report) > 12000 else ""),
            **({"project_knowledge": stored} if stored else {}),
            "instructions": "Summarize the key findings for the user with their citations and give the report_file path.",
        }

    return [
        Tool(
            "deep_research",
            "Write a long, cited research report on a topic: plans sub-questions, searches and reads many sources, "
            "and writes a structured markdown report saved to the workspace. Takes several minutes. Use for reports, "
            "literature/market/competitor reviews and 'research X in depth'; for a quick fact use web_research. "
            "Pass `project` to also store every source read as evidence in that research project.",
            {"type": "object", "properties": {
                "question": {"type": "string", "description": "The research topic or question."},
                "depth": {"type": "string", "enum": sorted(REPORT_TYPES), "default": "standard",
                          "description": "quick (read sources, no report), standard (~1000 words), detailed, deep (recursive, slowest)."},
                "source_urls": {"type": "array", "items": {"type": "string"}, "description": "Pages that must be used as sources."},
                "output": {"type": "string", "description": "Markdown file to save the report to (default research/<date>-<topic>.md)."},
                "project": {"type": "string", "description": "Research project to store the evidence in (name or id)."},
            }, "required": ["question"]},
            deep_research,
        )
    ]
