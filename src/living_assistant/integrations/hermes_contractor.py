"""
Hermes Agent Integration - The "Brain in a Vat"
Wraps the real hermes-agent AIAgent (from run_agent) and routes Living Assistant's
armored tools through it. All high-risk actions (Shell, File I/O, Browser) remain
gated by the Nervous System Daemon's security_guardian — Hermes never executes
anything directly on the host.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from living_assistant.tools.registry import ToolRegistry
from living_assistant.tools.base import Tool

logger = logging.getLogger("living_assistant.hermes_contractor")

# Alias mapping dictionary supporting both canonical Living Assistant tool names
# and legacy / alias tool names.
_ALLOWED_TOOL_MAPPING: dict[str, str] = {
    # Filesystem canonical tools
    "read_file": "read_file",
    "write_file": "write_file",
    "edit_file": "edit_file",
    "delete_file": "delete_file",
    "list_files": "list_files",
    "search_files": "search_files",
    "preview_write_file": "preview_write_file",
    # Shell & execution canonical tools
    "run_command": "run_command",
    # Git canonical tools
    "git_commit": "git_commit",
    "git_diff": "git_diff",
    "git_status": "git_status",
    # Browser canonical tools
    "browser_snapshot": "browser_snapshot",

    # Legacy / alias tool names mapped to canonical names
    "file_read": "read_file",
    "file_write": "write_file",
    "file_delete": "delete_file",
    "remove_file": "delete_file",
    "unlink": "delete_file",
    "create_file": "write_file",
    "touch": "write_file",
    "shell_exec": "run_command",
    "playwright_navigate": "browser_snapshot",
    "playwright_extract": "browser_snapshot",
}

# Allowlist of tool names (both canonical and legacy aliases) for backward compatibility
_ALLOWED_TOOL_NAMES = frozenset(_ALLOWED_TOOL_MAPPING.keys())


def _la_tool_to_hermes_schema(tool: Tool) -> dict:
    """Return an OpenAI-compatible function schema for a Living Assistant tool."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.parameters if isinstance(tool.parameters, dict) else {},
        },
    }


def _build_tool_dispatch(tools: list[Tool]) -> dict[str, Tool]:
    """
    Build a dispatch mapping connecting canonical names and all recognized aliases
    to their corresponding tool instances.
    """
    dispatch: dict[str, Tool] = {}
    for t in tools:
        canonical = _ALLOWED_TOOL_MAPPING.get(t.name, t.name)
        dispatch[canonical] = t
        dispatch[t.name] = t
        for alias, target in _ALLOWED_TOOL_MAPPING.items():
            if target == canonical or target == t.name:
                dispatch[alias] = t
    return dispatch


