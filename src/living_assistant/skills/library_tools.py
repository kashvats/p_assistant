"""Chat tools for SKILL.md skills: find, install, read, learn, edit, remove and restore."""
from __future__ import annotations

import functools

from typing import Callable

from living_assistant.security.security_utils import redact_secrets
from living_assistant.skills.library import SkillError, SkillLibrary, skillhub_search
from living_assistant.tools.base import Tool


def build_skill_library_tools(library: SkillLibrary, *, approval=None,
                              read_text: Callable[[str], str] | None = None,
                              fetch_text: Callable[[str], str] | None = None,
                              session_text: Callable[[str], str] | None = None) -> list[Tool]:
    """``read_text(path)`` reads a workspace file, ``fetch_text(url)`` a web page as text, and
    ``session_text(session_id)`` the current conversation - the material ``skill_learn`` can learn from."""

    def safe(fn):
        @functools.wraps(fn)  # keeps the signature: the orchestrator passes _session_id to tools that take it
        def wrapper(**kwargs):
            try:
                return fn(**kwargs)
            except SkillError as exc:
                return {"ok": False, "error": str(exc)}
            except Exception as exc:
                return {"ok": False, "error": redact_secrets(exc, 600)}
        return wrapper

    def approved(action: str, reason: str) -> dict | None:
        if approval is None:
            return None
        decision = approval.request(action, reason, "write")
        if decision.get("allowed"):
            return None
        return {"ok": False, "approval_required": True, "approval_id": decision.get("approval_id"),
                "error": decision.get("message") or "Approval is required; approve it, then retry the same action."}

    @safe
    def skill_list(include_trash: bool = False):
        rows = library.list()
        out = {"ok": True, "skills": [{k: r.get(k) for k in ("name", "description", "builtin", "valid", "error")} for r in rows]}
        if include_trash:
            out["trash"] = [{"trash_name": t["trash_name"], "description": t.get("description")} for t in library.trash()]
        return out

    @safe
    def skill_find(query: str, where: str = "both", limit: int = 8):
        out: dict = {"ok": True, "query": query}
        if where in ("installed", "both"):
            out["installed"] = [{"name": r["name"], "description": r["description"]} for r in library.relevant(query, limit)]
        if where in ("skillhub", "both"):
            try:
                out["skillhub"] = skillhub_search(query, limit)
                out["install_with"] = "skill_install(source=<the result's source>)"
            except SkillError as exc:
                out["skillhub_error"] = str(exc)
        return out

    @safe
    def skill_install(source: str, subpath: str = "", name: str = "", replace: bool = False, preview: bool = False):
        if preview:
            return {"ok": True, "would_install": library.inspect(source, subpath, name)}
        if replace:
            blocked = approved(f"Replace installed skill(s) from {source}", "Overwrites an installed skill with a new copy.")
            if blocked:
                return blocked
        installed = library.install(source, subpath, name, force=replace)
        return {"ok": True, "installed": installed,
                "note": "Installing copied files only; nothing from the package was run. Use skill_read to load one."}

    @safe
    def skill_read(name: str, file: str = ""):
        return library.read(name, file)

    @safe
    def skill_learn(name: str, goal: str = "", material: str = "", path: str = "", url: str = "",
                    from_conversation: bool = False, replace: bool = False, _session_id: str | None = None):
        parts = [material] if material else []
        if path:
            if read_text is None:
                return {"ok": False, "error": "Reading files is unavailable here."}
            parts.append(f"[file {path}]\n{read_text(path)}")
        if url:
            if fetch_text is None:
                return {"ok": False, "error": "Fetching web pages is unavailable here."}
            parts.append(f"[page {url}]\n{fetch_text(url)}")
        if from_conversation:
            if session_text is None or not _session_id:
                return {"ok": False, "error": "There is no conversation to learn from here."}
            parts.append(f"[the conversation so far]\n{session_text(_session_id)}")
        if replace:
            blocked = approved(f"Replace skill {name} with a newly learned version", "Overwrites an installed skill.")
            if blocked:
                return blocked
        learned = library.learn(name, goal, "\n\n".join(p for p in parts if p), force=replace)
        return {"ok": True, **learned,
                "note": "Saved. Tell the user what the skill does and that they can edit or remove it."}

    @safe
    def skill_edit(name: str, description: str = "", instructions: str = "", file: str = "", content: str = ""):
        if file:
            return library.edit(name, file=file, content=content)
        if not (description or instructions):
            return {"ok": False, "error": "Give a new description, new instructions, or a file and its content."}
        return library.edit(name, description=description or None, instructions=instructions or None)

    @safe
    def skill_remove(name: str):
        blocked = approved(f"Remove skill {name}", "Moves the skill to the skill trash; skill_restore brings it back.")
        if blocked:
            return blocked
        return {"ok": True, **library.remove(name)}

    @safe
    def skill_restore(trash_name: str):
        return {"ok": True, **library.restore(trash_name)}

    obj = {"type": "object"}
    s = {"type": "string"}
    return [
        Tool("skill_list", "List installed SKILL.md skills (name and what each is for); include_trash also lists removed ones.",
             {**obj, "properties": {"include_trash": {"type": "boolean", "default": False}}}, skill_list),
        Tool("skill_find", "Find a skill for a task: among installed skills and/or on the SkillHub skill market. "
                           "where: installed | skillhub | both.",
             {**obj, "properties": {"query": s, "where": {"type": "string", "enum": ["installed", "skillhub", "both"],
                                                          "default": "both"},
                                    "limit": {"type": "integer", "default": 8}}, "required": ["query"]}, skill_find),
        Tool("skill_install", "Install skills (SKILL.md format) from a local folder/SKILL.md/ZIP/TAR, a GitHub repo or "
                              "sub-folder link, a git URL, a download URL, or SkillHub (skillhub:<slug> or a skillhub.cn "
                              "page). preview=true only shows what would be installed. replace=true overwrites an "
                              "installed skill (asks for approval).",
             {**obj, "properties": {"source": s, "subpath": s, "name": s, "replace": {"type": "boolean", "default": False},
                                    "preview": {"type": "boolean", "default": False}}, "required": ["source"]}, skill_install),
        Tool("skill_read", "Load an installed skill's instructions (call this before doing a task a skill covers), or "
                           "one of its resource files with file=<relative path>.",
             {**obj, "properties": {"name": s, "file": s}, "required": ["name"]}, skill_read),
        Tool("skill_learn", "Learn a new skill: turn material into a reusable SKILL.md skill. Material can be text, a "
                            "workspace file (path), a web page (url), and/or this conversation (from_conversation=true, "
                            "e.g. 'save what we just did as a skill'). goal says what the skill should let you do.",
             {**obj, "properties": {"name": s, "goal": s, "material": s, "path": s, "url": s,
                                    "from_conversation": {"type": "boolean", "default": False},
                                    "replace": {"type": "boolean", "default": False}}, "required": ["name"]}, skill_learn),
        Tool("skill_edit", "Change an installed skill: its description, its instructions, or one file (file + content).",
             {**obj, "properties": {"name": s, "description": s, "instructions": s, "file": s, "content": s},
              "required": ["name"]}, skill_edit),
        Tool("skill_remove", "Remove an installed skill (moved to the skill trash, restorable). Asks for approval.",
             {**obj, "properties": {"name": s}, "required": ["name"]}, skill_remove),
        Tool("skill_restore", "Restore a removed skill from the skill trash (names from skill_list include_trash=true).",
             {**obj, "properties": {"trash_name": s}, "required": ["trash_name"]}, skill_restore),
    ]
