from __future__ import annotations

import inspect
import json
import math
import re
import time
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from living_assistant.agents.agents import SpecialistRouter
from living_assistant.agents.prompts import ORCHESTRATOR
from living_assistant.core.model_provider import ModelManager
from living_assistant.core.skills import SkillRegistry
from living_assistant.security.security_utils import redact_secrets
from living_assistant.system.resource_manager import ResourceManager
from living_assistant.tools.base import Tool
from living_assistant.core.typesafe import JevClient


# Keep the tool surface small enough for compact local orchestrator models while
# still allowing progressive discovery during a run.
INITIAL_TOOL_LIMIT = 8
MAX_ACTIVE_TOOLS = 16
DISCOVERY_DEFAULT_LIMIT = 6
DISCOVERY_MAX_LIMIT = 12
FOLLOWUP_TOOL_LIMIT = 4
MAX_TOOL_RESULT_CHARS = 60_000
ROUTING_RESULT_CHARS = 8_000

# Internal tool name reserved by the orchestrator. It lets the model query the
# complete registered tool catalog if the initial retrieval missed a capability.
TOOL_DISCOVERY_NAME = "tool_catalog_search"


@dataclass(frozen=True)
class _ToolDocument:
    name: str
    description: str
    schema: dict[str, Any]
    name_terms: frozenset[str]
    terms: Counter[str]
    length: int
    searchable_text: str


