# Original User Request

## 2026-10-07T16:07:08Z

# Teamwork Project Prompt

Requested team: Software Company Multi-Agent Team (Manager/Architect, QA Engineer, Backend Developer, Frontend Developer)

Merge the AI coding assistant from `c:\Users\human-bot\projects\new-curiosity\ai-coding-assistant` into the Living Assistant (`c:\Users\human-bot\projects\ai-personal`) repository, preserve and integrate the existing codebase pickup/onboarding capability, and make Hermes and Collibri fully operational using a software company multi-agent hierarchy (Manager, QA, Backend Developer, Frontend Developer).

Working directory: c:\Users\human-bot\projects\ai-personal
Source directory: c:\Users\human-bot\projects\new-curiosity\ai-coding-assistant
Integrity mode: development

## Requirements

### R1. Merge AI Coding Assistant Capabilities into Living Assistant
Analyze and integrate the capabilities, tools, and endpoints from `new-curiosity/ai-coding-assistant` (backend services, code generation pipelines, developer tools, SearXNG search integration, and UI components) into `ai-personal`. Ensure no duplication with existing Living Assistant modules and preserve all passing tests.

### R2. Brownfield Codebase Pickup & Onboarding Engine
Preserve and enhance the existing codebase onboarding feature so the assistant can automatically inspect, index, understand, and resume development on pre-existing projects (parsing AST hierarchies, detecting dependencies, identifying conventions, and building system graphs).

### R3. Multi-Agent Software Company Hierarchy (Manager, QA, Backend, Frontend)
Configure and operationalize an end-to-end multi-agent software development company workflow:
- **Manager / Technical Lead:** Decomposes user goals into modular tasks, allocates specifications, and tracks execution milestones.
- **Backend Developer Agent:** Implements server APIs, data models, business logic, and integrations.
- **Frontend Developer Agent:** Implements user interfaces, components, and real-time client contracts.
- **QA / Test Engineer Agent:** Generates regression suites, tests edge cases, validates implementations independently, and rejects failing builds before delivery.

### R4. Hermes & Collibri Multi-Agent Integration
Wire the `hermes-agent` / `HermesContractor` and Collibri agent runners into the multi-agent hierarchy, routing their actions through the project's security gates, path confinement, and tool dispatchers.

## Acceptance Criteria

### Integration & Architecture
- [ ] Source tools and services from `new-curiosity/ai-coding-assistant` are unified into `ai-personal` without redundant duplicate packages.
- [ ] Existing Living Assistant test suite (`pytest tests/`) remains functional and passing.

### Codebase Pickup Capability
- [ ] An automated onboarding command or method scans an arbitrary existing repository path, parses its AST/file tree, and generates a structured codebase index and architecture summary.

### Multi-Agent Company Workflow Execution
- [ ] A task dispatched to the company workflow automatically routes through Manager -> Developers (Backend/Frontend) -> QA.
- [ ] The QA agent independently runs verification/tests and reports pass/fail status back to the Manager before closing a task.
- [ ] Hermes contractor executes sandboxed actions via the central tool registry without unconfined host access.


## 2026-10-07T16:21:54Z

Master Software Company Execution Prompt has been provided by user and saved to `c:\Users\human-bot\projects\ai-personal\.agents\teamwork\MASTER_EXECUTION_PROMPT.md`.

Key directives to inject into the Orchestrator's synthesis and milestone decomposition:
1. Brownfield Integration: Merge `C:\Users\human-bot\projects\new-curiosity\ai-coding-assistant` into `C:\Users\human-bot\projects\ai-personal` without greenfield rewrites.
2. Architecture Ownership: Living Assistant is the Control Plane (task graph, persistent state, security gates, codebase knowledge). Hermes is the sole Agent Runtime (roles, execution, delegated reasoning). Collibri is an execution capability behind security gates.
3. Git Safety: Record baseline commit, establish checkpoints before risky changes, never run destructive git resets.
4. Dynamic Software Company Organization: Roles (Manager, Product, Architect, UX/UI, Backend, Frontend, DB, DevOps, Codebase Engineer, QA, Security, VAPT, SEO, Reviewer, Git/Change Manager, Release Manager, Verifier) are dynamically activated profiles in Hermes, not permanent processes.
5. Independent Evidence-Based QA & Verification: Developers cannot self-certify. QA and Final Verifier must validate evidence before declaring tasks complete.

