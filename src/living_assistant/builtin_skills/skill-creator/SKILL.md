---
name: skill-creator
description: How to write a good SKILL.md skill - use when creating, learning, improving or reviewing a skill, or turning notes, documents or a finished task into a reusable skill.
---

# Writing a skill

A skill teaches the assistant how to do one kind of task well, every time. It is a folder with a
`SKILL.md` and, if needed, resource files (scripts, reference notes, templates).

## SKILL.md layout

```
---
name: short-kebab-case-name
description: What it does AND when to use it, in one or two sentences with the words a user would say.
---

# Title

## When to use
## Steps
## Rules and checks
## Examples (optional)
```

- The **description** decides when the skill is picked, so name the task, the inputs and typical
  phrasings ("convert", "invoice", "weekly report"). Keep it under ~300 characters.
- The **body** is instructions for the assistant, written as direct imperatives ("Read the file
  first", "Ask before deleting"). Keep it under ~300 lines; move long reference material into
  `references/*.md` and say when to read it.
- Put deterministic or repeated work in `scripts/` (Python preferred, standard library only when
  possible) and tell the assistant exactly how to run them and what they print.

## What to keep from source material

- Keep: the steps that worked, required inputs, file formats, commands, settings, pitfalls and how
  to check the result is right.
- Drop: chit-chat, one-off values (names, dates, paths of a single run), anything secret (keys,
  passwords, tokens), and steps that failed.
- Generalise specific values into inputs ("the user's CSV file") unless they are always the same.
- Never invent facts, API names or commands the material does not support; mark guesses as
  "verify before use".

## Quality checks before saving

1. Would a fresh assistant, given only this skill, do the task correctly?
2. Is every step actionable, in order, with the check that proves it worked?
3. Are destructive or outward actions (deleting, sending, paying, publishing) gated on the user's
   confirmation?
4. Is the description specific enough to be picked for the right requests and not others?
