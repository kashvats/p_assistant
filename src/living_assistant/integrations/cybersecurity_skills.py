from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import threading
from typing import Any
import yaml

from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt Injection Signatures (OWASP LLM01:2025)
# ---------------------------------------------------------------------------
INJECTION_PATTERNS: list[tuple[str, str]] = [
    ("system_prompt_override", r"(?i)\b(ignore|disregard|forget|override|bypass)\b.{0,30}\b(previous|above|prior|all|system|initial)\b.{0,20}\b(instructions?|prompts?|rules?|directives?|context)\b"),
    ("role_play_escape", r"(?i)\b(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are)|simulate\s+being|switch\s+to|enter\s+.{0,10}mode)\b"),
    ("instruction_hijack", r"(?i)\b(do\s+not\s+follow|stop\s+following|new\s+instructions?|instead\s+(do|say|output|respond|print))\b"),
    ("delimiter_escape", r"(?i)(```\s*(system|assistant|user)\s*\n|<\s*/?\s*(system|instruction|prompt)\s*>|\[INST\]|\[/INST\]|<<\s*SYS\s*>>)"),
    ("data_exfiltration", r"(?i)\b(output|reveal|show|display|print|leak|exfiltrate|extract)\b.{0,30}\b(system\s+prompt|instructions?|config|password|secret|api\s*key|token|credentials?)\b"),
    ("encoding_obfuscation", r"(?i)\b(base64|rot13|hex\s*encode|url\s*encode|unicode\s*escape)\b.{0,30}\b(decode|convert|translate|interpret)\b"),
    ("sql_injection_via_prompt", r"(?i)(;\s*(DROP|DELETE|UPDATE|INSERT|ALTER|EXEC)\b|'\s*(OR|AND)\s+['\d]|UNION\s+SELECT)"),
    ("command_injection_via_prompt", r"(?i)(;\s*(rm|cat|wget|curl|bash|sh|python|exec|eval)\b|\|\s*(cat|ls|id|whoami|nc)\b|`[^`]+`)"),
    ("markdown_injection", r"(?i)(\!\[.*?\]\(javascript:|<img\s+[^>]*onerror|<script\b|<iframe\b)"),
    ("context_manipulation", r"(?i)\b(the\s+above\s+(is|was)\s+(a\s+)?(test|joke|example|fake)|end\s+of\s+(system|initial)\s+(message|prompt)|---+\s*(new|real|actual)\s+(instructions?|task))\b"),
    ("multi_language_obfuscation", r"(?i)(ignorar\s+instruc|ignorer\s+les\s+instruc|ignoriere\s+die\s+anweis|alle\s+bisherigen|toutes\s+les\s+instructions\s+pr)"),
    ("token_smuggling", r"(?i)(\u200b|\u200c|\u200d|\ufeff|[\x00-\x08\x0b\x0c\x0e-\x1f])"),
    ("repetitive_override", r"(?i)((?:ignore\s+){3,}|(?:yes\s+){5,}|(?:please\s+){5,})"),
    ("developer_mode", r"(?i)\b(developer\s+mode|DAN\s+mode|jailbreak\s+mode|god\s+mode|sudo\s+mode|admin\s+mode|unrestricted\s+mode)\b"),
    ("prompt_leaking", r"(?i)\b(what\s+(is|are)\s+your\s+(system\s+)?instructions?|repeat\s+(your\s+)?(system\s+)?prompt|show\s+me\s+your\s+(rules|prompt|instructions?))\b"),
    ("few_shot_injection", r"(?i)(user:\s*.{0,50}\nassistant:\s*.{0,50}\nuser:|human:\s*.{0,50}\nassistant:\s*.{0,50}\nhuman:)"),
    ("indirect_injection_marker", r"(?i)(BEGIN\s+INJECTION|INJECTED\s+INSTRUCTION|HIDDEN\s+COMMAND|AI\s*,?\s+please\s+ignore\s+the\s+above)"),
    ("virtual_prompt", r"(?i)(completion:\s*\n|response:\s*\n|answer:\s*\n).{0,50}(ignore|forget|disregard|override)"),
    ("payload_separator", r"[-=]{10,}|[#]{5,}\s*(new|real|actual|override)"),
    ("base64_payload", r"[A-Za-z0-9+/]{40,}={0,2}"),
]

INSTRUCTION_KEYWORDS = {
    "ignore", "disregard", "forget", "override", "bypass", "instead",
    "pretend", "simulate", "act", "roleplay", "imagine", "hypothetically",
    "jailbreak", "unrestricted", "unfiltered", "uncensored", "unlimited",
    "reveal", "output", "print", "show", "display", "leak", "extract",
    "system", "prompt", "instruction", "directive", "rule", "constraint",
}

DELIMITER_CHARS = {"```", "---", "===", "###", "<|", "|>", "[INST]", "[/INST]", "<<SYS>>"}


