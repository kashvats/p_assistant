---
name: web-app-python
description: "Build a complete, runnable Python web application (Flask + SQLite + Jinja templates + pytest) in its own virtual environment - the default stack for web apps, shops, blogs and dashboards built on this machine."
---

# Web app (Python, Flask, SQLite)

## Layout (relative to the project folder)
```
requirements.txt        flask>=3.0  and  pytest>=8.0  (one per line)
app.py                  create_app(test_config=None) factory + routes, runs with `python app.py`
db.py                   get_db(), init_db(), schema in schema.sql, seed data function
schema.sql              CREATE TABLE statements
templates/base.html     layout with nav; every page extends it
templates/*.html        one template per page
static/style.css        simple clean CSS (no build step)
tests/test_app.py       pytest tests using app.test_client()
README.md               setup, run, test
```

## Commands (Windows, run_command with no cwd = the project folder)
- This is Windows cmd: no `mkdir -p`, `touch`, `cat`, `&&` chains of `cd`. Create folders and files with write_file
  (missing folders are created for you); never `cd` into the project, you are already in it.
- Create env: `python -m venv .venv`
- Install: `.venv\Scripts\python -m pip install -r requirements.txt` (asks the user once; wait for it)
- Run tests: `.venv\Scripts\python -m pytest -q`
- Start the app (only to check it boots, then stop it): use start_process with `.venv\Scripts\python app.py`

## Rules that make it work
1. Use the app factory: `def create_app(test_config=None)`; `DATABASE` path in `app.config`, default `instance/app.sqlite`; tests pass a temp path.
2. `init_db()` runs schema.sql and seeds sample data so pages are never empty.
3. Use `sqlite3` with `row_factory = sqlite3.Row` and `?` placeholders only (never string formatting in SQL).
4. Templates: Jinja auto-escaping stays on. Forms use POST and redirect after success (POST/redirect/GET). Show flash messages.
5. Sessions: set `SECRET_KEY` from the environment with a dev default. Passwords: `werkzeug.security.generate_password_hash` / `check_password_hash`.
6. Every route the requirements name gets at least one test: status code 200 (or redirect) and expected text in the page.
7. Prove it: tests pass when YOU run them; report the exact command and the summary line (e.g. `8 passed`).
