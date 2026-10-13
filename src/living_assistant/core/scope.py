"""Per-turn workspace scope for company employees.

While an employee works on a project, file paths resolve inside the project folder and anything
outside it is refused (Workspace.resolve). If the user opted in for that project, ordinary build and
test commands run inside the folder without asking each time; destructive, privileged, system and
network commands still ask. Context variables keep this to the employee's own turn: chat and other
threads are unaffected.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_scope: ContextVar[Path | None] = ContextVar("workspace_scope", default=None)
_trust_commands: ContextVar[bool] = ContextVar("workspace_trust_commands", default=False)


def current_scope() -> Path | None:
    return _scope.get()


def commands_trusted() -> bool:
    return _trust_commands.get()


def within(path: Path, root: Path) -> bool:
    path, root = Path(path).resolve(), Path(root).resolve()
    return path == root or root in path.parents


@contextmanager
def project_scope(folder: str | Path, trust_commands: bool = False):
    scope_token = _scope.set(Path(folder).resolve())
    trust_token = _trust_commands.set(bool(trust_commands))
    try:
        yield
    finally:
        _scope.reset(scope_token)
        _trust_commands.reset(trust_token)