Please forward these directives to the orchestrator to guide Phase 0 synthesis into `PROJECT.md` and Phase 1 milestone execution.


## 2026-10-07T16:24:13Z

Additional Specialist Roles Directive added to `MASTER_EXECUTION_PROMPT.md`:

1. Tool / Browser Operator:
- Manages complex multi-step tool workflows (browser, shell, search, filesystem, APIs, YouTube, MCPs).
- Collects evidence and structured outputs for other agents.
- Handles tool failures and safe retries under task-scoped permissions without bypassing central Tool Gateway or security controls.
- (Simple tool calls remain directly with agents; this specialist is used for complex multi-step tool interactions.)

2. GitHub / Open-Source Researcher:
- Searches GitHub and public sources for reusable projects, libraries, and patterns instead of reinventing from scratch.
- Performs repository health, test coverage, and supply-chain risk assessments.
- Strict license analysis (identifies license terms, flags incompatibilities).
- Categorizes recommendations into: REUSE (direct dependency), ADAPT (code adaptation), DEPEND, INSPIRE (reference only), or REJECT.
- Reports recommendations to the Manager before external code is approved or ingested.

Please forward these role profiles to the Project Orchestrator (`b55bf22b-24c2-41de-b5ff-a43ce278e30f`) to incorporate into the Hermes specialist role catalog and task decomposition logic.

## 2026-10-08T03:49:46Z

# Teamwork Project Prompt — Master Software Company & Living Assistant Integration

Requested team: Software Company Multi-Agent Team (Manager/Architect, QA Engineer, Backend Developer, Frontend Developer, Security, Design)

Merge the AI coding assistant from `c:\Users\human-bot\projects\new-curiosity\ai-coding-assistant` into the Living Assistant (`c:\Users\human-bot\projects\ai-personal`) repository, preserve and enhance the existing brownfield codebase onboarding capability, operationalize Hermes and Collibri, and complete the architecture with the Personal Assistant Director as root product, full software company role catalogue, task-scoped tool permissions, Git change checkpoints, and independent verification gating.

Working directory: c:\Users\human-bot\projects\ai-personal
Source directory: c:\Users\human-bot\projects\new-curiosity\ai-coding-assistant
Integrity mode: development
Reference documents:
- c:\Users\human-bot\projects\ai-personal\.agents\teamwork\MASTER_EXECUTION_PROMPT.md
- c:\Users\human-bot\projects\ai-personal\.agents\teamwork\ADDENDUM.md
- c:\Users\human-bot\projects\ai-personal\.agents\teamwork\PROJECT.md

## Requirements

### R1. Merge AI Coding Assistant Capabilities into Living Assistant
Analyze and integrate the capabilities, tools, and endpoints from `new-curiosity/ai-coding-assistant` (backend services, code generation pipelines, developer tools, SearXNG search integration, and UI components) into `ai-personal`. Consolidate duplicate implementations, preserve existing Living Assistant modules, and keep existing tests passing.

### R2. Brownfield Codebase Pickup & Onboarding Engine
Preserve and enhance the existing codebase onboarding engine (`CodebaseOnboardingEngine`) so the assistant can automatically inspect, index, understand, and resume development on pre-existing projects (parsing AST hierarchies, detecting dependencies, identifying conventions, and building system graphs). Expose via CLI and API endpoints.

### R3. Personal Assistant Director & Root Product Domain Routing
Preserve Living Assistant as the top-level product. Implement the Personal Assistant Director above specialized domains to classify user intents (`personal`, `technical`, `coding`, `research`, `media`, `computer`, `mixed`), coordinate direct personal actions, dispatch software tasks to the company subsystem, and synthesize multi-domain outputs into one coherent response.

