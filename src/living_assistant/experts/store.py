"""Agents, agent templates and teams.

- **Templates**: Octop's expert library (``experts/library``, MIT, TencentCloud/Octop): each has a
  manifest (name, description, icon, colour, welcome text, quick prompts), persona files and
  bundled SKILL.md skills. "Hiring" one creates an agent from it and installs its skills.
- **Agents**: a name, a purpose, an optional MBTI persona, instructions, the skills it should use,
  and quick prompts. Chatting with an agent puts its persona and instructions in front of every turn.
- **Teams** ("agent companies"): a lead plus member agents. The lead plans, hands parts of the work
  to members with ``team_ask`` (each member works with its own persona and skills) and combines the
  results.
"""
from __future__ import annotations

import json
import re
import threading
import time
from importlib import resources
from pathlib import Path
from typing import Any

from living_assistant.core.storage_utils import atomic_write_json
from living_assistant.experts.mbti_profiles import get_all_profiles, get_profile

DEFAULT_AGENT_ID = "assistant"
MAX_INSTRUCTIONS = 12_000
_FRONTMATTER = re.compile(r"^﻿?---\s*\n.*?\n---\s*\n", re.DOTALL)


def library_root() -> Path:
    return Path(str(resources.files("living_assistant").joinpath("experts", "library")))


def _en(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("en") or next(iter(value.values()), "") or "")
    return str(value or "")


def _slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:40] or "agent"
    return base


def persona_text(code: str | None) -> str:
    profile = get_profile(code or "") if code else None
    if profile is None:
        return ""
    b = profile.behavior
    return (f"Personality ({profile.code}, {profile.name_en}): {profile.summary_en}. Traits: {profile.descriptors_en}.\n"
            f"- Answer style: {b.answer_style}\n- Casual chat: {b.casual_chat}\n- Conflict: {b.conflict}\n"
            f"- Creativity: {b.creativity}\n- Emotion: {b.emotion}\n- Planning: {b.planning}")


def mbti_catalog() -> list[dict]:
    return [{"code": p.code, "name": p.name_en, "summary": p.summary_en, "traits": p.descriptors_en, "color": p.color}
            for p in get_all_profiles()]


