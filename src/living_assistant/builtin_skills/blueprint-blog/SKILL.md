---
name: blueprint-blog
description: "Product blueprint for a blog / content site / CMS: features, data model, pages, acceptance criteria and a task breakdown - use when planning or building a blog, news site or simple CMS."
---

# Blueprint: blog

Stack unless the user asks otherwise: the `web-app-python` skill (Flask + SQLite + pytest).

## Minimum viable features
1. Public: home page with the newest published posts (title, date, excerpt), paginated (5 per page); post page by slug; tag pages; search by title/body; an RSS feed at /feed.xml.
2. Comments: readers add a comment (name + text) to a post; comments wait for approval before they show.
3. Author/admin (login required): create, edit, publish/unpublish and delete posts; approve or delete comments.
4. Post body is plain text with paragraphs (or Markdown only if the `markdown` package is in requirements); always escaped - no raw user HTML.

## Data model
posts(id, title, slug UNIQUE, body, excerpt, published, created_at, updated_at)
tags(id, name, slug); post_tags(post_id, tag_id)
comments(id, post_id, author, body, approved, created_at)
users(id, username, password_hash)

## Acceptance criteria to give the tasks
- Home shows only published posts, newest first, 5 per page with next/previous links.
- A post page shows its body, tags and approved comments only.
- Submitting a comment stores it unapproved; after admin approval it appears.
- Admin pages require login; creating a post with a title generates a unique slug.
- /feed.xml is valid RSS listing published posts.
- `python -m pytest -q` passes with tests for each item above.

## Suggested tasks (adapt to the request)
1. Infra: project setup (venv, requirements, app factory, db + schema + seed posts, base template, CSS, test fixture).
2. Backend: public pages - home with pagination, post page, tags, search, RSS (with tests).
3. Backend: comments with moderation (with tests).
4. Backend: admin login and post management (with tests).
5. Frontend/design: readable typography, layout, nav, empty states.
6. QA: edge cases (unpublished post 404, duplicate slugs, empty search) and a full test run.
7. Docs: README.
