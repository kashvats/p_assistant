from __future__ import annotations

from .base import Tool
from living_assistant.integrations.codebase_memory import CodebaseMemoryAdapter


def build_codebase_memory_tools(adapter: CodebaseMemoryAdapter) -> list[Tool]:
    def cbm_get_architecture(project_path: str = ".") -> dict:
        """Get high-level architecture overview: languages, boundaries, entry points, layers."""
        return adapter.get_architecture(project_path=project_path)

    def cbm_index_repository(project_path: str = ".") -> dict:
        """Index a project into the Codebase Memory AST knowledge graph."""
        return adapter.index_repository(project_path=project_path)

    def cbm_query_graph(query: str, project_path: str = ".") -> dict:
        """Run a Cypher-like knowledge graph query over the codebase AST."""
        return adapter.query_graph(cypher_query=query, project_path=project_path)

    def cbm_find_callers(symbol: str, project_path: str = ".") -> dict:
        """Find all functions/methods calling the given symbol across packages."""
        return adapter.find_callers(symbol=symbol, project_path=project_path)

    def cbm_find_callees(symbol: str, project_path: str = ".") -> dict:
        """Find all functions/methods called by the given symbol."""
        return adapter.find_callees(symbol=symbol, project_path=project_path)

    def cbm_manage_adr(action: str = "list", title: str = "", content: str = "", project_path: str = ".") -> dict:
        """Create, read, or list Architectural Decision Records (ADRs)."""
        return adapter.manage_adr(action=action, title=title, content=content, project_path=project_path)

    return [
        Tool(
            "cbm_get_architecture",
            (
                "Extract a comprehensive architecture overview of a codebase: languages, "
                "packages, entry points, routes, hotspots, boundaries, layers, and clusters."
            ),
            {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "default": ".",
                        "description": "Path to the repository root directory",
                    },
                },
            },
            cbm_get_architecture,
        ),
        Tool(
            "cbm_index_repository",
            (
                "Trigger Codebase Memory AST indexing for a repository. Automatically parses "
                "files into an ultra-fast structural knowledge graph."
            ),
            {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string", "default": "."},
                },
            },
            cbm_index_repository,
        ),
        Tool(
            "cbm_query_graph",
            (
                "Execute Cypher-like graph queries over the codebase (e.g. "
                "'MATCH (f:Function)-[:CALLS]->(g) WHERE f.name = \"main\" RETURN g.name')."
            ),
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Cypher-like AST graph query"},
                    "project_path": {"type": "string", "default": "."},
                },
                "required": ["query"],
            },
            cbm_query_graph,
        ),
        Tool(
            "cbm_find_callers",
            (
                "Resolve all cross-file and cross-package callers of a specific function or class."
            ),
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Function, method, or class name"},
                    "project_path": {"type": "string", "default": "."},
                },
                "required": ["symbol"],
            },
            cbm_find_callers,
        ),
        Tool(
            "cbm_find_callees",
            (
                "Resolve all functions or dependencies called by a specific function or method."
            ),
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Function, method, or class name"},
                    "project_path": {"type": "string", "default": "."},
                },
                "required": ["symbol"],
            },
            cbm_find_callees,
        ),
        Tool(
            "cbm_manage_adr",
            (
                "Manage Architectural Decision Records (ADRs) to persist long-term engineering "
                "decisions across sessions."
            ),
            {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "get", "create"], "default": "list"},
                    "title": {"type": "string", "description": "Title of the ADR"},
                    "content": {"type": "string", "description": "ADR markdown body or rationale"},
                    "project_path": {"type": "string", "default": "."},
                },
            },
            cbm_manage_adr,
        ),
    ]