### R4. Dynamic Software Company Organization & Hermes Role Profiles
Operationalize a self-coordinating software company workflow powered by Hermes as the sole agent runtime:
- **Executive & Product:** Manager / Tech Lead, Product Manager / Analyst.
- **Design:** UX Designer, UI Designer, Design System Specialist.
- **Engineering:** Software Architect, Backend Dev, Frontend Dev, Database Engineer, Data/Analytics Specialist, AI/ML Engineer, DevOps/SRE.
- **Specialists:** Tool / Browser Operator (multi-step tool workflows), GitHub / Open-Source Researcher (candidate discovery, license compliance, REUSE/ADAPT/DEPEND/INSPIRE/REJECT audit), Web Researcher, Computer Operator.

### R5. Task-Scoped Tool Permissions & Dynamic Model Routing
Enforce task-scoped tool permissions: `ROLE + TASK + ENVIRONMENT + RESOURCE + RISK = ALLOWED ACTIONS`. Wire model routing to select models dynamically based on task complexity, context requirements, latency/cost, and local hardware. Collibri acts as an execution capability strictly behind security and permission gates.

### R6. Autonomous Git Change Manager & Recovery Checkpoints
Implement the Version Control / Change Manager to record task baselines, create checkpoints before autonomous changes, associate diffs with task IDs, and provide multi-level rollback to known-good states without destructive resets.

### R7. Security Department & Action Approval Policy
Structure the Security functions (Security Architect, AppSec, VAPT / Red Team within workspace confines, Security Auditor). Enforce explicit action classes (Automatic vs Approval-Required) and an incident containment/recovery workflow.

### R8. Independent QA Rejection Gate, Final Verifier & Test Verification
QA must operate independently of implementing roles, generate regression tests, test edge cases, and enforce an authoritative rejection gate. The Final Verifier acts as the completion gate, confirming all criteria, tests, security, artifacts, and Git state before marking tasks `COMPLETED`.

## Acceptance Criteria

### Integration & Architecture
- [ ] Source capabilities from `new-curiosity/ai-coding-assistant` are unified into `ai-personal` without duplicate frameworks.
- [ ] Existing Living Assistant test suite (`pytest tests/`) remains passing.
- [ ] Living Assistant remains the root product with the Personal Assistant Director routing requests.

### Codebase Pickup Capability
- [ ] Automated onboarding scans arbitrary repositories, parses AST hierarchies, and generates structured codebase knowledge.
- [ ] Incremental updates to codebase knowledge are supported.

### Multi-Agent Company Workflow & Hermes Runtime
- [ ] Dynamic task graphs route through Manager -> Required Roles -> QA -> Verifier.
- [ ] QA independently executes tests and rejects failing implementations back to the Manager.
- [ ] Only the Final Verifier can transition tasks to `COMPLETED`.
- [ ] Hermes executes role profiles through the central tool gateway with task-scoped permissions.
- [ ] Collibri functions under tool and security confinement.

### Governance & Safety
- [ ] Git checkpoints are established before autonomous edits and safe rollbacks are verified.
- [ ] Destructive Git and filesystem operations require explicit user approval.
- [ ] All 100% of newly added and existing unit, integration, and regression tests pass.

## 2026-10-08T05:20:40Z

Phase A Audit has concluded and passed all exit criteria (audit report written to `.agents/teamwork/PHASE_A_AUDIT.md`, A2 Hermes capabilities verified, A3 Collibri single definition recorded in `system.graph.yaml`, A4 model depth established).

Proceed immediately with PHASE B: THIN VERTICAL SLICE on real task ("implement cart"):
Execution Flow:
Requirements -> user approval of spec -> Manager -> backend/frontend nodes -> leaf nodes -> frozen tests -> harness-generated QA report -> Final Verifier -> COMPLETED.

