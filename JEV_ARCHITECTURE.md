# Dual-Engine AI Architecture: Jev + AirLLM

> **This document is the authoritative system contract for p_assistant.**
> All agents and engineers working on this codebase must read this before
> touching any decision-making, routing, memory, or security code.

---

## The Core Problem This Solves

AirLLM lets you run massive frontier models (70B–405B params) locally by
swapping layers through VRAM from disk. The trade-off is low tokens-per-second
(TPS). If you use AirLLM for every binary choice (routing, loop detection,
safety gating), the assistant becomes visibly slow and expensive to run.

**Jev** (TypeSafe AI, Sep 2026) is a "System One" model. It cannot generate
text. It only evaluates context against strictly typed primitives and returns
calibrated probabilities in sub-100ms. No hallucination possible — it
mathematically cannot return a value outside the options you give it.

---

## The Two-Engine Contract (GOLDEN RULES)

| Decision Type | Engine | Why |
|---|---|---|
| Which tool to use? | **Jev `Score`** | Routing must never hallucinate a tool name |
| Is this action safe? | **Jev `Noul`** | Security gates must be instant, not slow |
| Is the task done? | **Jev `Noul`** | Prevents AirLLM from wasting context looping |
| Is this memory relevant? | **Jev `Score`** | Stops context bloat hurting AirLLM accuracy |
| Is this lesson obsolete? | **Jev `Score`** | Semantic GC > timestamp math |
| Write a code patch | **AirLLM** | Only generative model can produce novel text |
| Write a skill update | **AirLLM** | Needs deep reasoning, not a reflex |
| Synthesize a summary | **AirLLM** | Text generation |
| Generate tool arguments | **AirLLM** | Needs to produce specific, structured payloads |

### ❌ Never do this:
- Use AirLLM to decide Yes/No (route, gate, done check). It's 100× more
  expensive than Jev for this.
- Use Jev to generate free-text responses, code, or JSON payloads. It cannot.
- Let the AI autonomously merge its own proposed skill updates. Always write to
  disk as a proposal; the human applies it.

---

## Implementation Map

### 1. `src/living_assistant/core/typesafe.py` — The JevClient
The single interface to all Jev primitives. Designed with live API fallback
and a calibrated local mock (used automatically when `TYPESAFE_API_KEY` is
not set).

**Key methods:**
```python
jev.choice(context, options, question)        # Tool routing
jev.noul(context, statement)                  # Yes/No gate
jev.score(context, levels, question)          # Relevance ranking
jev.goal_achieved(user_goal, tool_results)    # Loop breaker
jev.is_lesson_relevant(lesson, request)       # Memory filter
jev.link_incident(pattern, tracker_items)     # Incident linker
jev.score_secret_risk(text_chunk)             # Outbound secret scan
jev.score_knowledge_value(lesson)             # Daemon GC
```

**To activate the live Jev API** (when TypeSafe AI exits early access):
```bash
export TYPESAFE_API_KEY=sk-your-key
# optionally: export TYPESAFE_BASE_URL=https://api.typesafe.ai/v1
```

---

### 2. `src/living_assistant/agents/orchestrator.py` — Three Jev Hooks

**Hook A — Tool Router (`_initial_tool_names`)**
Jev `Score` replaces BM25 keyword matching for initial tool selection.
Jev scores every registered tool as `Irrelevant / Maybe / Highly Relevant`
against the user's request. Only tools above the threshold enter AirLLM's
context window. AirLLM then writes the specific argument payloads.

**Hook B — Security Gate (inside tool loop)**
Before `_execute_tool()` fires, Jev `Noul` evaluates the proposed action.
If safety probability < 0.5, the call is blocked instantly. No AirLLM
inference wasted. Fixes BUG-05, BUG-09.

**Hook C — Loop Breaker (end of each step)**
After each tool step, Jev `Noul` checks if the user's goal has been achieved.
If probability ≥ 0.82, the loop is hard-killed and the current answer is
returned. Prevents infinite context-drain with slow AirLLM models.

---

### 3. `src/living_assistant/learning/experience.py` — Memory Filter

**`context_for()` — Jev-gated injection:**
1. **Broad net:** Pull 3× candidates via cheap token-overlap search.
2. **Jev filter:** Pass all candidates through `jev.is_lesson_relevant()`.
3. **Surgical injection:** Only `Exact Match` lessons enter AirLLM's prompt.

This is the single most impactful accuracy improvement. AirLLM stops
hallucinating when it stops seeing 15 loosely related memories at once.

---

### 4. `src/living_assistant/system/daemon.py` — Semantic GC

**Hourly maintenance — Jev knowledge-value scoring:**
After standard `maintenance()` runs (timestamp decay, episode pruning),
Jev `Score` evaluates every active lesson for current knowledge value:
- `Highly Relevant` → keep
- `Stale` → leave for natural decay
- `Obsolete/Wrong` (conf ≥ 0.75, not user-confirmed) → reject immediately

Replaces brittle `if age > 180 and confidence < 0.4` heuristics with semantic
judgment. `skills.py` knowledge base self-heals nightly.

---

## The Self-Optimizing Loop (AirLLM + Jev)

```
User Interaction (real-time)
  └─ Jev routes & gates (< 100ms)
  └─ AirLLM generates payloads (seconds, only when needed)
  └─ Jev checks completion (< 100ms)
  └─ Lessons recorded in experience.py

Daemon (background, queued)
  └─ AirLLM reviews daily failure logs → discovers patterns
  └─ Jev links each pattern to MASTER_TRACKER.md (link_incident)
  └─ AirLLM writes patch / skill update proposal to disk
  └─ Human reviews → approves → applies

Hourly GC
  └─ Jev scores all active lessons for knowledge value
  └─ Obsolete lessons auto-rejected
  └─ skills.py and experience.py stay clean
```

---

## When the Live Jev API Becomes Available

1. Set `TYPESAFE_API_KEY` in your environment.
2. The `JevClient` automatically switches from the local mock to live calls
   with `httpx` (already in project deps).
3. Expect 40–200× speed increase on routing and gating vs the local mock.
4. No other code changes required. Same interface, same contract.
