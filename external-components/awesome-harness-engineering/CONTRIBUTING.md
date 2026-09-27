# How to Contribute

## Scope of the list

We welcome resources that genuinely help practitioners build, measure, or run agent harnesses. Strong contributions typically touch one or more of these areas:

- Session state, memory, and progress-tracking artifacts
- Tool use and environment design
- Trajectory evals, grading, and agent observability
- Long horizon agents
- Reinforcement learning loops and self-evolving agents (curricula, rollouts, reflection, and harnesses that update their own policies, memory, or tools)
- Case studies and reference implementations

Surface-level AI news, model announcements, or general agent-framework promotion are usually out of scope unless the piece delivers concrete, harness-level substance.

## What we look for

Before proposing an entry, make sure the resource is:

- A primary source or an original technical deep-dive
- Not already represented by an existing entry
- Currently live and reachable on the open web
- Detailed enough that you can explain, in one line, why it matters to harness builders

## How to format an entry

Each entry must follow this format:

```
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) - Anthropic's breakdown of how to shape agent context windows for reliability across long tasks.
```

Write descriptions that are tight and concrete. Lead with the harness-engineering takeaway — not a generic summary of the topic.

## Where to put it

- Slot the entry into the narrowest existing section that applies.
- Only introduce a new section when no existing one fits; pick a title that is short and broad enough to keep growing.
- Don't list the same resource in more than one section.

## Pre-submission checklist

- Verify every link resolves.
- Double-check that the resource genuinely speaks to harness concerns.
- Make sure the description reflects the content honestly and isn't marketing copy.
- Scan the README to catch duplicates.
- Keep the diff tight and on-topic.

## Opening a PR

Smaller, tightly scoped PRs move through review the fastest.

When a single PR adds multiple links, add a short note explaining what ties them together and why the chosen section is the right home.
