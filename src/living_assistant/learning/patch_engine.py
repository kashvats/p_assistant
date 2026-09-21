from __future__ import annotations

import ast
import difflib
from pathlib import Path


class ASTSafePatchEngine:
    """AST-aware guard for full-file improvement proposals."""

    @staticmethod
    def _symbols(tree: ast.AST) -> dict[str, ast.AST]:
        symbols: dict[str, ast.AST] = {}

        def walk(body: list[ast.stmt], prefix: str = "") -> None:
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = f"{prefix}.{node.name}" if prefix else node.name
                    symbols[name] = node
                    if isinstance(node, ast.ClassDef):
                        walk(node.body, name)

        if isinstance(tree, ast.Module):
            walk(tree.body)
        return symbols

    def analyze(self, original: str, proposed: str, path: str | Path) -> dict:
        target = Path(path)
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(True),
                proposed.splitlines(True),
                fromfile=str(target),
                tofile=str(target),
            )
        )
        result = {
            "ok": True,
            "ast_checked": target.suffix.lower() == ".py",
            "diff": diff,
            "added_symbols": [],
            "changed_symbols": [],
            "removed_symbols": [],
        }
        if target.suffix.lower() != ".py":
            return result

        try:
            proposed_tree = ast.parse(proposed, filename=str(target))
        except SyntaxError as exc:
            return {
                **result,
                "ok": False,
                "error": f"Proposed Python is not syntactically valid: {exc.msg} (line {exc.lineno}).",
                "syntax_error": {"message": exc.msg, "line": exc.lineno, "offset": exc.offset},
            }

        try:
            original_tree = ast.parse(original, filename=str(target))
        except SyntaxError as exc:
            result["original_syntax_error"] = {
                "message": exc.msg,
                "line": exc.lineno,
                "offset": exc.offset,
            }
            return result

        old_symbols = self._symbols(original_tree)
        new_symbols = self._symbols(proposed_tree)
        old_names = set(old_symbols)
        new_names = set(new_symbols)
        removed = sorted(old_names - new_names)
        added = sorted(new_names - old_names)
        changed = sorted(
            name
            for name in old_names & new_names
            if ast.dump(old_symbols[name], include_attributes=False)
            != ast.dump(new_symbols[name], include_attributes=False)
        )
        result.update(
            added_symbols=added,
            changed_symbols=changed,
            removed_symbols=removed,
        )
        if removed:
            result["ok"] = False
            result["error"] = (
                "AST safety blocked removal of existing Python symbols: "
                + ", ".join(removed[:20])
                + (" ..." if len(removed) > 20 else "")
            )
        return result
