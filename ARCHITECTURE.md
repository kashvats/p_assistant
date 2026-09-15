# Living Assistant v0.4 Architecture

```text
                         ┌────────────────────────────┐
                         │   User / CLI / Tray / API  │
                         │   Voice / Browser session  │
                         └──────────────┬─────────────┘
                                        │
                              intent / approved sensor
                                        │
                         ┌──────────────▼─────────────┐
                         │        Orchestrator        │
                         │  smallest model + tools    │
                         └──────┬─────────────┬───────┘
                                │             │
                    deterministic tools       │ specialist handoff
                                │             │
              ┌─────────────────▼───┐   ┌────▼──────────────┐
              │ Policy / Approvals  │   │ one active SLM     │
              │ outside the model   │   │ at a time normally │
              └─────────┬───────────┘   └───────────────────┘
                        │
  ┌─────────────────────▼────────────────────────────────────────────┐
  │ files • shell • projects • DB • git • web • browser • desktop  │
  │ voice • routines • quarantine • improvements • security         │
  └─────────────────────────────────────────────────────────────────┘

                         LOW-RESOURCE NERVOUS SYSTEM
  ┌─────────────────────────────────────────────────────────────────┐
  │ reminders • process crashes • health checks • file watches      │
  │ new ports • deterministic routines • notifications              │
  │ NO LLM remains loaded while idle                                │
  └─────────────────────────────────────────────────────────────────┘
```

## Sleeping-agent model

The system separates **roles** from **physical models**. On low/moderate hardware, several specialists can be the same quantized SLM with different system prompts. `ModelManager` unloads the previous model when a different physical model is activated.

## Sensors are privileged

Microphone capture, clipboard reads and screenshots are treated as sensitive sensors. The model cannot directly read them; it can only request an approval-gated tool.

## Browser isolation

Browser automation never attaches to the user's normal browser profile. Named sessions use Playwright-isolated contexts. A persistent session, when explicitly approved, gets an assistant-only profile directory. Session navigation is scoped to the host set established at session creation, and downloads remain disabled.

## Routines

Routines are deliberately deterministic first. `notify` and `todo` actions can run from the daemon without loading an LLM. `assistant_prompt` exists, but `routines.allow_model_wake` is `false` by default. When enabled, it still runs through a noninteractive runtime, so high-impact tool calls create approval requests instead of silently executing.

## Self-improvement

Self-improvement is a proposal pipeline, not unrestricted mutation:

```text
observation / repeated failure
          ↓
proposal: exact replacement + diff + rationale + suggested tests
          ↓
base file SHA-256 recorded
          ↓
user review / approval
          ↓
conflict check + backup
          ↓
apply exact proposal
          ↓
run tests separately / inspect result
```

The automatic apply path refuses to modify `security_policy.py`, `approval.py`, or `improvements.py`.

## Trust boundary

The LLM is not the security boundary. The deterministic tool layer validates workspace paths, SQL mode, downloads, browser scope, shell risk, approvals, and self-modification rules. External web/file/DB content remains untrusted observation data.