Key Implementation Directives:
1. B1. Recursive Task Graph inside existing TaskGraphManager DAG:
   - Max depth: 2 (local lightweight) / 3 (high-capacity).
   - Parent writes interface contract (endpoints, schemas, types) before splitting and passes to children.
   - Integration step at each level after children finish.
   - Children receive only spec, contract, and relevant code. Never whole conversation/repo. State lives in task graph.
   - Leaf is done only when check passes; parent reports upward only after verifying children's evidence.
2. B2. Evidence-Based Gates:
   - QAReport generated by harness from real runner output (command, exit code, log hash, commit SHA), never filled in by agent.
   - QA tests written and frozen before implementation; developer workers cannot edit them.
   - Every criteria_met entry in VerificationVerdict must reference an artifact ID.
   - Enforce in task-state code that ONLY FinalVerifier can set COMPLETED, and only when evidence references validate.
3. B3. Budget & Loop Control:
   - Max iterations, max retries, token cap, wall-clock cap.
   - QA REJECTED returns to Manager at most 3 times, then stops and escalates to human.
   - Per-task kill switch. Human decides if QA/Security reject but Manager wants to ship.
4. B4. Requirements Step:
   - Director -> Requirements (Product Manager profile) -> user approval -> Manager. Visible written spec, no silent rewrites.
5. B5. Isolation:
   - Worktree or branch, baseline commit recorded.
6. B6. Serial Execution default (4GB VRAM); parallelism only via VRAM lease.
7. B7. Per-task audit log (tool calls, model, tokens, duration, outcome).

Required Adversarial Tests:
- Agent editing frozen tests is blocked.
- Forging QA report is blocked.
- Setting COMPLETED without evidence is blocked.
- Exceeding depth or budget is blocked.
- Writing outside workspace is blocked.

Exit Criteria: "implement cart" task completes end-to-end with real verifiable evidence.


## 2026-10-08T08:50:13Z

Continue teamwork execution: Phase B Thin Vertical Slice ("implement cart").

## 2026-10-08T08:50:05Z

Continue execution: Phase B Thin Vertical Slice ("implement cart"). Report status.

## 2026-10-08T13:51:39Z

User Update & Correction from User:

"Correction: 'cart' was only an illustrative example, not a real task. Rename Phase B to 'Thin Vertical Slice' and remove 'Implement Cart' from the title, the task state, and any task graph or tests created for it. Do not implement a cart. Pause Phase B until the user specifies the slice task, or until the Manager proposes one small, self-contained feature from the target repo with a clear pass/fail check and the user approves it. If any cart work was already started, report what exists, do not delete it silently, and wait for my decision."

Instructions for the team:
1. Update task state, plans, and references to rename Phase B to "Thin Vertical Slice" and remove "Implement Cart".
2. Do NOT implement a cart. Report what cart work already exists (e.g., in test slices or models) without deleting it silently.
3. Pause Phase B vertical slice execution until user specifies the slice task, or Manager proposes one small, self-contained feature from the target repo with a clear pass/fail check and user approves it.
4. Continue with remaining architecture, merge, and verification milestones (Milestone 4: Unified Router & GEMINI Knowledge Base Sync, Milestone 5: Git Change Manager, etc.). Proceed immediately with the teamwork agent workflow.


## 2026-10-08T13:51:48Z

User Update & Correction from User:

"Correction: 'cart' was only an illustrative example, not a real task. Rename Phase B to 'Thin Vertical Slice' and remove 'Implement Cart' from the title, the task state, and any task graph or tests created for it. Do not implement a cart. Pause Phase B until the user specifies the slice task, or until the Manager proposes one small, self-contained feature from the target repo with a clear pass/fail check and the user approves it. If any cart work was already started, report what exists, do not delete it silently, and wait for my decision."

Instructions:
1. Update task state, plans, and references to rename Phase B to "Thin Vertical Slice" and remove "Implement Cart".
2. Do NOT implement a cart. Report what cart work already exists without deleting it silently.
3. Pause Phase B vertical slice execution until user specifies the slice task, or Manager proposes one small, self-contained feature from the target repo with a clear pass/fail check and user approves it.
4. Continue coordinating the agent team on the remaining objectives.


## 2026-10-08T18:46:17Z

