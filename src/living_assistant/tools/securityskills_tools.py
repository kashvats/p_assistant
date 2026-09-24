from __future__ import annotations

from typing import Any

from .base import Tool
from living_assistant.integrations.cybersecurity_skills import CybersecuritySkillsAdapter


def build_security_skills_tools(adapter: CybersecuritySkillsAdapter) -> list[Tool]:
    """Build tool definitions for Anthropic-Cybersecurity-Skills capabilities."""

    def security_search_skills(query: str = "", domain: str = "", limit: int = 10) -> dict[str, Any]:
        """Search the 800+ cybersecurity skills library by keyword, vulnerability, or attack vector."""
        return adapter.search_skills(query=query, domain=domain, limit=limit)

    def security_get_skill(name: str) -> dict[str, Any]:
        """Retrieve complete guidance, detection rules, and remediation steps for a cybersecurity skill."""
        return adapter.get_skill(name_or_path=name)

    def security_audit_prompt(prompt: str) -> dict[str, Any]:
        """Audit text or user input against prompt injection signatures, delimiter escapes, and anomalies."""
        return adapter.audit_prompt_injection(prompt=prompt)

    def security_threat_model(component: str, context: str = "") -> dict[str, Any]:
        """Generate threat modeling scenarios and recommended defenses for a system component."""
        return adapter.threat_model_component(component=component, context=context)

    return [
        Tool(
            "security_search_skills",
            "Search across 800+ defensive cybersecurity and threat modeling skills by keyword, technique, or component.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'prompt injection', 's3 bucket', 'kubernetes rbac', 'jwt')",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter (e.g. 'cybersecurity')",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results to return",
                    },
                },
            },
            security_search_skills,
        ),
        Tool(
            "security_get_skill",
            "Retrieve full instructions, detection patterns, MITRE ATT&CK mappings, and scripts for a security skill.",
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact or partial name of the skill (e.g. 'detecting-ai-model-prompt-injection-attacks')",
                    },
                },
                "required": ["name"],
            },
            security_get_skill,
        ),
        Tool(
            "security_audit_prompt",
            "Audit untrusted text or prompts against OWASP LLM01:2025 prompt injection patterns and structural anomalies.",
            {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The input text or prompt to analyze for injection attacks",
                    },
                },
                "required": ["prompt"],
            },
            security_audit_prompt,
        ),
        Tool(
            "security_threat_model",
            "Retrieve attack scenarios, vulnerability vectors, and recommended defensive skills for an architecture component.",
            {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Target component or technology (e.g. 's3', 'api gateway', 'kubernetes', 'oauth', 'rag')",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional architectural context or operational environment",
                    },
                },
                "required": ["component"],
            },
            security_threat_model,
        ),
    ]
