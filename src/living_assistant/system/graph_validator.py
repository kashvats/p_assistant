from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class GraphDiagnostics:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    node_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "node_count": self.node_count,
        }


class SystemGraphValidator:
    """Validates system.graph.yaml integrity against code reality, dependency cycles,

    duplicate node IDs, and registered capabilities.
    """

    @classmethod
    def validate_file(
        cls,
        graph_path: Path | str,
        repo_root: Path | str | None = None,
        registered_tools: list[str] | set[str] | None = None,
    ) -> GraphDiagnostics:
        path = Path(graph_path).resolve()
        if not path.exists():
            return GraphDiagnostics(ok=False, errors=[f"Graph file not found: {path}"])

        try:
            raw_text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw_text)
        except Exception as exc:
            return GraphDiagnostics(ok=False, errors=[f"Invalid YAML syntax in graph file: {exc}"])

        return cls.validate_dict(data, repo_root=repo_root, registered_tools=registered_tools)

    @classmethod
    def validate_dict(
        cls,
        data: Any,
        repo_root: Path | str | None = None,
        registered_tools: list[str] | set[str] | None = None,
    ) -> GraphDiagnostics:
        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(data, dict) or "system" not in data:
            return GraphDiagnostics(ok=False, errors=["Schema violation: Root must contain a 'system' mapping."])

        system = data["system"]
        nodes = system.get("nodes")
        if not isinstance(nodes, list):
            return GraphDiagnostics(ok=False, errors=["Schema violation: 'system.nodes' must be a list."])

        seen_ids: set[str] = set()
        root_path = Path(repo_root).resolve() if repo_root else None
        adj_list: dict[str, list[str]] = {}

        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"Node at index {idx} is not a dictionary.")
                continue

            node_id = node.get("id")
            if not node_id:
                errors.append(f"Node at index {idx} is missing an 'id'.")
                continue

            # Duplicate Node ID Check
            if node_id in seen_ids:
                errors.append(f"Duplicate node ID detected: '{node_id}'.")
            seen_ids.add(node_id)

            # Node Type and State checks
            if not node.get("type"):
                warnings.append(f"Node '{node_id}' is missing a 'type' field.")
            if not node.get("state"):
                warnings.append(f"Node '{node_id}' is missing a 'state' field.")

            # Referenced implementation file check
            file_rel = node.get("file")
            if file_rel and root_path:
                node_file = root_path / file_rel
                if not node_file.exists():
                    warnings.append(f"Node '{node_id}' references non-existent implementation file: '{file_rel}'.")

            # Dependencies for cycle detection
            deps = node.get("dependencies", [])
            if isinstance(deps, list):
                adj_list[node_id] = [d for d in deps if isinstance(d, str)]
            else:
                adj_list[node_id] = []

        # Dependency cycle detection using DFS
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(curr: str, path_stack: list[str]):
            visited.add(curr)
            rec_stack.add(curr)
            path_stack.append(curr)

            for neighbor in adj_list.get(curr, []):
                if neighbor not in visited:
                    dfs(neighbor, path_stack)
                elif neighbor in rec_stack:
                    cycle = " -> ".join(path_stack + [neighbor])
                    errors.append(f"Dependency cycle detected: {cycle}")

            rec_stack.remove(curr)
            path_stack.pop()

        for n_id in adj_list:
            if n_id not in visited:
                dfs(n_id, [])

        # Check registered tools against graph
        if registered_tools:
            # Look for tool node references or registry node
            graph_tool_ids = {n.get("tool_name") or n.get("id") for n in nodes if isinstance(n, dict)}
            for tool_name in registered_tools:
                if f"TOOL_{tool_name.upper().replace('.', '_')}" not in seen_ids and tool_name not in graph_tool_ids:
                    warnings.append(f"Runtime tool '{tool_name}' is registered but absent in system graph.")

        ok = len(errors) == 0
        return GraphDiagnostics(ok=ok, errors=errors, warnings=warnings, node_count=len(seen_ids))
