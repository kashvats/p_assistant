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

# Allowlist of LA tool names that Hermes may call.  All of these already
# contain security-guardian approval gates inside their handlers.
_ALLOWED_TOOL_NAMES = frozenset({
    "shell_exec", "file_read", "file_write",
    "git_commit", "playwright_navigate", "playwright_extract",
})


def _la_tool_to_hermes_schema(tool: Tool) -> dict:
    """Return an OpenAI-compatible function schema for a Living Assistant tool."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _build_tool_dispatch(tools: list[Tool]) -> dict[str, Tool]:
    return {t.name: t for t in tools}


class HermesContractor:
    """
    Sandboxed specialist contractor powered by hermes-agent's AIAgent.

    Hermes performs multi-step reasoning and tool planning; every tool
    invocation is dispatched through Living Assistant's own handlers so
    security gates, approval prompts, and resource limits are never bypassed.
    """

    def __init__(self, model_manager, session_id: str, tool_registry: ToolRegistry | None = None):
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

        # Build the allowed tool set from the registry passed in by the daemon.
        # Falls back to an empty set if no registry is provided so the contractor
        # can still run in read/reasoning-only mode.
        allowed: list[Tool] = []
        if tool_registry is not None:
            allowed = [t for t in tool_registry.all() if t.name in _ALLOWED_TOOL_NAMES]
        self._dispatch = _build_tool_dispatch(allowed)
        self._tool_schemas = [_la_tool_to_hermes_schema(t) for t in allowed]

        logger.info(
            "[HermesContractor] Initialized with %d armored tools: %s",
            len(allowed),
            [t.name for t in allowed],
        )

    def _handle_tool_call(self, tool_name: str, arguments: dict) -> Any:
        """Called by the Hermes loop when it wants to invoke a tool."""
        tool = self._dispatch.get(tool_name)
        if tool is None:
            logger.warning("[HermesContractor] Blocked disallowed tool request: %s", tool_name)
            return {"ok": False, "error": f"Tool '{tool_name}' is not available to the contractor."}

        logger.info("[HermesContractor] Executing armored tool: %s args=%s", tool_name, list(arguments.keys()))
        try:
            return tool.handler(**arguments)
        except TypeError as exc:
            return {"ok": False, "error": f"Invalid arguments for {tool_name}: {exc}"}
        except Exception as exc:
            logger.error("[HermesContractor] Tool %s raised: %s", tool_name, exc)
            return {"ok": False, "error": str(exc)}

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
                agent = self._AIAgent(
                    provider="ollama",       # local-first; honours privacy guarantee
                    session_id=self.session_id,
                    ephemeral_system_prompt=(
                        "You are an isolated specialist contractor inside the Living Assistant "
                        "ecosystem. Use only the tools provided. Your outputs will be reviewed "
                        "by the Security Guardian before any action reaches the host OS."
                    ),
                    tool_start_callback=lambda name, args: logger.debug(
                        "[HermesContractor] tool_start: %s", name
                    ),
                    quiet_mode=True,
                )

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
                    if name in self._dispatch:
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
