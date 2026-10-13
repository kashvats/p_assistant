---
name: file-organizer
description: Tidy up a folder - sort files into subfolders by type or date, rename them consistently, find duplicates and large files - always showing the plan before changing anything.
---

# File organizer

## When to use
The user wants a folder cleaned up, sorted, renamed in bulk, de-duplicated, or wants to know what takes space.

## Steps
1. List the folder (and subfolders if asked) with the file tools. Note counts by type, total size, oldest/newest, and likely duplicates (same name and size).
2. Propose a plan as a short table: current file -> new location/name. Default grouping: Documents, Images, Videos, Audio, Archives, Code, Other; or by year-month when the user asks for dates.
3. Wait for the user's go-ahead. Then move/rename files; each change asks for approval.
4. Report what changed and what was left alone.

## Rules and checks
- Never delete anything unless the user explicitly asks; prefer moving to an "_to_delete" folder.
- Never touch system folders, hidden files or files outside the folder named.
- Keep file extensions unchanged when renaming.
