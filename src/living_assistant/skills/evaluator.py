from __future__ import annotations

import ast
import re
from typing import Any


class DeclarativeEvaluationError(RuntimeError):
    pass


def _resolve_context_path(path: str, context: dict[str, Any]) -> Any:
    """Resolve a dot-separated variable path within the execution context."""
    parts = path.strip().split(".")
    curr: Any = context
    for part in parts:
        if isinstance(curr, dict):
            if part in curr:
                curr = curr[part]
            else:
                return None
        elif hasattr(curr, part):
            curr = getattr(curr, part)
        else:
            return None
    return curr


def interpolate_variables(template: Any, context: dict[str, Any]) -> Any:
    """Recursively interpolates {path.to.var} placeholders in strings, dicts, and lists.

    Supports typed substitution: if the string is exactly '{path.to.var}',
    the raw typed value (e.g. list, dict, bool, int, float) is returned.
    """
    if isinstance(template, str):
        # Check if template is exactly a single placeholder: "{var}"
        exact_match = re.fullmatch(r"\{([a-zA-Z0-9_.]+)\}", template.strip())
        if exact_match:
            val = _resolve_context_path(exact_match.group(1), context)
            return val if val is not None else ""

        # Otherwise do string substitution
        def replace_match(m):
            val = _resolve_context_path(m.group(1), context)
            if val is None:
                return ""
            if isinstance(val, (dict, list)):
                import json
                return json.dumps(val)
            return str(val)

        return re.sub(r"\{([a-zA-Z0-9_.]+)\}", replace_match, template)

    elif isinstance(template, dict):
        return {k: interpolate_variables(v, context) for k, v in template.items()}
    elif isinstance(template, list):
        return [interpolate_variables(item, context) for item in template]
    return template


class _SafeConditionVisitor(ast.NodeVisitor):
    """Restricted AST visitor for evaluating declarative boolean conditions safely without eval()."""

    ALLOWED_NODES = (
        ast.Expression,
        ast.Compare,
        ast.BoolOp,
        ast.UnaryOp,
        ast.BinOp,
        ast.Constant,
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.Index,
        ast.Load,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Is,
        ast.IsNot,
        ast.In,
        ast.NotIn,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Add,
        ast.Sub,
    )

    def __init__(self, context: dict[str, Any]):
        self.context = context

    def visit(self, node: ast.AST) -> Any:
        if not isinstance(node, self.ALLOWED_NODES):
            raise DeclarativeEvaluationError(
                f"Unsupported declarative expression node: {type(node).__name__}. Calls, lambdas, and statements are prohibited."
            )
        return super().visit(node)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        name = node.id
        if name in {"true", "True"}:
            return True
        if name in {"false", "False"}:
            return False
        if name in {"null", "None"}:
            return None
        return _resolve_context_path(name, self.context)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        val = self.visit(node.value)
        if isinstance(val, dict):
            return val.get(node.attr)
        return getattr(val, node.attr, None)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        val = self.visit(node.value)
        slice_val = self.visit(node.slice)
        try:
            return val[slice_val]
        except Exception:
            return None

    def visit_Index(self, node: Any) -> Any:
        return self.visit(node.value)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        val = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not bool(val)
        if isinstance(node.op, ast.USub):
            return -val
        raise DeclarativeEvaluationError(f"Unsupported unary operator: {type(node.op).__name__}")

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not bool(self.visit(v)):
                    return False
            return True
        elif isinstance(node.op, ast.Or):
            for v in node.values:
                if bool(self.visit(v)):
                    return True
            return False
        raise DeclarativeEvaluationError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        raise DeclarativeEvaluationError(f"Unsupported binary operator: {type(node.op).__name__}")

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            result = self._apply_cmp(op, left, right)
            if not result:
                return False
            left = right
        return True

    def _apply_cmp(self, op: ast.cmpop, left: Any, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.Is):
            return left is right
        if isinstance(op, ast.IsNot):
            return left is not right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
        raise DeclarativeEvaluationError(f"Unsupported comparison operator: {type(op).__name__}")


def evaluate_condition(expression: str | None, context: dict[str, Any]) -> bool:
    """Safely evaluates a declarative condition expression against context without eval().

    If expression is empty or None, defaults to True.
    """
    if not expression or not expression.strip():
        return True

    expr = expression.strip()
    # Interpolate variables first if curly braces are present: e.g. "{files.count} > 0"
    if "{" in expr:
        expr = interpolate_variables(expr, context)

    # Normalize true/false/null
    expr = re.sub(r"\btrue\b", "True", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bfalse\b", "False", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bnull\b", "None", expr, flags=re.IGNORECASE)

    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise DeclarativeEvaluationError(f"Invalid condition syntax '{expression}': {exc}")

    visitor = _SafeConditionVisitor(context)
    result = visitor.visit(parsed)
    return bool(result)


def validate_workflow_contract(
    workflow: list[Any],
    registered_tools: set[str],
    max_steps: int = 50,
) -> list[str]:
    """Validate workflow steps for uniqueness, registered tools, dependency cycles, and limits."""
    errors: list[str] = []
    if len(workflow) > max_steps:
        errors.append(f"Workflow contains {len(workflow)} steps, exceeding maximum limit of {max_steps}.")

    step_ids: set[str] = set()
    portable_tools = {
        "files.list", "files.read", "files.move", "files.write", "files.preview_write",
        "documents.extract", "notifications.show", "calendar.list", "briefings.get",
        "personal.remember", "personal.recall"
    }
    all_valid_tools = registered_tools | portable_tools

    # Step ID uniqueness and tool validity
    for step in workflow:
        step_id = getattr(step, "id", "")
        if not step_id:
            errors.append("Workflow step is missing required 'id'.")
            continue
        if step_id in step_ids:
            errors.append(f"Duplicate step ID '{step_id}' found in workflow.")
        step_ids.add(step_id)

        tool = getattr(step, "tool", "")
        if tool not in all_valid_tools:
            errors.append(f"Step '{step_id}' references unregistered tool '{tool}'.")

    # Dependency ordering and cycle detection
    # Step arguments may reference {previous_step.output_var} or {step_id.output_var}
    seen_steps: set[str] = set()
    for step in workflow:
        step_id = getattr(step, "id", "")
        args_str = str(getattr(step, "arguments", {})) + " " + str(getattr(step, "when", "") or "")
        referenced = re.findall(r"\{([a-zA-Z0-9_]+)\.", args_str)
        for ref in referenced:
            if ref in step_ids:
                if ref == step_id:
                    errors.append(f"Cyclic self-reference: Step '{step_id}' references its own output.")
                elif ref not in seen_steps:
                    errors.append(f"Step '{step_id}' references output of forward step '{ref}'. Steps must be topologically ordered.")
        seen_steps.add(step_id)

    return errors
