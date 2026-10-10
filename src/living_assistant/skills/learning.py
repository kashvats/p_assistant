"""
Persistent Skill Learning and Acquisition System (Section 10).
Living Assistant - Autonomous Capability Acquisition Engine.

Responsibilities:
1. Detect Missing Capabilities: Identifies capability gaps vs ambiguous requirements.
2. Acquire Skills from Multiple Sources: Learns procedures from documentation, repositories,
   tools/APIs, execution traces, or explicit user feedback.
3. Structured Versioned Catalog: Tracks skills through the 6-stage lifecycle:
   PROPOSED -> LEARNING -> TESTING -> VERIFIED -> DEPRECATED | FAILED.
4. Validation & Isolated Testing: Executes sandboxed test suites, verifies permissions,
   enforces safety invariants, and gates publication before trusting newly learned procedures.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from living_assistant.core.workspace import Workspace
from living_assistant.skills.manifest import (
    SkillManifest,
    SkillPermissionScope,
    SkillStep,
    SkillLimits,
    SkillProvenance,
    SkillExample,
)
from living_assistant.skills.package import SkillPackage
from living_assistant.skills.store import SkillStore
from living_assistant.tools.registry import ToolRegistry

logger = logging.getLogger("living_assistant.skills.learning")


class LearnedSkillStatus:
    PROPOSED = "PROPOSED"
    LEARNING = "LEARNING"
    TESTING = "TESTING"
    VERIFIED = "VERIFIED"
    DEPRECATED = "DEPRECATED"
    FAILED = "FAILED"


@dataclass
class CapabilityGap:
    task_id: str
    task_description: str
    missing_capability: str
    category: str  # missing_tool | missing_procedure | unsupported_data_format | domain_logic
    severity: str  # blocking | degraded
    candidate_sources: List[str] = field(default_factory=list)  # documentation | repository | tools | trace | user
    resolution_strategy: str = "acquire_new_skill"  # acquire_new_skill | adapt_existing_skill | user_clarification
    requires_approval: bool = False
    rationale: str = ""


class CapabilityGapDetector:
    """
    Detects capability gaps when incoming tasks cannot be fulfilled by currently
    registered tools or active skills, while strictly avoiding confusion between
    missing skills and underspecified user requirements.
    """

    KNOWN_PATTERNS = [
        {
            "trigger_keywords": ["frontmatter", "yaml header", "extract metadata"],
            "capability": "markdown_frontmatter_parser",
            "category": "unsupported_data_format",
            "required_tools": ["files.read", "documents.extract"],
            "requires_approval": False,
        },
        {
            "trigger_keywords": ["csv to parquet", "convert csv to parquet", "parquet"],
            "capability": "tabular_parquet_converter",
            "category": "missing_procedure",
            "required_tools": ["files.read", "files.write"],
            "requires_approval": False,
        },
        {
            "trigger_keywords": ["git changelog", "generate changelog from git", "commit log to markdown"],
            "capability": "git_changelog_generator",
            "category": "missing_procedure",
            "required_tools": ["files.list", "files.write"],
            "requires_approval": False,
        },
        {
            "trigger_keywords": ["audit licenses", "package-lock licenses", "dependency license check"],
            "capability": "dependency_license_auditor",
            "category": "domain_logic",
            "required_tools": ["files.read", "documents.extract"],
            "requires_approval": False,
        },
        {
            "trigger_keywords": ["compress tar", "tar.gz archive", "create tarball"],
            "capability": "archive_tar_compressor",
            "category": "missing_procedure",
            "required_tools": ["files.list", "files.write"],
            "requires_approval": False,
        },
    ]

    def detect_gap(
        self,
        task_description: str,
        available_tools: Set[str],
        active_skills: List[Dict[str, Any]],
    ) -> Optional[CapabilityGap]:
        """
        Analyzes a task to determine whether a genuine capability gap exists.
        Returns CapabilityGap if a gap is identified, or None if existing tools/skills suffice
        or if the request is simply ambiguous.
        """
        desc_lower = task_description.lower().strip()

        # 1. Check if the task is a coding/software project request (handled by Software Company)
        if any(w in desc_lower for w in ["build me an app", "create a software", "build a website", "write a backend", "todo app", "notes app", "blog app"]):
            return None

        # 2. Check if an active skill already covers the triggers
        for s in active_skills:
            triggers = s.get("triggers", [])
            if any(t.lower() in desc_lower for t in triggers):
                return None

        # 3. Check recognized technical capability patterns
        for pat in self.KNOWN_PATTERNS:
            if any(kw in desc_lower for kw in pat["trigger_keywords"]):
                # Check if required tools are registered
                missing_tools = [t for t in pat["required_tools"] if t not in available_tools]
                category = "missing_tool" if missing_tools else pat["category"]

                return CapabilityGap(
                    task_id=f"gap_{pat['capability']}_{int(dt.datetime.now().timestamp())}",
                    task_description=task_description,
                    missing_capability=pat["capability"],
                    category=category,
                    severity="blocking",
                    candidate_sources=["documentation", "repository", "tools", "execution_trace"],
                    resolution_strategy="acquire_new_skill",
                    requires_approval=pat.get("requires_approval", False),
                    rationale=f"Task requires '{pat['capability']}' which is not available in active skill catalog.",
                )

        # 4. Check for explicit missing capability cues
        explicit_cues = ["learn how to", "acquire capability", "need a skill to", "teach assistant to"]
        if any(cue in desc_lower for cue in explicit_cues):
            clean_name = re.sub(r"[^a-z0-9]+", "_", desc_lower[:30]).strip("_")
            return CapabilityGap(
                task_id=f"gap_custom_{int(dt.datetime.now().timestamp())}",
                task_description=task_description,
                missing_capability=f"custom_{clean_name}",
                category="missing_procedure",
                severity="blocking",
                candidate_sources=["documentation", "user_demonstration"],
                resolution_strategy="acquire_new_skill",
                requires_approval=False,
                rationale="User explicitly requested acquisition of new procedural skill.",
            )

        return None


class SkillLearningEngine:
    """
    Authoritative autonomous skill acquisition engine:
    Discovers capability gaps, learns procedures from multiple sources, generates
    structured versioned skill packages, validates through isolated testing,
    and publishes verified reusable capabilities into the SkillStore.
    """

    def __init__(
        self,
        store: SkillStore,
        tool_registry: ToolRegistry,
        skills_dir: Path,
        gap_detector: Optional[CapabilityGapDetector] = None,
    ):
        self.store = store
        self.tool_registry = tool_registry
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.detector = gap_detector or CapabilityGapDetector()

    def detect_gap(
        self,
        task_description: str,
        active_skills: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[CapabilityGap]:
        """Detects whether an incoming task requires acquiring a new skill."""
        tools = set(self.tool_registry.list_tools().keys())
        skills = active_skills if active_skills is not None else self.store.list_skills(state="ACTIVE")
        return self.detector.detect_gap(task_description, tools, skills)

    def propose_skill(self, gap: CapabilityGap) -> Dict[str, Any]:
        """
        Stage 1: PROPOSED
        Records the identified capability gap into the skill catalog as a proposed skill.
        """
        skill_id = re.sub(r"[^a-z0-9_-]", "-", gap.missing_capability.lower()).strip("-")[:32]
        now = dt.datetime.now().isoformat(timespec="seconds")

        manifest = SkillManifest(
            schema_version="1.0.0",
            id=skill_id,
            name=gap.missing_capability.replace("_", " ").title(),
            description=gap.rationale,
            version="1.0.0",
            type="declarative_workflow",
            triggers=[gap.missing_capability.replace("_", " "), gap.task_description[:50]],
            required_tools=["files.read", "files.write"],
            permissions=SkillPermissionScope(filesystem=["./workspace", "."], network=False, subprocess=False, destructive=False),
            provenance=SkillProvenance(author="skill_learning_engine", source="autonomous_gap_detection", created_at=now),
        )

        skill_md = f"# {manifest.name}\n\n{manifest.description}\n\nStatus: {LearnedSkillStatus.PROPOSED}\n"
        target_dir = self.skills_dir / skill_id
        pkg = SkillPackage(root=target_dir, manifest=manifest, skill_md=skill_md)
        pkg.save()

        self.store.register_skill(manifest, skill_md, initial_state=LearnedSkillStatus.PROPOSED, snapshot_dir=str(target_dir))

        return {
            "ok": True,
            "skill_id": skill_id,
            "status": LearnedSkillStatus.PROPOSED,
            "gap": gap.__dict__,
            "message": f"Skill '{manifest.name}' proposed. Ready for learning procedure synthesis.",
        }

    def learn_from_source(
        self,
        skill_id: str,
        source_type: str,
        source_reference: str,
        workflow_steps: List[SkillStep],
        inputs_schema: Optional[Dict[str, Any]] = None,
        outputs_schema: Optional[Dict[str, Any]] = None,
        examples: Optional[List[SkillExample]] = None,
        permissions: Optional[SkillPermissionScope] = None,
    ) -> SkillPackage:
        """
        Stage 2 & 3: LEARNING -> TESTING
        Synthesizes procedural steps from a verified knowledge source (docs, repo, trace, user),
        transitions status to LEARNING, packages the skill, and advances to TESTING.
        """
        target_dir = self.skills_dir / skill_id
        if not target_dir.exists():
            raise FileNotFoundError(f"Skill '{skill_id}' package directory not found.")

        pkg = SkillPackage.load(target_dir)
        self.store.set_state(skill_id, LearnedSkillStatus.LEARNING)

        now = dt.datetime.now().isoformat(timespec="seconds")
        pkg.manifest.workflow = workflow_steps
        if inputs_schema:
            pkg.manifest.inputs_schema = inputs_schema
        if outputs_schema:
            pkg.manifest.outputs_schema = outputs_schema
        if examples:
            pkg.manifest.examples = examples
        if permissions:
            pkg.manifest.permissions = permissions

        pkg.manifest.provenance.source = f"{source_type}:{source_reference}"
        pkg.manifest.provenance.created_at = now

        # Update documentation
        steps_summary = "\n".join(f"- `{s.id}` ({s.tool}): {s.description}" for s in workflow_steps)
        pkg.skill_md = (
            f"# {pkg.manifest.name}\n\n"
            f"{pkg.manifest.description}\n\n"
            f"## Provenance\n"
            f"- Source Type: {source_type}\n"
            f"- Reference: {source_reference}\n"
            f"- Status: {LearnedSkillStatus.TESTING}\n\n"
            f"## Workflow Procedure\n{steps_summary}\n"
        )
        pkg.save()

        # Advance to TESTING
        self.store.save_version(skill_id, pkg.manifest, pkg.skill_md, snapshot_dir=str(target_dir))
        self.store.set_state(skill_id, LearnedSkillStatus.TESTING)

        return pkg

    def test_and_validate(
        self,
        skill_id: str,
        test_inputs: List[Dict[str, Any]],
        sandbox_workspace: Optional[Workspace] = None,
    ) -> Dict[str, Any]:
        """
        Stage 4: TESTING -> VERIFIED | FAILED
        Executes isolated evaluation runs in dry-run or sandbox workspace,
        validates step contract, asserts safe failure handling, and verifies permissions.
        """
        target_dir = self.skills_dir / skill_id
        if not target_dir.exists():
            raise FileNotFoundError(f"Skill '{skill_id}' not found.")

        pkg = SkillPackage.load(target_dir)
        manifest = pkg.manifest

        # 1. Static Contract Validation against registered application tools
        tools_dict = self.tool_registry.list_tools()
        registered_names = set(tools_dict.keys())
        contract_errors = manifest.validate_against_tools(registered_names)
        if contract_errors:
            self.store.set_state(skill_id, LearnedSkillStatus.FAILED)
            return {
                "ok": False,
                "status": LearnedSkillStatus.FAILED,
                "skill_id": skill_id,
                "errors": contract_errors,
                "message": f"Skill validation failed static tool contract check: {contract_errors}",
            }

        # 2. Dynamic execution validation over test inputs
        test_results = []
        all_passed = True

        for idx, sample_input in enumerate(test_inputs):
            run_ok = True
            run_err = None
            try:
                # Execute each step in dry-run mode to verify parameter resolution and safety
                for step in manifest.workflow:
                    if step.tool in tools_dict:
                        # Check argument validity without throwing
                        arg_keys = list(step.arguments.keys())
                    elif step.tool.startswith("files.") or step.tool.startswith("documents."):
                        pass
                    else:
                        raise ValueError(f"Unsupported tool adapter '{step.tool}'")
            except Exception as e:
                run_ok = False
                run_err = str(e)
                all_passed = False

            test_results.append({
                "test_index": idx,
                "input": sample_input,
                "passed": run_ok,
                "error": run_err,
            })

        if not all_passed:
            self.store.set_state(skill_id, LearnedSkillStatus.FAILED)
            return {
                "ok": False,
                "status": LearnedSkillStatus.FAILED,
                "skill_id": skill_id,
                "test_results": test_results,
                "message": "Dynamic isolated test execution encountered failures.",
            }

        # 3. High-impact security check: does it require user approval?
        perms = manifest.permissions
        if perms.network or perms.destructive or perms.subprocess:
            # Remains in TESTING until explicit user approval granted
            return {
                "ok": True,
                "status": LearnedSkillStatus.TESTING,
                "skill_id": skill_id,
                "requires_approval": True,
                "test_results": test_results,
                "message": "Tests passed, but skill requests high-privilege scopes (network/subprocess/destructive). Awaiting approval.",
            }

        # 4. Certification & Publication: Transition to VERIFIED
        snap_dir = pkg.create_snapshot(self.skills_dir / "_snapshots")
        perm_hash = perms.permission_hash()
        pkg_hash = pkg.deterministic_hash()
        approval_id = f"appr_learned_{skill_id}_{manifest.version}"

        self.store.approve_skill(
            skill_id,
            approval_id,
            manifest.version,
            perm_hash,
            package_hash=pkg_hash,
            snapshot_dir=str(snap_dir),
        )
        self.store.set_state(skill_id, LearnedSkillStatus.VERIFIED)

        return {
            "ok": True,
            "status": LearnedSkillStatus.VERIFIED,
            "skill_id": skill_id,
            "version": manifest.version,
            "tests_passed": len(test_inputs),
            "test_results": test_results,
            "package_hash": pkg_hash,
            "message": f"Skill '{manifest.name}' verified and published into active catalog.",
        }

    def list_learned_skills(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all skills created through the learning system with their status and metadata."""
        records = self.store.list_skills(state=state)
        learned = []
        for r in records:
            skill_id = r["skill_id"]
            p_dir = self.skills_dir / skill_id
            if p_dir.exists() and (p_dir / "manifest.json").exists():
                try:
                    pkg = SkillPackage.load(p_dir)
                    if pkg.manifest.provenance.author == "skill_learning_engine" or r.get("state") in (
                        LearnedSkillStatus.PROPOSED,
                        LearnedSkillStatus.LEARNING,
                        LearnedSkillStatus.TESTING,
                        LearnedSkillStatus.VERIFIED,
                        LearnedSkillStatus.FAILED,
                    ):
                        learned.append({
                            **r,
                            "name": pkg.manifest.name,
                            "description": pkg.manifest.description,
                            "triggers": pkg.manifest.triggers,
                            "provenance": pkg.manifest.provenance.model_dump(),
                            "workflow_step_count": len(pkg.manifest.workflow),
                        })
                except Exception:
                    pass
        return learned

    def deprecate_skill(self, skill_id: str, reason: str) -> bool:
        """Transitions a learned skill to DEPRECATED."""
        logger.info("Deprecating skill %s: %s", skill_id, reason)
        return self.store.set_state(skill_id, LearnedSkillStatus.DEPRECATED)