class DynamicToolRouter:
    """Rank registered tools from their own metadata.

    The router intentionally has no request-specific phrase rules. It derives its
    searchable corpus from each tool's name, description, and JSON schema, then
    uses a lightweight BM25-style ranker plus typo-tolerant fuzzy matching.

    This keeps routing deterministic, fast, dependency-free, and compatible with
    small local models. The orchestrator can progressively expand the active tool
    set after each tool result or through the catalog-search tool.
    """

    _TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
    _CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

    def __init__(self, tools: dict[str, Tool]):
        self._tools = tools
        self._documents: dict[str, _ToolDocument] = {}
        self._idf: dict[str, float] = {}
        self._avg_length = 1.0
        self._catalog_signature: tuple[tuple[str, str], ...] = ()
        self.refresh(force=True)

    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        text = cls._CAMEL_RE.sub(" ", text)
        text = text.replace("_", " ").replace("-", " ")
        return " ".join(text.lower().split())

    @classmethod
    def _term_variants(cls, term: str) -> list[str]:
        """Return conservative generic morphology variants.

        The original token is always retained. Variants improve matching for
        ordinary plural/verb forms without encoding capability-specific aliases.
        """

        term = term.lower()
        variants = [term]

        if len(term) > 5 and term.endswith("ies"):
            variants.append(term[:-3] + "y")
        elif len(term) > 4 and term.endswith(("ches", "shes", "xes", "zes")):
            variants.append(term[:-2])
        elif len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
            variants.append(term[:-1])

        if len(term) > 5 and term.endswith("ing"):
            base = term[:-3]
            if len(base) >= 3:
                if len(base) >= 2 and base[-1] == base[-2]:
                    base = base[:-1]
                variants.append(base)
                variants.append(base + "e")

        if len(term) > 4 and term.endswith("ed"):
            base = term[:-2]
            variants.append(base)
            variants.append(base + "e")

        return list(dict.fromkeys(v for v in variants if len(v) >= 2))

    @classmethod
    def _tokenize(cls, value: Any) -> list[str]:
        normalized = cls._normalize_text(value)
        terms: list[str] = []
        for token in cls._TOKEN_RE.findall(normalized):
            if len(token) < 2:
                continue
            terms.extend(cls._term_variants(token))
        return terms

    @classmethod
    def _flatten_schema(cls, value: Any, depth: int = 0) -> list[str]:
        if depth > 8:
            return []
        if isinstance(value, dict):
            parts: list[str] = []
            for key, item in value.items():
                parts.append(str(key))
                parts.extend(cls._flatten_schema(item, depth + 1))
            return parts
        if isinstance(value, (list, tuple, set)):
            parts = []
            for item in value:
                parts.extend(cls._flatten_schema(item, depth + 1))
            return parts
        if value is None:
            return []
        return [str(value)]

    @staticmethod
    def _safe_schema(tool: Tool) -> dict[str, Any]:
        try:
            schema = tool.ollama_schema()
            return schema if isinstance(schema, dict) else {}
        except Exception:
            return {}

    def _signature(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (
                    name,
                    str(getattr(tool, "description", "") or ""),
                )
                for name, tool in self._tools.items()
                if name != TOOL_DISCOVERY_NAME
            )
        )

    def refresh(self, force: bool = False) -> None:
        signature = self._signature()
        if not force and signature == self._catalog_signature:
            return

        documents: dict[str, _ToolDocument] = {}
        document_frequency: Counter[str] = Counter()

        for name, tool in self._tools.items():
            if name == TOOL_DISCOVERY_NAME:
                continue

            description = str(getattr(tool, "description", "") or "")
            schema = self._safe_schema(tool)

            name_tokens = self._tokenize(name)
            description_tokens = self._tokenize(description)
            schema_tokens = self._tokenize(" ".join(self._flatten_schema(schema)))

            # Field weighting is encoded as repeated generic terms, not as
            # capability-specific rules. Names carry the strongest signal.
            weighted_terms = (
                name_tokens * 4
                + description_tokens * 2
                + schema_tokens
            )
            term_counts = Counter(weighted_terms)
            searchable_text = self._normalize_text(
                f"{name} {description} {' '.join(self._flatten_schema(schema))}"
            )

            doc = _ToolDocument(
                name=name,
                description=description,
                schema=schema,
                name_terms=frozenset(name_tokens),
                terms=term_counts,
                length=max(1, sum(term_counts.values())),
                searchable_text=searchable_text,
            )
            documents[name] = doc
            document_frequency.update(set(term_counts))

        document_count = max(1, len(documents))
        avg_length = (
            sum(doc.length for doc in documents.values()) / document_count
            if documents
            else 1.0
        )

        idf: dict[str, float] = {}
        for term, df in document_frequency.items():
            # BM25 IDF with +1 to keep values positive for common terms.
            idf[term] = math.log(
                1.0 + (document_count - df + 0.5) / (df + 0.5)
            )

        self._documents = documents
        self._idf = idf
        self._avg_length = max(1.0, avg_length)
        self._catalog_signature = signature

    @staticmethod
    def _char_ngrams(text: str, n: int = 3) -> set[str]:
        compact = re.sub(r"\s+", " ", text.strip().lower())
        if len(compact) < n:
            return {compact} if compact else set()
        return {compact[i : i + n] for i in range(len(compact) - n + 1)}

    def _fuzzy_score(self, query_text: str, document: _ToolDocument) -> float:
        query_text = self._normalize_text(query_text)
        if not query_text or not document.searchable_text:
            return 0.0

        # SequenceMatcher catches misspellings and close name variants.
        name_ratio = SequenceMatcher(
            None,
            query_text[:500],
            self._normalize_text(document.name),
        ).ratio()

        query_grams = self._char_ngrams(query_text[:1000])
        doc_grams = self._char_ngrams(document.searchable_text[:3000])
        if query_grams and doc_grams:
            jaccard = len(query_grams & doc_grams) / max(
                1,
                len(query_grams | doc_grams),
            )
        else:
            jaccard = 0.0

        return (name_ratio * 0.75) + (jaccard * 0.25)

    def search(
        self,
        query: str,
        *,
        limit: int = INITIAL_TOOL_LIMIT,
        exclude: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.refresh()

        exclude_set = set(exclude or ())
        query_terms = self._tokenize(query)
        query_counts = Counter(query_terms)
        query_text = self._normalize_text(query)

        if not self._documents:
            return []

        k1 = 1.5
        b = 0.75
        scored: list[tuple[float, _ToolDocument]] = []

        for name, doc in self._documents.items():
            if name in exclude_set:
                continue

            score = 0.0
            for term, query_tf in query_counts.items():
                tf = doc.terms.get(term, 0)
                if not tf:
                    continue

                idf = self._idf.get(term, 0.0)
                denominator = tf + k1 * (
                    1.0 - b + b * (doc.length / self._avg_length)
                )
                score += (
                    idf
                    * ((tf * (k1 + 1.0)) / max(denominator, 1e-9))
                    * (1.0 + math.log1p(query_tf))
                )

                if term in doc.name_terms:
                    score += idf * 1.5

            lexical_score = score
            fuzzy = self._fuzzy_score(query_text, doc)

            # Fuzzy matching is only a supporting signal. Strong lexical matches
            # dominate. A fuzzy-only match must clear a higher threshold so random
            # unrelated tools are not injected into a small model's context.
            if lexical_score > 0.0:
                score = lexical_score + (fuzzy * 0.35)
            elif fuzzy >= 0.30:
                score = fuzzy * 0.50
            else:
                continue

            scored.append((score, doc))

        scored.sort(key=lambda item: (-item[0], item[1].name))

        safe_limit = max(1, min(int(limit), DISCOVERY_MAX_LIMIT))
        return [
            {
                "name": doc.name,
                "description": doc.description,
                "score": round(score, 5),
            }
            for score, doc in scored[:safe_limit]
        ]


class Orchestrator:
    def __init__(
        self,
        model_manager: ModelManager,
        model: str,
        tools: list[Tool],
        specialist_router: SpecialistRouter,
        keep_alive: int = 45,
        max_steps: int = 10,
        context_tokens: int = 4096,
        skills: SkillRegistry | None = None,
        resource_manager: ResourceManager | None = None,
        session_store=None,
        max_session_messages: int = 24,
        experiences=None,
        event_bus=None,
        run_history=None,
        model_usage=None,
    ):
        self.mm = model_manager
        self.model = model
        self.keep_alive = keep_alive
        self.max_steps = max_steps
        self.context_tokens = context_tokens
        self.specialists = specialist_router
        self.skills = skills
        self.resources = resource_manager
        self.sessions = session_store
        self.max_session_messages = max(2, min(int(max_session_messages), 100))
        self.experiences = experiences
        self.event_bus = event_bus
        self.run_history = run_history
        self.model_usage = model_usage

        self.jev = JevClient()

        duplicate_names = self._duplicate_tool_names(tools)
        if duplicate_names:
            raise ValueError(
                "Duplicate tool names are not allowed: "
                + ", ".join(sorted(duplicate_names))
            )

        self.tools = {tool.name: tool for tool in tools}

        self._register_internal_tool(
            Tool(
                "delegate_agent",
                "Ask a sleeping specialist agent for help when specialist reasoning materially improves the task.",
                {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": [
                                "general",
                                "coder",
                                "researcher",
                                "security",
                                "database",
                                "planner",
                            ],
                        },
                        "task": {"type": "string"},
                        "context": {"type": "string", "default": ""},
                    },
                    "required": ["role", "task"],
                },
                self._delegate,
            )
        )

        # Build the dynamic index after delegate_agent exists so specialist
        # delegation itself can be discovered through normal metadata ranking.
        self.tool_router = DynamicToolRouter(self.tools)

        self._register_internal_tool(
            Tool(
                TOOL_DISCOVERY_NAME,
                (
                    "Search the complete registered tool catalog for capabilities that are not currently exposed. "
                    "Use this before claiming the assistant lacks a required function."
                ),
                {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Describe the capability or next action needed.",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": DISCOVERY_MAX_LIMIT,
                            "default": DISCOVERY_DEFAULT_LIMIT,
                        },
                    },
                    "required": ["query"],
                },
                self._tool_catalog_search,
            )
        )

        # Refresh once more so the router sees the final catalog signature. The
        # discovery tool itself is intentionally excluded from searchable docs.
        self.tool_router.refresh(force=True)

    @staticmethod
    def _duplicate_tool_names(tools: list[Tool]) -> set[str]:
        counts = Counter(tool.name for tool in tools)
        return {name for name, count in counts.items() if count > 1}

    def _register_internal_tool(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(
                f"Tool name {tool.name!r} is reserved by the orchestrator."
            )
        self.tools[tool.name] = tool

    # ---------------------------------------------------------------------
    # Specialist delegation
    # ---------------------------------------------------------------------

    def _delegate(
        self,
        role: str,
        task: str,
        context: str = "",
        _session_id: str | None = None,
        _run_id: str | None = None,
    ):
        delegate = self.specialists.delegate
        try:
            signature = inspect.signature(delegate)
            params = signature.parameters.values()
            accepts_metadata = any(
                param.kind is inspect.Parameter.VAR_KEYWORD for param in params
            ) or {"session_id", "run_id"}.issubset(signature.parameters)
        except (TypeError, ValueError):
            accepts_metadata = False

        if accepts_metadata:
            return delegate(
                role,
                task,
                context,
                session_id=_session_id,
                run_id=_run_id,
            )
        return delegate(role, task, context)

    # ---------------------------------------------------------------------
    # Dynamic tool discovery and activation
    # ---------------------------------------------------------------------

    def _tool_catalog_search(self, query: str, limit: int = DISCOVERY_DEFAULT_LIMIT):
        try:
            safe_limit = max(1, min(int(limit), DISCOVERY_MAX_LIMIT))
        except (TypeError, ValueError):
            safe_limit = DISCOVERY_DEFAULT_LIMIT

        matches = self.tool_router.search(
            query,
            limit=safe_limit,
            exclude={TOOL_DISCOVERY_NAME},
        )
        return {
            "ok": True,
            "query": str(query)[:1000],
            "tools": matches,
        }

    @staticmethod
    def _merge_tool_names(
        active: list[str],
        additions: Iterable[str],
        available: dict[str, Tool],
        *,
        max_tools: int = MAX_ACTIVE_TOOLS,
    ) -> list[str]:
        merged = list(active)
        seen = set(merged)
        for name in additions:
            if len(merged) >= max_tools:
                break
            if name in available and name not in seen:
                merged.append(name)
                seen.add(name)
        return merged

    def _initial_tool_names(
        self,
        user_text: str,
        context: str,
        prior: str,
    ) -> list[str]:
        route_query = "\n".join(
            part
            for part in (
                user_text,
                (context or "")[-2000:],
                (prior or "")[-3000:],
            )
            if part
        )

        # Use Jev System One primitive to instantly score tool relevance
        scored_tools = []
        for name, tool in self.tools.items():
            if name == TOOL_DISCOVERY_NAME:
                continue

            tool_ctx = f"Request: {route_query}\nTool: {name} - {getattr(tool, 'description', '')}"
            level, conf = self.jev.score(
                context=tool_ctx,
                levels=["Irrelevant", "Maybe", "Highly Relevant"],
                question="How relevant is this tool to fulfilling the request?"
            )

            score_val = 0
            if level == "Highly Relevant": score_val = 2
            elif level == "Maybe": score_val = 1

            scored_tools.append((score_val + conf, name))

        # Sort by Jev score descending and take the top ones
        scored_tools.sort(reverse=True)
        names = [name for score, name in scored_tools[:INITIAL_TOOL_LIMIT] if score > 0.5]

        # Fallback to BM25 if Jev didn't find anything relevant
        if not names:
            matches = self.tool_router.search(
                route_query,
                limit=INITIAL_TOOL_LIMIT,
                exclude={TOOL_DISCOVERY_NAME},
            )
            names = [item["name"] for item in matches]

        # Catalog search is the only always-visible tool.
        names = self._merge_tool_names(
            names,
            [TOOL_DISCOVERY_NAME],
            self.tools,
        )
        return names

    def _followup_tool_names(
        self,
        user_text: str,
        tool_name: str | None,
        result: Any,
        active: list[str],
    ) -> list[str]:
        try:
            rendered_result = json.dumps(result, default=str)
        except Exception:
            rendered_result = str(result)

        query = "\n".join(
            part
            for part in (
                user_text,
                tool_name or "",
                rendered_result[:ROUTING_RESULT_CHARS],
            )
            if part
        )

        matches = self.tool_router.search(
            query,
            limit=FOLLOWUP_TOOL_LIMIT,
            exclude=set(active) | {TOOL_DISCOVERY_NAME},
        )
        return [item["name"] for item in matches]

    def _expand_from_discovery_result(
        self,
        active: list[str],
        result: Any,
    ) -> list[str]:
        if not isinstance(result, dict):
            return active
        tools = result.get("tools")
        if not isinstance(tools, list):
            return active

        names: list[str] = []
        for item in tools:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])

        return self._merge_tool_names(active, names, self.tools)

    def _schemas_for(self, active_tool_names: list[str]) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        for name in active_tool_names:
            tool = self.tools.get(name)
            if tool is None:
                continue
            schemas.append(tool.ollama_schema())
        return schemas

    @staticmethod
    def _routing_context(active_tool_names: list[str]) -> str:
        names = ", ".join(active_tool_names) if active_tool_names else "none"
        return (
            "\n\n[DYNAMIC TOOL ROUTING]\n"
            "The application exposes only a small retrieved subset of tools at a time.\n"
            f"Currently exposed tools: {names}.\n"
            f"If the required capability is not present, call {TOOL_DISCOVERY_NAME} with a concise description "
            "of the missing capability before concluding that it is unavailable.\n"
            "Tool results are authoritative for whether an action actually succeeded.\n"
            "Continue using tools until the user's requested outcome is complete or a real blocker is returned."
        )

    # ---------------------------------------------------------------------
    # Model and telemetry helpers
    # ---------------------------------------------------------------------

    def _model_lease(self):
        lease = getattr(self.mm, "lease", None)
        if callable(lease):
            try:
                return lease(self.model, priority=100)
            except TypeError:
                return lease(self.model)

        try:
            self.mm.activate(self.model, priority=100)
        except TypeError:
            self.mm.activate(self.model)
        return nullcontext(self.keep_alive)

    def _publish(self, event_type: str, **data):
        if self.event_bus:
            try:
                return self.event_bus.publish(event_type, **data)
            except Exception:
                return None
        return None

    def _history_start(
        self,
        user_text: str,
        context: str,
        session_id: str | None,
    ) -> tuple[str | None, str | None]:
        project = self._project_hint(context)
        if not self.run_history:
            return None, project
        try:
            return (
                self.run_history.start_run(
                    user_text,
                    project=project,
                    session_id=session_id,
                ),
                project,
            )
        except Exception:
            return None, project

    def _history_tool(
        self,
        run_id: str | None,
        project: str | None,
        session_id: str | None,
        name: str | None,
        args: dict,
        result,
    ):
        if not self.run_history or not run_id or not name:
            return
        try:
            self.run_history.record_tool(
                run_id,
                name,
                args,
                result,
                project=project,
                session_id=session_id,
            )
        except Exception:
            pass

    def _history_finish(
        self,
        run_id: str | None,
        project: str | None,
        session_id: str | None,
        status: str,
        summary: str = "",
    ):
        if not self.run_history or not run_id:
            return
        try:
            self.run_history.finish_run(
                run_id,
                project=project,
                session_id=session_id,
                status=status,
                summary=summary,
            )
        except Exception:
            pass

    def _record_model_usage(
        self,
        response: dict | None,
        latency_seconds: float,
        session_id: str | None,
        run_id: str | None,
    ):
        if not self.model_usage:
            return
        try:
            self.model_usage.record_response(
                self.model,
                response,
                latency_seconds,
                session_id=session_id,
                run_id=run_id,
                role="orchestrator",
            )
        except Exception:
            # Usage telemetry must never make a successful assistant response fail.
            pass

    # ---------------------------------------------------------------------
    # Context helpers
    # ---------------------------------------------------------------------

    def _skill_context(self, user_text: str) -> str:
        if not self.skills:
            return ""
        matched = self.skills.match(user_text)
        if matched:
            blocks = [
                f"Skill {item['name']} ({item.get('description', '')}):\n{item.get('instructions', '')}"
                for item in matched
            ]
            return "\n\n[USER-CONFIRMED LOCAL SKILLS]\n" + "\n\n".join(blocks)

        # When no specific skill matches, expose compact active metadata to avoid context bloat
        mgr = getattr(self.skills, "manager", None)
        if mgr and hasattr(mgr, "get_orchestrator_summary"):
            summary = mgr.get_orchestrator_summary()
            return f"\n\n{summary}\n" if summary else ""
        return ""

    def _session_context(self, session_id: str | None) -> str:
        if not self.sessions or not session_id:
            return ""
        rows = self.sessions.recent_messages(session_id, self.max_session_messages)
        if not rows:
            return ""

        char_budget = max(4000, min(60_000, int(self.context_tokens * 4 * 0.45)))
        selected: list[str] = []
        used = 0
        for row in reversed(rows):
            rendered = f"{row['role'].upper()}: {str(row['content'])[:4000]}"
            cost = len(rendered) + 1
            if selected and used + cost > char_budget:
                break
            if cost > char_budget:
                rendered = rendered[-char_budget:]
                cost = len(rendered)
            selected.append(rendered)
            used += cost
        selected.reverse()
        return "\n\n[BOUNDED LOCAL SESSION HISTORY]\n" + "\n".join(selected)

    @staticmethod
    def _project_hint(context: str) -> str | None:
        for pattern in (
            r"Project(?: path)?:\s*([^\n]+)",
            r"Preferred working directory:\s*([^\n]+)",
        ):
            match = re.search(pattern, context or "", re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip().strip('`"')
            if value in {".", "./"}:
                continue
            try:
                return Path(value).expanduser().name or value[:120]
            except Exception:
                return value[:120]
        return None

    def _experience_context(self, user_text: str, context: str) -> str:
        if not self.experiences:
            return ""
        try:
            combined = user_text + ((" " + context) if context else "")
            return self.experiences.context_for(
                combined,
                project=self._project_hint(context),
            )
        except Exception:
            return ""

    def _finish(self, answer: str, session_id: str | None) -> str:
        if self.sessions and session_id:
            self.sessions.add_message(session_id, "assistant", answer)
        return answer

    def _prepare(
        self,
        user_text: str,
        context: str,
        session_id: str | None,
    ):
        if self.sessions and session_id:
            self.sessions.ensure(session_id)
            prior = self._session_context(session_id)
            self.sessions.add_message(session_id, "user", user_text)
        else:
            prior = ""

        skill_ctx = self._skill_context(user_text)
        experience_ctx = self._experience_context(user_text, context)
        active_tool_names = self._initial_tool_names(user_text, context, prior)

        system = (
            ORCHESTRATOR
            + skill_ctx
            + experience_ctx
            + self._routing_context(active_tool_names)
        )

        user_payload = user_text
        if prior:
            user_payload += prior
        if context:
            user_payload += f"\n\nWorking context:\n{context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_payload},
        ]
        return messages, active_tool_names, self._project_hint(context)

    # ---------------------------------------------------------------------
    # Tool execution
    # ---------------------------------------------------------------------

    def _execute_tool(
        self,
        name: str | None,
        args,
        session_id: str | None = None,
        run_id: str | None = None,
    ):
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        if not isinstance(args, dict):
            args = {}

        tool = self.tools.get(name)
        if not tool:
            return args, {"ok": False, "error": f"Unknown tool {name}"}

        try:
            if name == "delegate_agent":
                return args, tool.handler(
                    **args,
                    _session_id=session_id,
                    _run_id=run_id,
                )
            return args, tool.handler(**args)
        except TypeError as exc:
            return args, {
                "ok": False,
                "error": redact_secrets(
                    f"Tool arguments invalid: {exc}",
                    2000,
                ),
            }
        except Exception as exc:
            return args, {
                "ok": False,
                "error": redact_secrets(exc, 2000),
            }

    @staticmethod
    def _serialized_tool_result(result: Any) -> str:
        try:
            return json.dumps(result, default=str)[:MAX_TOOL_RESULT_CHARS]
        except Exception:
            return json.dumps(
                {"ok": False, "error": "Tool result could not be serialized."}
            )

    def _update_active_tools_after_result(
        self,
        active_tool_names: list[str],
        user_text: str,
        tool_name: str | None,
        result: Any,
    ) -> list[str]:
        updated = list(active_tool_names)

        if tool_name == TOOL_DISCOVERY_NAME:
            updated = self._expand_from_discovery_result(updated, result)

        followups = self._followup_tool_names(
            user_text,
            tool_name,
            result,
            updated,
        )
        return self._merge_tool_names(updated, followups, self.tools)

    # ---------------------------------------------------------------------
    # Non-streaming execution
    # ---------------------------------------------------------------------

    def run(
        self,
        user_text: str,
        context: str = "",
        session_id: str | None = None,
    ) -> str:
        run_id, history_project = self._history_start(
            user_text,
            context,
            session_id,
        )
        self._publish(
            "chat.started",
            session_id=session_id,
            model=self.model,
            run_id=run_id,
        )

        if self.resources:
            ok, reason = self.resources.can_start_model()
            if not ok:
                self.mm.sleep()
                answer = (
                    "I did not load the local model because the machine is under "
                    f"memory pressure. {reason}"
                )
                self._history_finish(
                    run_id,
                    history_project,
                    session_id,
                    "resource_blocked",
                    reason,
                )
                self._publish(
                    "chat.completed",
                    session_id=session_id,
                    model=self.model,
                    run_id=run_id,
                )
                return self._finish(answer, session_id)

        messages, active_tool_names, project_hint = self._prepare(
            user_text,
            context,
            session_id,
        )
        history_project = project_hint or history_project
        trace: list[dict[str, Any]] = []

        self._publish(
            "tools.routed",
            session_id=session_id,
            run_id=run_id,
            tools=list(active_tool_names),
        )

        try:
            for step in range(self.max_steps):
                schemas = self._schemas_for(active_tool_names)

                with self._model_lease() as keep_alive:
                    usage_started = time.perf_counter()
                    data = self.mm.provider.chat(
                        self.model,
                        messages,
                        tools=schemas,
                        keep_alive=keep_alive,
                        options={"num_ctx": self.context_tokens},
                    )
                    usage_elapsed = time.perf_counter() - usage_started

                self._record_model_usage(
                    data,
                    usage_elapsed,
                    session_id,
                    run_id,
                )

                msg = data.get("message", {})
                if not isinstance(msg, dict):
                    msg = {"role": "assistant", "content": str(msg or "")}
                messages.append(msg)

                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    if self.experiences and trace:
                        try:
                            self.experiences.learn_from_trace(
                                user_text,
                                trace,
                                project=project_hint,
                                session_id=session_id,
                            )
                        except Exception:
                            pass

                    answer = str(msg.get("content") or "")
                    self._history_finish(
                        run_id,
                        history_project,
                        session_id,
                        "completed",
                        "Assistant completed the run.",
                    )
                    self._publish(
                        "chat.completed",
                        session_id=session_id,
                        model=self.model,
                        run_id=run_id,
                    )
                    return self._finish(answer, session_id)

                for call in tool_calls:
                    fn = call.get("function", {}) if isinstance(call, dict) else {}
                    name = fn.get("name")
                    args = fn.get("arguments") or {}

                    self._publish(
                        "tool.started",
                        session_id=session_id,
                        tool=name,
                        run_id=run_id,
                        step=step + 1,
                    )

                    # --- JEV SECURITY GATE ---
                    is_safe_prob = self.jev.noul(
                        context={"tool": name, "args": args},
                        statement="This tool call and its arguments are completely safe and do not violate security policies."
                    )
                    if is_safe_prob < 0.5:
                        result = f"Security Error: Jev System One router blocked this action (Safety Probability: {is_safe_prob:.2f}). Action deemed unsafe."
                        self._publish("tool.blocked", session_id=session_id, tool=name, args=args, prob=is_safe_prob)
                    else:
                        args, result = self._execute_tool(
                            name,
                            args,
                            session_id=session_id,
                            run_id=run_id,
                        )

                    self._history_tool(
                        run_id,
                        history_project,
                        session_id,
                        name,
                        args,
                        result,
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": self._serialized_tool_result(result),
                        }
                    )

                    ok_result = (
                        bool(result.get("ok", True))
                        if isinstance(result, dict)
                        else True
                    )
                    self._publish(
                        "tool.completed",
                        session_id=session_id,
                        tool=name,
                        ok=ok_result,
                        run_id=run_id,
                        step=step + 1,
                    )

                    before = list(active_tool_names)
                    active_tool_names = self._update_active_tools_after_result(
                        active_tool_names,
                        user_text,
                        name,
                        result,
                    )
                    if active_tool_names != before:
                        self._publish(
                            "tools.expanded",
                            session_id=session_id,
                            run_id=run_id,
                            tools=list(active_tool_names),
                            source_tool=name,
                        )

                    if self.experiences:
                        try:
                            episode = self.experiences.record_episode(
                                user_text,
                                name,
                                args,
                                result,
                                project=project_hint,
                                session_id=session_id,
                            )
                            trace.append({"tool_name": name, **episode})
                        except Exception:
                            pass

                # --- JEV LOOP BREAKER ---
                # After all tool calls in this step, ask Jev if the goal is met.
                # This hard-kills the loop without burning another full AirLLM inference.
                if trace:
                    try:
                        tool_summaries = [
                            f"{t.get('tool_name', '')}: {t.get('result_summary', '')}"
                            for t in trace[-6:]
                        ]
                        achieved, goal_prob = self.jev.goal_achieved(user_text, tool_summaries)
                        if achieved:
                            answer = str(msg.get("content") or "")
                            self._history_finish(
                                run_id, history_project, session_id,
                                "completed", "Jev loop-breaker: goal achieved."
                            )
                            self._publish(
                                "chat.completed",
                                session_id=session_id, model=self.model, run_id=run_id,
                            )
                            return self._finish(answer, session_id)
                    except Exception:
                        pass

        except Exception as exc:
            self._history_finish(
                run_id,
                history_project,
                session_id,
                "error",
                redact_secrets(exc, 1000),
            )
            self._publish(
                "chat.error",
                session_id=session_id,
                model=self.model,
                error=redact_secrets(exc, 500),
                run_id=run_id,
            )
            raise

        if self.experiences and trace:
            try:
                self.experiences.learn_from_trace(
                    user_text,
                    trace,
                    project=project_hint,
                    session_id=session_id,
                )
            except Exception:
                pass

        answer = (
            "I reached the configured tool-step limit before completing the task. "
            "Review the latest tool results and retry with a narrower goal."
        )
        self._history_finish(
            run_id,
            history_project,
            session_id,
            "limited",
            "Configured tool-step limit reached.",
        )
        self._publish(
            "chat.completed",
            session_id=session_id,
            model=self.model,
            limited=True,
            run_id=run_id,
        )
        return self._finish(answer, session_id)

    # ---------------------------------------------------------------------
    # Streaming execution
    # ---------------------------------------------------------------------

    def run_stream(
        self,
        user_text: str,
        context: str = "",
        session_id: str | None = None,
    ):
        """Yield structured streaming events without bypassing the tool loop."""

        run_id, history_project = self._history_start(
            user_text,
            context,
            session_id,
        )
        self._publish(
            "chat.started",
            session_id=session_id,
            model=self.model,
            run_id=run_id,
        )
        yield {
            "type": "status",
            "status": "starting",
            "model": self.model,
            "run_id": run_id,
        }

        if self.resources:
            ok, reason = self.resources.can_start_model()
            if not ok:
                self.mm.sleep()
                answer = (
                    "I did not load the local model because the machine is under "
                    f"memory pressure. {reason}"
                )
                self._finish(answer, session_id)
                self._history_finish(
                    run_id,
                    history_project,
                    session_id,
                    "resource_blocked",
                    reason,
                )
                self._publish(
                    "chat.completed",
                    session_id=session_id,
                    model=self.model,
                    run_id=run_id,
                )
                yield {
                    "type": "final",
                    "text": answer,
                    "session_id": session_id,
                    "run_id": run_id,
                }
                return

        messages, active_tool_names, project_hint = self._prepare(
            user_text,
            context,
            session_id,
        )
        history_project = project_hint or history_project
        trace: list[dict[str, Any]] = []

        self._publish(
            "tools.routed",
            session_id=session_id,
            run_id=run_id,
            tools=list(active_tool_names),
        )
        yield {
            "type": "routing",
            "tools": list(active_tool_names),
        }

        try:
            for step in range(self.max_steps):
                schemas = self._schemas_for(active_tool_names)

                self._publish(
                    "model.generating",
                    session_id=session_id,
                    model=self.model,
                    step=step + 1,
                    run_id=run_id,
                )
                yield {
                    "type": "status",
                    "status": "generating",
                    "model": self.model,
                    "step": step + 1,
                }

                content_parts: list[str] = []
                tool_calls: list[dict] = []
                seen_calls: set[str] = set()
                last_usage_chunk: dict | None = None

                with self._model_lease() as keep_alive:
                    usage_started = time.perf_counter()
                    for chunk in self.mm.provider.chat_stream(
                        self.model,
                        messages,
                        tools=schemas,
                        keep_alive=keep_alive,
                        options={"num_ctx": self.context_tokens},
                    ):
                        if not isinstance(chunk, dict):
                            continue

                        last_usage_chunk = chunk
                        msg_part = chunk.get("message") or {}
                        if not isinstance(msg_part, dict):
                            continue

                        text = str(msg_part.get("content") or "")
                        if text:
                            content_parts.append(text)
                            yield {"type": "token", "text": text}

                        for call in msg_part.get("tool_calls") or []:
                            try:
                                key = json.dumps(call, sort_keys=True, default=str)
                            except Exception:
                                key = repr(call)
                            if key not in seen_calls:
                                seen_calls.add(key)
                                tool_calls.append(call)

                    usage_elapsed = time.perf_counter() - usage_started

                self._record_model_usage(
                    last_usage_chunk,
                    usage_elapsed,
                    session_id,
                    run_id,
                )

                msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(content_parts),
                }
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                messages.append(msg)

                if not tool_calls:
                    if self.experiences and trace:
                        try:
                            self.experiences.learn_from_trace(
                                user_text,
                                trace,
                                project=project_hint,
                                session_id=session_id,
                            )
                        except Exception:
                            pass

                    answer = str(msg.get("content") or "")
                    self._finish(answer, session_id)
                    self._history_finish(
                        run_id,
                        history_project,
                        session_id,
                        "completed",
                        "Assistant completed the run.",
                    )
                    self._publish(
                        "chat.completed",
                        session_id=session_id,
                        model=self.model,
                        run_id=run_id,
                    )
                    yield {
                        "type": "final",
                        "text": answer,
                        "session_id": session_id,
                        "run_id": run_id,
                    }
                    return

                for call in tool_calls:
                    fn = call.get("function", {}) if isinstance(call, dict) else {}
                    name = fn.get("name")
                    args = fn.get("arguments") or {}

                    self._publish(
                        "tool.started",
                        session_id=session_id,
                        tool=name,
                        run_id=run_id,
                        step=step + 1,
                    )
                    yield {
                        "type": "tool",
                        "tool": name,
                        "status": "started",
                    }

                    # --- JEV SECURITY GATE ---
                    # Use Noul primitive to block potentially harmful tool calls
                    is_safe_prob = self.jev.noul(
                        context={"tool": name, "args": args},
                        statement="This tool call and its arguments are completely safe and do not violate security policies (like dropping databases, leaking keys, or writing to system files)."
                    )
                    if is_safe_prob < 0.5:
                        result = f"Security Error: Jev System One router blocked this action (Safety Probability: {is_safe_prob:.2f}). Action deemed unsafe."
                        self._publish("tool.blocked", session_id=session_id, tool=name, args=args, prob=is_safe_prob)
                    else:
                        args, result = self._execute_tool(
                            name,
                            args,
                            session_id=session_id,
                            run_id=run_id,
                        )

                    self._history_tool(
                        run_id,
                        history_project,
                        session_id,
                        name,
                        args,
                        result,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": self._serialized_tool_result(result),
                        }
                    )

                    ok_result = (
                        bool(result.get("ok", True))
                        if isinstance(result, dict)
                        else True
                    )
                    self._publish(
                        "tool.completed",
                        session_id=session_id,
                        tool=name,
                        ok=ok_result,
                        run_id=run_id,
                        step=step + 1,
                    )
                    yield {
                        "type": "tool",
                        "tool": name,
                        "status": "completed",
                        "ok": ok_result,
                    }

                    before = list(active_tool_names)
                    active_tool_names = self._update_active_tools_after_result(
                        active_tool_names,
                        user_text,
                        name,
                        result,
                    )
                    if active_tool_names != before:
                        self._publish(
                            "tools.expanded",
                            session_id=session_id,
                            run_id=run_id,
                            tools=list(active_tool_names),
                            source_tool=name,
                        )
                        yield {
                            "type": "routing",
                            "tools": list(active_tool_names),
                        }

                    if self.experiences:
                        try:
                            episode = self.experiences.record_episode(
                                user_text,
                                name,
                                args,
                                result,
                                project=project_hint,
                                session_id=session_id,
                            )
                            trace.append({"tool_name": name, **episode})
                        except Exception:
                            pass

                # --- JEV LOOP BREAKER (streaming) ---
                # Same sub-100ms goal check as run(). No extra AirLLM call needed.
                if trace:
                    try:
                        tool_summaries = [
                            f"{t.get('tool_name', '')}: {t.get('result_summary', '')}"
                            for t in trace[-6:]
                        ]
                        achieved, goal_prob = self.jev.goal_achieved(user_text, tool_summaries)
                        if achieved:
                            answer = str(msg.get("content") or "")
                            self._finish(answer, session_id)
                            self._history_finish(
                                run_id, history_project, session_id,
                                "completed", "Jev loop-breaker: goal achieved."
                            )
                            self._publish(
                                "chat.completed",
                                session_id=session_id, model=self.model, run_id=run_id,
                            )
                            yield {"type": "final", "text": answer, "session_id": session_id, "run_id": run_id}
                            return
                    except Exception:
                        pass

        except Exception as exc:
            self._history_finish(
                run_id,
                history_project,
                session_id,
                "error",
                redact_secrets(exc, 1000),
            )
            self._publish(
                "chat.error",
                session_id=session_id,
                model=self.model,
                error=redact_secrets(exc, 500),
                run_id=run_id,
            )
            yield {
                "type": "error",
                "error": redact_secrets(exc, 1200),
                "run_id": run_id,
            }
            return

        if self.experiences and trace:
            try:
                self.experiences.learn_from_trace(
                    user_text,
                    trace,
                    project=project_hint,
                    session_id=session_id,
                )
            except Exception:
                pass

        answer = (
            "I reached the configured tool-step limit before completing the task. "
            "Review the latest tool results and retry with a narrower goal."
        )
        self._finish(answer, session_id)
        self._history_finish(
            run_id,
            history_project,
            session_id,
            "limited",
            "Configured tool-step limit reached.",
        )
        self._publish(
            "chat.completed",
            session_id=session_id,
            model=self.model,
            limited=True,
            run_id=run_id,
        )
        yield {
            "type": "final",
            "text": answer,
            "session_id": session_id,
            "run_id": run_id,
        }
