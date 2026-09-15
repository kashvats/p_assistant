# Experience Engine — Learning from Past Mistakes

Living Assistant v0.9 adds an evidence-weighted local experience system. It is designed to learn useful operational lessons without treating every failure or model guess as permanent truth.

## Memory levels

The engine separates **episodes** from **lessons**.

- **Episode** — a short-lived local record of one tool attempt and its outcome. Episodes are retained for a configurable period (30 days by default) and are used for pattern detection.
- **Candidate lesson** — a possible lesson that is not trusted enough to influence normal reasoning yet.
- **Active lesson** — a lesson with enough evidence to be retrieved automatically for relevant tasks.
- **User-confirmed lesson** — a high-confidence lesson explicitly confirmed by the user.
- **Superseded/rejected lesson** — historical knowledge that is retained for audit but not injected into future reasoning.

This prevents a one-off incident from becoming a permanent rule.

## Automatic recovery learning

The orchestrator records bounded, redacted tool outcomes. If the same tool first fails and a later call succeeds with different arguments during the same task, v0.9 can create a low-confidence recovery candidate.

Example:

```text
run_command: npm start  -> failed: missing script
run_command: npm run dev -> success
```

The first occurrence stays a candidate. If the same recovery is observed again, the candidate can become active. The exact root cause is **not** automatically declared proven.

## Verified postmortems

After a failure is understood and a fix is actually validated, the orchestrator can record a structured postmortem:

```text
Situation: Backend crashed after restart
Past action: Restart API immediately
Outcome: It crashed again
Root cause: MongoDB was unavailable
Better action: Check dependency/database health before restart
Lesson: Diagnose dependencies before restarting this service
Verified: yes
```

Verified lessons can immediately become active, but current evidence always outranks old memory.

## Confidence and decay

Each lesson has:

- confidence
- evidence successes
- evidence failures
- observation count
- verified/user-confirmed flags
- last-seen and last-verified timestamps
- conflict count

Unconfirmed lessons decay over time. User-confirmed lessons decay much more slowly. This helps old procedures lose influence after projects migrate.

Default policy:

```yaml
experience:
  enabled: true
  auto_capture: true
  min_inject_confidence: 0.55
  confidence_half_life_days: 120
  confirmed_half_life_days: 365
  auto_promote_repeats: 2
  episode_retention_days: 30
  max_context_lessons: 5
```

## Contradictions

If two active lessons describe the same situation/project but recommend different better actions, both are marked as conflicting. Retrieved context contains a warning and the orchestrator is told to verify the current state instead of blindly picking an old rule.

Example:

```text
Old: Start API with uvicorn
New: Start API with gunicorn
```

After confirming the migration, supersede the old lesson:

```bash
organism experience supersede OLD_ID NEW_ID
```

## Secret handling

Experience storage redacts common password, token, API-key, credential, cookie, bearer-token and private-key patterns. Large file contents are summarized by size/hash in tool episode arguments rather than persisted verbatim.

Do not use experience memory as a secret store.

## CLI

Teach a lesson explicitly:

```bash
organism experience add procedure \
  "Start RetailEye frontend" \
  "Use pnpm dev for the current frontend" \
  --project RetailEye \
  --better-action "pnpm dev" \
  --confirmed
```

Search:

```bash
organism experience search "RetailEye backend restart"
```

List active lessons:

```bash
organism experience list
```

Include candidates:

```bash
organism experience search "frontend startup" --include-candidates
```

Confirm a lesson:

```bash
organism experience confirm EXPERIENCE_ID
```

Tell the system whether a retrieved lesson actually helped:

```bash
organism experience verify EXPERIENCE_ID --useful --evidence "Worked on current project version"
```

Or mark it unhelpful:

```bash
organism experience verify EXPERIENCE_ID --not-useful --evidence "Project migrated to pnpm"
```

Reject:

```bash
organism experience reject EXPERIENCE_ID "Incorrect inference"
```

See recurring failure clusters:

```bash
organism experience patterns
```

Inspect recent episodes:

```bash
organism experience episodes --failures-only
```

Statistics:

```bash
organism experience stats
```

## Retrieval behavior

Before a model task, the orchestrator searches active experience memory using the current request plus working/project context. Only lessons above the injection threshold are included, in a bounded section labeled as advisory evidence.

Experience memory never bypasses:

- command safety policy
- approval requirements
- database read-only policy
- workspace boundaries
- security controls
- evaluated self-improvement gates

A remembered command is not permission to run it.

## Failure-pattern clustering

Recent failed episodes are normalized into recurring patterns by tool and failure signature. Variable numbers, paths and addresses are normalized so repeated variants can cluster.

This can reveal patterns such as:

```text
run_command | connection refused code <n> | count 7
```

A cluster is an observation, **not proof of root cause**.

## What v0.9 intentionally does not do

- It does not fine-tune the SLM after every mistake.
- It does not permanently trust a single automatic recovery.
- It does not allow old experience to override current tool evidence.
- It does not store unredacted secrets intentionally.
- It does not let learned experience bypass approvals or policy.

For laptop-scale agents, explicit structured experience is cheaper, more auditable, and easier to correct than continuously retraining small models.