class ExpertStore:
    def __init__(self, path: Path, *, library: Path | None = None, skill_library=None):
        self.path = Path(path)
        self.library = library if library is not None else library_root()
        self.skills = skill_library
        self._lock = threading.RLock()
        self._templates: list[dict] | None = None

    # ---- storage ---------------------------------------------------------------------------

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data.setdefault("agents", {})
        data.setdefault("teams", {})
        data.setdefault("conversations", {})
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path, data)

    # ---- templates -------------------------------------------------------------------------

    def templates(self) -> list[dict]:
        if self._templates is None:
            out = []
            for folder in sorted(self.library.iterdir()) if self.library.is_dir() else []:
                manifest = folder / "manifest.json"
                if not manifest.is_file():
                    continue
                try:
                    m = json.loads(manifest.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                skills_dir = folder / "skills"
                out.append({
                    "id": folder.name, "name": _en(m.get("label")) or folder.name, "description": _en(m.get("description")),
                    "welcome": _en(m.get("welcome_message")), "icon": m.get("icon_name") or "bot", "color": m.get("color") or "#6366f1",
                    "quick_prompts": [{"title": _en(q.get("title")), "description": _en(q.get("description")), "prompt": _en(q.get("prompt"))}
                                      for q in m.get("quick_prompts") or [] if isinstance(q, dict)][:6],
                    "skills": sorted(d.name for d in skills_dir.iterdir() if (d / "SKILL.md").is_file()) if skills_dir.is_dir() else [],
                    "prompt_files": [f for f in m.get("prompt_files") or [] if (folder / f).is_file()],
                })
            self._templates = out
        return self._templates

    def template(self, template_id: str) -> dict:
        for t in self.templates():
            if t["id"] == template_id:
                return t
        raise KeyError(f"No agent template {template_id!r}.")

    def _template_instructions(self, t: dict) -> str:
        parts = []
        for name in t["prompt_files"]:
            text = (self.library / t["id"] / name).read_text(encoding="utf-8", errors="replace")
            parts.append(_FRONTMATTER.sub("", text, count=1).strip())
        return "\n\n".join(p for p in parts if p)[:MAX_INSTRUCTIONS]

    # ---- agents ----------------------------------------------------------------------------

    def _default(self) -> dict:
        return {"id": DEFAULT_AGENT_ID, "name": "Assistant", "description": "Your everyday helper for small tasks.",
                "icon": "sparkles", "color": "#6366f1", "mbti": "", "instructions": "", "skills": [], "builtin": True,
                "welcome": "What can I do for you?", "quick_prompts": [
                    {"title": "Summarize a document", "description": "Attach a file or paste text", "prompt": "Summarize this for me:\n\n"},
                    {"title": "Find something on the web", "description": "Current facts, with sources", "prompt": "Look up "},
                    {"title": "Organize my files", "description": "Sort, rename or clean a folder", "prompt": "Help me organize the folder "},
                ]}

    def agents(self) -> list[dict]:
        with self._lock:
            mine = sorted(self._load()["agents"].values(), key=lambda a: a.get("created_at", 0))
        return [self._default()] + mine

    def agent(self, agent_id: str) -> dict:
        if agent_id in ("", DEFAULT_AGENT_ID, None):
            return self._default()
        with self._lock:
            found = self._load()["agents"].get(agent_id)
        if not found:
            raise KeyError(f"No agent {agent_id!r}.")
        return found

    def _new_id(self, data: dict, name: str) -> str:
        base = _slug(name)
        candidate, n = base, 2
        while candidate in data["agents"] or candidate in data["teams"] or candidate == DEFAULT_AGENT_ID:
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    def save_agent(self, fields: dict, agent_id: str | None = None) -> dict:
        name = str(fields.get("name") or "").strip()[:80]
        if not name:
            raise ValueError("An agent needs a name.")
        mbti = str(fields.get("mbti") or "").upper().strip()
        if mbti and get_profile(mbti) is None:
            raise ValueError(f"Unknown personality type {mbti!r}.")
        with self._lock:
            data = self._load()
            if agent_id:
                if agent_id == DEFAULT_AGENT_ID:
                    raise ValueError("The default assistant cannot be changed; create your own agent instead.")
                if agent_id not in data["agents"]:
                    raise KeyError(f"No agent {agent_id!r}.")
                current = data["agents"][agent_id]
            else:
                current = {"id": self._new_id(data, name), "created_at": time.time()}
            current.update({
                "name": name, "description": str(fields.get("description") or "").strip()[:500],
                "icon": str(fields.get("icon") or current.get("icon") or "bot")[:40],
                "color": str(fields.get("color") or current.get("color") or "#6366f1")[:20], "mbti": mbti,
                "instructions": str(fields.get("instructions") or "")[:MAX_INSTRUCTIONS],
                "skills": [str(s) for s in fields.get("skills") or []][:40],
                "welcome": str(fields.get("welcome") or current.get("welcome") or "")[:300],
                "quick_prompts": [q for q in fields.get("quick_prompts") or current.get("quick_prompts") or [] if isinstance(q, dict)][:6],
                "template": fields.get("template") or current.get("template"), "updated_at": time.time(),
            })
            data["agents"][current["id"]] = current
            self._save(data)
            return current

    def hire(self, template_id: str, name: str = "") -> dict:
        """Create an agent from a template and install the skills it brings."""
        t = self.template(template_id)
        installed, skipped = [], []
        if self.skills is not None:
            for skill in t["skills"]:
                try:
                    self.skills.install(str(self.library / t["id"] / "skills" / skill))
                    installed.append(skill)
                except Exception as exc:  # already installed (keep the user's copy) or invalid
                    skipped.append({"skill": skill, "reason": str(exc)[:200]})
        agent = self.save_agent({"name": name or t["name"], "description": t["description"], "icon": t["icon"],
                                 "color": t["color"], "instructions": self._template_instructions(t), "skills": t["skills"],
                                 "welcome": t["welcome"], "quick_prompts": t["quick_prompts"], "template": t["id"]})
        return {**agent, "skills_installed": installed, "skills_kept": skipped}

    def delete_agent(self, agent_id: str) -> dict:
        with self._lock:
            data = self._load()
            if agent_id not in data["agents"]:
                raise KeyError(f"No agent {agent_id!r}.")
            removed = data["agents"].pop(agent_id)
            for team in data["teams"].values():
                team["members"] = [m for m in team.get("members", []) if m != agent_id]
            self._save(data)
        return {"ok": True, "deleted": removed["id"]}

    # ---- teams -----------------------------------------------------------------------------

    def teams(self) -> list[dict]:
        with self._lock:
            return sorted(self._load()["teams"].values(), key=lambda t: t.get("created_at", 0))

    def team(self, team_id: str) -> dict:
        with self._lock:
            found = self._load()["teams"].get(team_id)
        if not found:
            raise KeyError(f"No team {team_id!r}.")
        return found

    def save_team(self, fields: dict, team_id: str | None = None) -> dict:
        name = str(fields.get("name") or "").strip()[:80]
        if not name:
            raise ValueError("A team needs a name.")
        members = [str(m) for m in fields.get("members") or []]
        with self._lock:
            data = self._load()
            known = set(data["agents"]) | {DEFAULT_AGENT_ID}
            unknown = [m for m in members if m not in known]
            if unknown:
                raise ValueError(f"Unknown team member(s): {', '.join(unknown)}")
            if len(members) < 2:
                raise ValueError("A team needs at least two member agents.")
            if team_id:
                if team_id not in data["teams"]:
                    raise KeyError(f"No team {team_id!r}.")
                current = data["teams"][team_id]
            else:
                current = {"id": self._new_id(data, name), "created_at": time.time()}
            current.update({"name": name, "description": str(fields.get("description") or "").strip()[:500],
                            "icon": str(fields.get("icon") or "users")[:40], "color": str(fields.get("color") or "#0ea5e9")[:20],
                            "lead_instructions": str(fields.get("lead_instructions") or "")[:MAX_INSTRUCTIONS],
                            "members": list(dict.fromkeys(members))[:8], "updated_at": time.time()})
            data["teams"][current["id"]] = current
            self._save(data)
            return current

    def delete_team(self, team_id: str) -> dict:
        with self._lock:
            data = self._load()
            if team_id not in data["teams"]:
                raise KeyError(f"No team {team_id!r}.")
            data["teams"].pop(team_id)
            self._save(data)
        return {"ok": True, "deleted": team_id}

    # ---- starters -------------------------------------------------------------------------

    STARTER_AGENTS = [
        {"name": "Writer", "icon": "edit", "color": "#ec4899", "mbti": "ENFP",
         "description": "Writes and polishes emails, messages, reports and meeting notes.",
         "skills": ["email-writer", "meeting-notes", "weekly-report"], "welcome": "What should we write?","quick_prompts": [{"title": 'Draft an email', "description": "Tell me who it's to and what you need", "prompt": 'Write an email to '}, {"title": 'Meeting notes', "description": 'Paste notes or attach a transcript', "prompt": 'Turn these meeting notes into minutes with action items:\n\n'}, {"title": 'Weekly report', "description": 'From your notes or todos', "prompt": 'Write my weekly report from this:\n\n'}],
         "instructions": "Write clearly and briefly in the user's voice. Show drafts; never send anything yourself."},
        {"name": "Researcher", "icon": "globe", "color": "#0ea5e9", "mbti": "INTP",
         "description": "Looks things up on the web and answers with sources.",
         "skills": ["web-fact-check"], "welcome": "What should I find out?","quick_prompts": [{"title": 'Look something up', "description": 'Current facts with sources', "prompt": 'Find out '}, {"title": 'Check a claim', "description": 'Is it true? With sources', "prompt": 'Is it true that '}, {"title": 'Compare options', "description": 'Prices, features, reviews', "prompt": 'Compare these options for me: '}],
         "instructions": "Answer only from pages you actually read, cite them, and say when sources disagree or are old."},
        {"name": "Coder", "icon": "code", "color": "#10b981", "mbti": "ISTJ",
         "description": "Writes, fixes and explains code in your projects.",
         "skills": ["code-review"], "welcome": "Which code are we working on?","quick_prompts": [{"title": 'Fix a bug', "description": 'Describe it and the file', "prompt": 'There is a bug in '}, {"title": 'Explain code', "description": 'Point me to a file', "prompt": 'Explain what this code does: '}, {"title": 'Review my code', "description": 'Bugs, security, readability', "prompt": 'Review the code in '}],
         "instructions": "Read the relevant files before changing them. Make the smallest change that works and run the "
                         "project's tests or the code to check it."},
        {"name": "Reviewer", "icon": "shield", "color": "#f59e0b", "mbti": "INTJ",
         "description": "Checks work for mistakes - code, documents, facts - before it is called done.",
         "skills": ["code-review", "web-fact-check"], "welcome": "What should I check?","quick_prompts": [{"title": 'Check a document', "description": 'Mistakes, gaps, facts', "prompt": 'Check this document for mistakes:\n\n'}, {"title": 'Review code', "description": 'Before you merge it', "prompt": 'Review the changes in '}, {"title": 'Fact-check', "description": 'With sources', "prompt": 'Fact-check this:\n\n'}],
         "instructions": "Be specific: name each problem, where it is, why it matters and how to fix it. Say plainly when "
                         "something is fine."},
        {"name": "Planner", "icon": "calendar", "color": "#8b5cf6", "mbti": "ESTJ",
         "description": "Breaks a goal into steps, schedules them and keeps track.",
         "skills": [], "welcome": "What do you want to get done?","quick_prompts": [{"title": 'Plan a goal', "description": 'Steps, order and dates', "prompt": 'Help me plan: '}, {"title": 'Plan my week', "description": 'From my todos and calendar', "prompt": 'Plan my week. My priorities are: '}, {"title": 'Break down a project', "description": 'Into small tasks', "prompt": 'Break this project into tasks: '}],
         "instructions": "Turn goals into short, ordered steps with owners and dates. Offer to add them as todos or "
                         "calendar entries (those ask for approval)."},
        {"name": "Organizer", "icon": "folder", "color": "#64748b", "mbti": "ISFJ",
         "description": "Tidies folders: sorts, renames and finds duplicates, always asking first.",
         "skills": ["file-organizer"], "welcome": "Which folder should I tidy?", "instructions": "", "quick_prompts": [{"title": 'Tidy a folder', "description": 'Sort files into folders', "prompt": 'Tidy up the folder '}, {"title": 'Find duplicates', "description": 'Same files twice', "prompt": 'Find duplicate files in '}, {"title": 'What takes space?', "description": 'Biggest files and folders', "prompt": 'What takes the most space in '}]},
    ]
    STARTER_TEAMS = [
        {"name": "Software company", "color": "#10b981", "members": ["planner", "coder", "reviewer"],
         "description": "Plans a feature, builds it and reviews it before calling it done.",
         "lead_instructions": "1) Ask the Planner for a short plan. 2) Give the Coder one step at a time with the file "
                              "paths and the plan. 3) Have the Reviewer check the result; send fixes back to the Coder. "
                              "Report what was built, what was tested and anything left open."},
        {"name": "Content studio", "color": "#ec4899", "members": ["researcher", "writer", "reviewer"],
         "description": "Researches a topic, writes it up and fact-checks it.",
         "lead_instructions": "Have the Researcher gather facts with sources first, then the Writer draft from them, then "
                              "the Reviewer check facts and clarity. Keep the sources in the final text."},
        {"name": "Office team", "color": "#7c3aed", "members": ["writer", "planner", "organizer"],
         "description": "Everyday office work: emails, reports, schedules and tidy files.",
         "lead_instructions": "Send writing to the Writer, scheduling and task lists to the Planner and folder work to "
                              "the Organizer. Combine their results into one short reply."},
    ]

    def ensure_starters(self) -> list[str]:
        """Create the starter agents and teams once (first run). Deleting them later is respected."""
        with self._lock:
            data = self._load()
            if data.get("starters_seeded"):
                # starters made by an earlier version: give them the starter prompts they lack
                specs = {spec["name"]: spec for spec in self.STARTER_AGENTS}
                changed = False
                for agent in data["agents"].values():
                    spec = specs.get(agent.get("name"))
                    if spec and not agent.get("quick_prompts") and spec.get("quick_prompts"):
                        agent["quick_prompts"] = spec["quick_prompts"]
                        changed = True
                if changed:
                    self._save(data)
                return []
            made, ids = [], {}
            for spec in self.STARTER_AGENTS:
                agent = self.save_agent(spec)
                ids[spec["name"].lower()] = agent["id"]
                made.append(agent["id"])
            for spec in self.STARTER_TEAMS:
                members = [ids[m] for m in spec["members"] if m in ids]
                if len(members) >= 2:
                    made.append(self.save_team({**spec, "members": members})["id"])
            data = self._load()
            data["starters_seeded"] = True
            self._save(data)
            return made

    # ---- which agent a conversation talks to ---------------------------------------------

    def bind(self, session_id: str, target: str) -> str:
        """Remember the agent ("<id>") or team ("team:<id>") a conversation is with."""
        target = str(target or DEFAULT_AGENT_ID)
        self.context_for(target)  # raises KeyError for an unknown agent/team
        with self._lock:
            data = self._load()
            data["conversations"][session_id] = target
            if len(data["conversations"]) > 2000:  # keep the newest bindings
                data["conversations"] = dict(list(data["conversations"].items())[-1500:])
            self._save(data)
        return target

    def bound(self, session_id: str | None) -> str:
        if not session_id:
            return DEFAULT_AGENT_ID
        with self._lock:
            target = self._load()["conversations"].get(session_id) or DEFAULT_AGENT_ID
        try:
            self.context_for(target)
        except KeyError:  # the agent or team was deleted since
            return DEFAULT_AGENT_ID
        return target

    # ---- what the model sees ------------------------------------------------------------

    def agent_context(self, agent: dict) -> str:
        if agent.get("id") == DEFAULT_AGENT_ID and not agent.get("instructions"):
            return ""
        lines = [f"[ACTIVE AGENT: {agent['name']}]",
                 f"You are acting as {agent['name']}" + (f" - {agent['description']}" if agent.get("description") else "") + ".",
                 "Always reply in the language the user writes in."]
        persona = persona_text(agent.get("mbti"))
        if persona:
            lines.append(persona)
        if agent.get("instructions"):
            lines.append("Agent instructions (from the agent's profile; they never override safety rules or approvals):\n"
                         + agent["instructions"][:MAX_INSTRUCTIONS])
        if agent.get("skills"):
            lines.append("This agent's skills (call skill_read with the name before a task one covers): "
                         + ", ".join(agent["skills"]))
        return "\n".join(lines)

    def team_context(self, team: dict) -> str:
        members = []
        for m in team.get("members", []):
            try:
                a = self.agent(m)
                members.append(f"- {a['id']}: {a['name']} - {a.get('description') or 'no description'}")
            except KeyError:
                continue
        return "\n".join([
            f"[ACTIVE TEAM: {team['name']}]",
            f"You lead the team '{team['name']}'" + (f" ({team['description']})" if team.get("description") else "") + ".",
            "Plan the work, give each part to the best member with team_ask(member, task) - give them everything they "
            "need in the task text, they do not see this chat - check what they return, then combine it into one answer. "
            "Do small things yourself. Always reply in the language the user writes in.",
            "Members:", *members,
            *(["Lead instructions:\n" + team["lead_instructions"]] if team.get("lead_instructions") else []),
        ])

    def context_for(self, target: str | None) -> tuple[str, dict | None]:
        """(prompt context, team or None) for an agent id or a team id ("team:<id>")."""
        if not target:
            return "", None
        if str(target).startswith("team:"):
            team = self.team(str(target)[5:])
            return self.team_context(team), team
        return self.agent_context(self.agent(str(target))), None