class HermesContractor:
    """
    Sandboxed specialist contractor powered by hermes-agent's AIAgent.

    Hermes performs multi-step reasoning and tool planning; every tool
    invocation is dispatched through Living Assistant's own handlers so
    security gates, approval prompts, and resource limits are never bypassed.
    """

    def __init__(
        self,
        model_manager=None,
        session_id: str = "default",
        tool_registry: ToolRegistry | None = None,
        base_url: str = "http://127.0.0.1:8080/v1",
        model_name: str = "openai/collibri",
        provider: str = "ollama",
    ):
        try:
            from run_agent import AIAgent  # real hermes-agent entry point
            self._AIAgent = AIAgent
        except ImportError as exc:
            raise RuntimeError(
                "hermes-agent is not installed or broken. "
                "Run: pip install 'hermes-agent>=0.19.0,<1'"
            ) from exc

        self.session_id = session_id
        self.mm = model_manager
        self.base_url = base_url
        self.model_name = model_name
        self.provider = provider

        # Build the allowed tool set from the registry passed in by the daemon.
        # Falls back to an empty set if no registry is provided so the contractor
        # can still run in read/reasoning-only mode.
        allowed: list[Tool] = []
        if tool_registry is not None:
            seen_canonical: set[str] = set()
            for t in tool_registry.all():
                canonical = _ALLOWED_TOOL_MAPPING.get(t.name)
                if canonical is not None:
                    if canonical not in seen_canonical:
                        seen_canonical.add(canonical)
                        allowed.append(t)
        self._dispatch = _build_tool_dispatch(allowed)
        self._tool_schemas = [_la_tool_to_hermes_schema(t) for t in allowed]

        logger.info(
            "[HermesContractor] Initialized with %d armored tools: %s",
            len(allowed),
            [t.name for t in allowed],
        )

    def _handle_tool_call(self, tool_name: str, arguments: dict | str) -> Any:
        """Called by the Hermes loop when it wants to invoke a tool."""
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {}
        elif not isinstance(arguments, dict):
            arguments = {}

        canonical_name = _ALLOWED_TOOL_MAPPING.get(tool_name, tool_name)
        tool = self._dispatch.get(canonical_name) or self._dispatch.get(tool_name)
        if tool is None:
            logger.warning("[HermesContractor] Blocked disallowed tool request: %s (resolved: %s)", tool_name, canonical_name)
            return {"ok": False, "error": f"Tool '{tool_name}' is not available to the contractor."}

        logger.info("[HermesContractor] Executing armored tool: %s (from alias %s) args=%s", canonical_name, tool_name, list(arguments.keys()))

        # Normalize argument aliases for backward compatibility (e.g., file_path -> path, cmd -> command)
        normalized_args = dict(arguments)
        if "file_path" in normalized_args and "path" not in normalized_args:
            normalized_args["path"] = normalized_args.pop("file_path")
        if "cmd" in normalized_args and "command" not in normalized_args:
            normalized_args["command"] = normalized_args.pop("cmd")

        try:
            res = tool.handler(**normalized_args)
        except TypeError as exc:
            return {"ok": False, "error": f"Invalid arguments for {tool_name}: {exc}"}
        except Exception as exc:
            logger.error("[HermesContractor] Tool %s raised: %s", tool_name, exc)
            return {"ok": False, "error": str(exc)}

        if isinstance(res, dict) and (res.get("approval_required") or res.get("status") == "PENDING_APPROVAL"):
            return {
                "ok": False,
                "status": "PENDING_APPROVAL",
                "message": "Action paused for user approval.",
            }

        return res

    def execute_task(self, task: str, context: str, timeout: float = 300.0) -> dict[str, Any]:
        """
        Run the Hermes Agent loop for a complex multi-step task.

        Hermes handles its own thought → tool-call → observation loop.
        We pass Living Assistant's armored tools as the available function set,
        wiring each call back through _handle_tool_call so security gates fire.
        """
        logger.info("[HermesContractor] Starting task: %.80s", task)

        full_prompt = f"Task: {task}\n\nContext:\n{context}" if context else task

        result_box: dict = {}
        error_box: dict = {}

        def _run():
            try:
                agent_kwargs: dict[str, Any] = {
                    "provider": self.provider,
                    "session_id": self.session_id,
                    "ephemeral_system_prompt": (
                        "You are an isolated specialist contractor inside the Living Assistant "
                        "ecosystem. Use only the tools provided. Your outputs will be reviewed "
                        "by the Security Guardian before any action reaches the host OS."
                    ),
                    "tool_start_callback": lambda name, args: logger.debug(
                        "[HermesContractor] tool_start: %s", name
                    ),
                    "quiet_mode": True,
                }
                if self.base_url:
                    agent_kwargs["base_url"] = self.base_url
                if self.model_name:
                    agent_kwargs["model"] = self.model_name

                agent = self._AIAgent(**agent_kwargs)

                # Inject our armored tool schemas into the agent's toolset.
                # AIAgent accepts custom tool definitions via get_tool_definitions
                # at runtime; we patch its internal list before the run loop.
                if self._tool_schemas:
                    existing = agent.get_tool_definitions() if callable(getattr(agent, "get_tool_definitions", None)) else []
                    # Merge: LA tools take precedence over any built-in with same name
                    la_names = {s["function"]["name"] for s in self._tool_schemas}
                    merged = [s for s in (existing or []) if s.get("function", {}).get("name") not in la_names]
                    merged.extend(self._tool_schemas)
                    if hasattr(agent, "_tool_definitions"):
                        agent._tool_definitions = merged

                # Wire our dispatcher so Hermes calls _handle_tool_call for LA tools
                original_handle = getattr(agent, "handle_function_call", None)

                def patched_handle(name, arguments, **kwargs):
                    canonical_name = _ALLOWED_TOOL_MAPPING.get(name, name)
                    if canonical_name in self._dispatch or name in self._dispatch:
                        return self._handle_tool_call(name, arguments)
                    if callable(original_handle):
                        return original_handle(name, arguments, **kwargs)
                    return {"ok": False, "error": f"No handler for tool: {name}"}

                agent.handle_function_call = patched_handle

                response = agent.run(full_prompt)
                result_box["output"] = response
            except Exception as exc:
                error_box["error"] = str(exc)
                logger.error("[HermesContractor] run failed: %s", exc)

        worker = threading.Thread(target=_run, name="hermes-contractor", daemon=True)
        worker.start()
        worker.join(timeout=timeout)

        if worker.is_alive():
            logger.error("[HermesContractor] Task timed out after %.0fs", timeout)
            return {"ok": False, "error": f"Hermes contractor timed out after {timeout:.0f}s.", "contractor": "hermes_agent"}

        if "error" in error_box:
            return {"ok": False, "error": error_box["error"], "contractor": "hermes_agent"}

        return {"ok": True, "output": result_box.get("output", ""), "contractor": "hermes_agent"}
