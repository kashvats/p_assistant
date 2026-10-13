---
name: database-design
description: "Design data models, schemas, migrations and queries (SQLite, PostgreSQL, JSON files) with integrity rules - use for data modelling and storage tasks."
---

# Database design

## When to use
A task needs a data model, a schema, a migration, or efficient queries.

## Steps
1. List the entities, their fields with types, and the relationships between them.
2. Choose keys, required fields, unique constraints and foreign keys; add indexes for the lookups the features need.
3. Write the schema or migration as code (SQL file or the project's ORM) and seed data only if asked.
4. Test it: create the database with the shell tool and run the main queries once.

## Rules and checks
- Never drop or rewrite existing user data without explicit approval.
- Parameterized queries only.
