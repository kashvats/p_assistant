---
name: system-architecture
description: "Choose the structure of a software system - components, data flow, technology, folder layout - and record the decisions with reasons - use for architecture and technical design tasks."
---

# System architecture

## When to use
Before building: decide how a system is split up, which technologies to use and how the parts talk to each other.

## Steps
1. Read the requirements and anything already in the workspace (existing code decides a lot).
2. Pick the simplest technology that meets the requirements and that runs on this machine (check what is installed: python, node, etc. with the shell tool when unsure).
3. Describe the components, what each owns, and the data that flows between them. Give the folder/file layout.
4. Define the interfaces between parts (function signatures, API routes, file formats) precisely enough that two people can build both sides independently.
5. Write an architecture decision record per important choice: decision, alternatives considered, reason.

## Rules and checks
- No technology the machine cannot run or the user did not allow.
- Prefer one process and few dependencies unless the requirements need more.
