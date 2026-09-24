# Living Assistant — Custom Skills Guide (FEAT-19)

This guide documents the architecture, lifecycle, and operational workflows for the Custom Skills System in Living Assistant.

---

## 1. Overview & Core Tenets

The Living Assistant Custom Skills system enables safe, deterministic, declarative workflows and tool combinations. It is designed with:
- **Portability:** Works seamlessly across Windows and Ubuntu/Linux environments.
- **Out-of-Model Security:** Zero reliance on LLMs to enforce permission boundaries. Path sanitization, workspace sandboxing, and tool allowlists run deterministically.
- **Immutable Snapshots:** Approvals bind directly to cryptographic SHA-256 hashes of manifest and package contents. Any live disk tampering immediately drops the skill to `DRAFT` and prevents execution.
- **Durable Action Recovery:** State changes and side effects are logged to SQLite before and after execution, supporting idempotent crash recovery and conflict-aware undo operations.
- **Resource Discipline:** Runs within bounded single-resident memory limits on 4 GB VRAM / 32 GB RAM hardware.

---

## 2. Skill Package Structure

Custom skills reside in `~/.living_assistant/skills/<skill-id>/` (or workspace-configured directory):

```
skills/<skill-id>/
├── SKILL.md            # Human-readable documentation, usage guidelines, prompts
├── manifest.json       # Machine-readable contract, dependencies, permissions, steps
├── examples/           # Sample inputs and scenario definitions
│   └── default.json
└── tests/              # Declarative test assertions
    └── test_cases.json
```

---

## 3. Skill Manifest Schema (`manifest.json`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "1.0.0",
  "id": "downloads-organizer",
  "name": "Downloads Organizer",
  "description": "Scans downloads, extracts metadata, categorizes into destination folders.",
  "version": "1.0.0",
  "type": "declarative_workflow",
  "entrypoint": "workflow",
  "required_tools": [
    "files.list",
    "documents.extract",
    "files.move"
  ],
  "permissions": {
    "filesystem": [
      "./downloads"
    ],
    "network": false,
    "destructive": false
  },
  "inputs_schema": {
    "type": "object",
    "properties": {
      "folder": { "type": "string", "default": "./downloads" }
    }
  },
  "workflow": [
    {
      "id": "list_downloads",
      "tool": "files.list",
      "description": "List files in target folder",
      "arguments": { "path": "{{folder}}" },
      "output_variable": "raw_files"
    },
    {
      "id": "process_files",
      "tool": "files.move",
      "for_each": "raw_files",
      "max_iterations": 100,
      "when": "item.is_file and item.extension == '.pdf'",
      "arguments": {
        "source": "{{item.path}}",
        "destination": "{{folder}}/Documents/{{item.name}}"
      },
      "retries": 1,
      "on_failure": "continue"
    }
  ]
}
```

### Step Control Semantics
- `when`: Declarative AST condition evaluated safely without Python `eval`. Supports `item.attr`, boolean operators, and constant comparisons.
- `for_each`: Iterates over an array produced by an earlier step.
- `max_iterations`: Hard cap preventing accidental infinite processing (default: 50).
- `retries` & `retry_delay_seconds`: Automatic retry on transient tool failure.
- `on_failure`: Strategy if all retries fail: `"abort"` (default), `"continue"`, or `"fallback"`.
- `fallback_step_id`: Step ID to branch to if `on_failure == "fallback"`.

---

## 4. Lifecycle States

Every custom skill moves through explicit lifecycle states stored in SQLite (`skill_lifecycle`):

```
DRAFT ──(Validation & Approval)──> ACTIVE ──(Tampering / Edit)──> DRAFT
  │                                   │
  ├───(Disable)───> DISABLED <────────┘
  │                    │
  └───(Archive)───> ARCHIVED
```

- **DRAFT:** Skill is created or edited. Executable only with `dry_run=True`.
- **ACTIVE:** Cryptographic package hash is approved. Live execution permitted.
- **DISABLED:** Temporarily paused; cannot be triggered.
- **ARCHIVED:** Soft-deleted.

---

## 5. Security & Verification

1. **Workspace Boundary:** Relative paths cannot escape workspace roots via `../` traversal or symbolic links (`SkillPermissionViolation`).
2. **Prohibited Targets:** System policy files (`security_policy.py`, `approval.py`, `.git/`) are unconditionally blocked.
3. **Collision Avoidance:** `files.move` automatically renames collisions (`filename (1).ext`) unless explicit `overwrite=true` is requested and approved.
4. **Approval Invalidation:** When any package file is modified on disk, the live hash diverges from the stored approval hash, immediately blocking live runs until re-approved.

---

## 6. Document Extraction & Docling Integration

The `documents.extract` tool and `DocumentExtractor`:
- Utilizes **Docling** when available for layout analysis, table parsing, and OCR.
- Employs deterministic zero-dependency fallback for text files, basic PDF metadata, and HTML tags if Docling is unavailable.
- Computes mathematical invoice validation (verifying whether `subtotal + tax == total`), extracts confidence scores, and outputs ambiguity flags if human review is advised.

---

## 7. Crash Recovery & Conflict-Aware Undo

- **SQLite Durable Logging (`skill_action_records`):** Every mutation records planned preconditions, started status, and post-action outcome.
- **Crash Recovery (`reconcile_execution`):** If power is lost mid-workflow, `reconcile_execution` inspects filesystem state, identifies which actions completed or failed, and clears interrupted states safely.
- **Conflict-Aware Undo (`undo_execution`):** Reverts moves in reverse order. If a destination file was modified after the run or the original location is already occupied, the conflict is flagged and destructive rollback is blocked.

---

## 8. CLI & API Reference

### CLI Commands (`organism skill`)
```bash
# List skills
organism skill list

# Draft a skill using natural language
organism skill draft "Create a skill that organizes downloaded invoices into monthly subfolders"

# Inspect and validate a skill
organism skill info downloads-organizer

# Test execution (dry-run mode)
organism skill test downloads-organizer --dry-run

# Activate after review
organism skill activate downloads-organizer

# Run active skill
organism skill run downloads-organizer --input folder=./downloads

# Undo execution run
organism skill undo <run_id>

# Reconcile interrupted execution
organism skill reconcile <run_id>

# Export / Import package
organism skill export downloads-organizer --out downloads-organizer.zip
organism skill import downloads-organizer.zip
```

### REST API Endpoints
- `GET /skills`: List skills with lifecycle metadata.
- `GET /skills/{id}`: Detailed manifest, history, and version records.
- `POST /skills/draft`: Create draft from natural-language prompt.
- `PUT /skills/{id}`: Update manifest and `SKILL.md`.
- `POST /skills/{id}/activate`: Create immutable snapshot and approve package hash.
- `POST /skills/{id}/execute`: Execute skill (supports `dry_run=true`).
- `POST /skills/{id}/undo`: Conflict-aware reversal of execution run.
- `POST /skills/{id}/reconcile`: Reconcile interrupted run.