class CybersecuritySkillsAdapter:
    """Production boundary around the Anthropic-Cybersecurity-Skills repository.

    Provides indexed search across 800+ cybersecurity skills, MITRE ATT&CK / OWASP
    mappings, threat modeling recommendations, and multi-layered prompt injection scanning.
    """

    _lock = threading.RLock()

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path).expanduser().resolve() if path else None
        if not self._path or not self._path.is_dir():
            default_candidate = Path("external-components/Anthropic-Cybersecurity-Skills").resolve()
            if default_candidate.is_dir():
                self._path = default_candidate

        self._index: dict[str, Any] | None = None
        self._skills_list: list[dict[str, Any]] = []
        self._compiled_regexes = [(name, re.compile(pat)) for name, pat in INJECTION_PATTERNS]

    # ------------------------------------------------------------------
    # Availability & Catalog Info
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Check if checkout and index/skills directory are present."""
        if not self._path or not self._path.is_dir():
            return False
        return (self._path / "index.json").is_file() or (self._path / "skills").is_dir()

    def _ensure_index(self) -> None:
        if self._index is not None:
            return
        with self._lock:
            if self._index is not None:
                return
            if self._path and (self._path / "index.json").is_file():
                try:
                    data = json.loads((self._path / "index.json").read_text(encoding="utf-8"))
                    self._index = data
                    self._skills_list = data.get("skills", [])
                    return
                except Exception as exc:
                    logger.warning("Failed to load index.json: %s", exc)

            # Fallback to scanning skills/ directory
            skills: list[dict[str, Any]] = []
            if self._path and (self._path / "skills").is_dir():
                for skill_dir in (self._path / "skills").iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file():
                        name = skill_dir.name
                        desc = name.replace("-", " ")
                        skills.append({
                            "name": name,
                            "description": desc,
                            "domain": "cybersecurity",
                            "path": f"skills/{name}",
                        })
            self._index = {
                "version": "1.1.0",
                "total_skills": len(skills),
                "skills": skills,
            }
            self._skills_list = skills

    def get_catalog_info(self) -> dict[str, Any]:
        """Get summary info about the loaded cybersecurity skills catalog."""
        self._ensure_index()
        assert self._index is not None
        return {
            "ok": True,
            "version": self._index.get("version", "1.0.0"),
            "total_skills": len(self._skills_list),
            "repository": self._index.get("repository", "https://github.com/mukul975/Anthropic-Cybersecurity-Skills"),
        }

    # ------------------------------------------------------------------
    # Skill Discovery & Retrieval
    # ------------------------------------------------------------------

    def search_skills(self, query: str, domain: str = "", limit: int = 10) -> dict[str, Any]:
        """Search cybersecurity skills by keyword, attack vector, or technique."""
        self._ensure_index()
        clean_query = (query or "").strip().lower()
        clean_domain = (domain or "").strip().lower()

        if not clean_query and not clean_domain:
            return {
                "ok": True,
                "count": min(len(self._skills_list), limit),
                "skills": self._skills_list[:limit],
            }

        terms = [t for t in re.split(r"[\s\-_]+", clean_query) if t]

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in self._skills_list:
            item_domain = str(item.get("domain", "")).lower()
            if clean_domain and clean_domain not in item_domain:
                continue

            name = str(item.get("name", "")).lower()
            desc = str(item.get("description", "")).lower()

            score = 0.0
            if clean_query:
                # Exact full phrase match
                if clean_query in name:
                    score += 5.0
                elif clean_query in desc:
                    score += 3.0

                # Token matching
                name_words = set(re.split(r"[\s\-_]+", name))
                desc_words = set(re.split(r"[\s\-_]+", desc))
                for term in terms:
                    if term in name_words:
                        score += 2.0
                    elif any(term in w for w in name_words):
                        score += 1.0
                    if term in desc_words:
                        score += 0.5

            if score > 0.0 or not clean_query:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item for _, item in scored[:limit]]
        return {
            "ok": True,
            "count": len(results),
            "skills": results,
        }

    def get_skill(self, name_or_path: str) -> dict[str, Any]:
        """Retrieve full details, frontmatter metadata, and instructions for a skill."""
        if not self._path:
            return {"ok": False, "error": "Cybersecurity skills directory not configured"}

        clean_name = name_or_path.strip().replace("skills/", "")
        skill_dir = self._path / "skills" / clean_name
        skill_file = skill_dir / "SKILL.md"

        if not skill_file.is_file():
            # Try finding by exact match in skills directory
            candidates = list((self._path / "skills").glob(f"*{clean_name}*"))
            if candidates and candidates[0].is_dir() and (candidates[0] / "SKILL.md").is_file():
                skill_dir = candidates[0]
                skill_file = skill_dir / "SKILL.md"
            else:
                return {"ok": False, "error": f"Skill not found: {name_or_path}"}

        content = skill_file.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        metadata: dict[str, Any] = {}
        instructions = content
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                instructions = parts[2].strip()
            except Exception:
                pass

        scripts = []
        if (skill_dir / "scripts").is_dir():
            scripts = [s.name for s in (skill_dir / "scripts").iterdir() if s.is_file()]

        references = []
        if (skill_dir / "references").is_dir():
            references = [r.name for r in (skill_dir / "references").iterdir() if r.is_file()]

        return {
            "ok": True,
            "name": metadata.get("name", skill_dir.name),
            "description": metadata.get("description", ""),
            "domain": metadata.get("domain", "cybersecurity"),
            "subdomain": metadata.get("subdomain", ""),
            "tags": metadata.get("tags", []),
            "version": metadata.get("version", "1.0.0"),
            "mitre_attack": metadata.get("mitre_attack", []),
            "nist_csf": metadata.get("nist_csf", []),
            "atlas_techniques": metadata.get("atlas_techniques", []),
            "d3fend_techniques": metadata.get("d3fend_techniques", []),
            "scripts": scripts,
            "references": references,
            "instructions": redact_secrets(instructions[:15000]),
        }

    # ------------------------------------------------------------------
    # Prompt Injection Defense (OWASP LLM01:2025)
    # ------------------------------------------------------------------

    def audit_prompt_injection(self, prompt: str) -> dict[str, Any]:
        """Audit input text against prompt injection signatures and structural anomalies."""
        text = str(prompt or "")
        if not text.strip():
            return {
                "ok": True,
                "flagged": False,
                "risk_level": "low",
                "score": 0.0,
                "matches": [],
                "patterns_detected": [],
            }

        # 1. Regex signature matching
        matches: list[str] = []
        for name, pattern in self._compiled_regexes:
            if pattern.search(text):
                matches.append(name)

        regex_score = min(1.0, len(matches) * 0.3)

        # 2. Heuristic scoring
        words = text.split()
        word_count = max(len(words), 1)

        instruction_count = sum(1 for w in words if w.lower().strip(".,!?;:") in INSTRUCTION_KEYWORDS)
        instruction_density = min(1.0, (instruction_count / word_count) * 2.5)

        delimiter_count = sum(1 for d in DELIMITER_CHARS if d in text)
        delimiter_presence = min(1.0, delimiter_count * 0.35)

        upper_chars = sum(1 for c in text if c.isupper())
        alpha_chars = max(sum(1 for c in text if c.isalpha()), 1)
        cap_ratio = upper_chars / alpha_chars
        cap_anomaly = 1.0 if cap_ratio > 0.65 and len(text) > 20 else cap_ratio * 0.3

        zwc_count = sum(1 for c in text if ord(c) in (0x200B, 0x200C, 0x200D, 0xFEFF) or 0x00 <= ord(c) <= 0x08)
        unicode_anomaly = min(1.0, zwc_count * 0.5)

        heuristic_score = min(
            1.0,
            (instruction_density * 0.4)
            + (delimiter_presence * 0.25)
            + (unicode_anomaly * 0.25)
            + (cap_anomaly * 0.1),
        )

        composite_score = min(1.0, (regex_score * 0.7) + (heuristic_score * 0.3))
        flagged = (len(matches) > 0) or (composite_score >= 0.35)

        if composite_score >= 0.7 or len(matches) >= 2:
            risk = "critical"
        elif composite_score >= 0.4 or len(matches) == 1:
            risk = "high"
        elif composite_score >= 0.2:
            risk = "medium"
        else:
            risk = "low"

        return {
            "ok": True,
            "flagged": flagged,
            "risk_level": risk,
            "score": round(composite_score, 3),
            "patterns_detected": matches,
            "heuristics": {
                "instruction_density": round(instruction_density, 3),
                "delimiter_presence": round(delimiter_presence, 3),
                "unicode_anomaly": round(unicode_anomaly, 3),
            },
        }

    # ------------------------------------------------------------------
    # Threat Modeling & MITRE ATT&CK Mapping
    # ------------------------------------------------------------------

    def threat_model_component(self, component: str, context: str = "") -> dict[str, Any]:
        """Retrieve threat scenarios, attack vectors, and defensive skills for a component."""
        comp = (component or "").strip().lower()
        search_res = self.search_skills(query=comp, limit=12)
        skills = search_res.get("skills", [])

        # Categorize skills into attack/exploit vs audit/defend
        attacks: list[dict[str, str]] = []
        defenses: list[dict[str, str]] = []
        for s in skills:
            name = s.get("name", "")
            desc = s.get("description", "")
            entry = {"name": name, "description": desc[:180]}
            if any(marker in name for marker in ("exploiting", "attacking", "bypassing", "abusing", "coercing")):
                attacks.append(entry)
            else:
                defenses.append(entry)

        return {
            "ok": True,
            "component": component,
            "context": context,
            "recommended_defenses": defenses[:6],
            "attack_scenarios": attacks[:6],
            "total_related_skills": len(skills),
        }