# Teamwork Project Prompt — Master Software Company & Living Assistant Integration

Requested team: Software Company Multi-Agent Team (Manager/Architect, QA Engineer, Backend Developer, Frontend Developer, Security, SRE)

Merge the AI coding assistant from `c:\Users\human-bot\projects\new-curiosity\ai-coding-assistant` into the Living Assistant (`c:\Users\human-bot\projects\ai-personal`) repository, preserve and enhance the existing brownfield codebase onboarding capability, operationalize Hermes and Collibri, and complete the architecture with the Personal Assistant Director as root product, full software company role catalogue, task-scoped tool permissions, Git change checkpoints, and independent verification gating.

Working directory: c:\Users\human-bot\projects\ai-personal
Source directory: c:\Users\human-bot\projects\new-curiosity\ai-coding-assistant
Integrity mode: development
Reference documents:
- c:\Users\human-bot\projects\ai-personal\.agents\teamwork\MASTER_EXECUTION_PROMPT.md
- c:\Users\human-bot\projects\ai-personal\.agents\teamwork\ADDENDUM.md
- c:\Users\human-bot\projects\ai-personal\.agents\teamwork\PROJECT.md

## Completed Work (Forensically Verified)
- [x] Milestone 1: Hermes Contractor armored tool aliasing, sandboxed dispatch, and Collibri local inference supervision (15/15 tests passing in tests/test_hermes_contractor.py).
- [x] Milestone 2: Brownfield codebase pickup & onboarding engine (CodebaseOnboardingEngine), AST indexing, and system graph synchronization (24/24 unit tests, 19/19 stress tests).
- [x] Milestone 3: Personal Assistant Director & 7-department software company dynamic roles, frozen test path confinement, and task completion verification gates (56/56 tests passing).
- [x] Milestone 4: Unified AI Coding Assistant Router (src/living_assistant/api_routes/coding.py), SearXNG web search, AST patch safety, project auditor, and command risk explainer (23/23 tests passing in tests/test_coding_routes.py / tests/test_feat_coding_router.py).
- [x] Phase B: Paused ("Thin Vertical Slice" awaiting user task selection; no cart implementation).

## Active Milestones & Requirements

### R5. Autonomous Git Change Manager & Recovery Checkpoints (Milestone 5)
Implement the Version Control / Change Manager to record task baselines, create checkpoints before autonomous changes, associate diffs with task IDs, and provide multi-level rollback to known-good states without destructive resets. Expose snapshot and restore operations with workspace confinement.

### R6. Security Governance & Action Approval Policy (Milestone 5)
Enforce explicit action classification (Automatic vs Approval-Required) across tools and Git operations. Destructive actions (hard resets, file deletions outside staging, forced pushes) require human-in-the-loop approval gating. Implement the 8-stage incident containment and recovery workflow.

### R7. Independent QA Rejection Gate & Final Verification (Milestone 6)
QA must operate independently of implementing roles, execute regression suites, validate edge cases, and enforce an authoritative rejection gate. The Final Verifier acts as the completion gate, confirming all criteria, tests, security, artifacts, and Git state before marking tasks COMPLETED.

## Acceptance Criteria

### Governance & Safety
- [ ] Git checkpoints are established before autonomous edits and safe rollbacks are verified without destructive resets.
- [ ] Destructive Git and filesystem operations require explicit user approval.
- [ ] Multi-level rollback restores workspace to clean state upon failed tasks or rejected builds.

### Verification & Quality Gating
- [ ] QA independently executes tests and rejects failing implementations back to the Manager.
- [ ] Only the Final Verifier can transition tasks to COMPLETED.
- [ ] 100% of newly added and existing unit, integration, and regression tests pass across all milestones.


## 2026-10-09T08:28:35Z

Resume execution on Milestone 6 (Independent QA Rejection Gate, Final Verification & E2E Hardening). The server has restarted and quotas have reset. Check status in .agents/teamwork/orchestrator_gen4/, complete the explorer synthesis, and dispatch Worker M6 to execute Milestone 6 implementation, verification, and final Victory Audit.
