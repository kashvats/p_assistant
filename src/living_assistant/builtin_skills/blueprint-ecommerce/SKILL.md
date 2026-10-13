---
name: blueprint-ecommerce
description: "Product blueprint for an online shop / e-commerce store: features, data model, pages, acceptance criteria and a task breakdown - use when planning or building a shop, store or e-commerce site."
---

# Blueprint: e-commerce shop

Stack unless the user asks otherwise: the `web-app-python` skill (Flask + SQLite + pytest).

## Minimum viable features
1. Catalog: product list with categories and a search box; product page (name, price, description, image URL, stock).
2. Cart: add / change quantity / remove, kept in the session; cart total.
3. Checkout: customer name, email, address; creates an order with its items and total; reduces stock; confirmation page with the order number. Payment is simulated ("pay on delivery") - never take real card data.
4. Orders: an order status (new, paid, shipped, cancelled).
5. Admin (login required): add / edit / delete products, list orders and change their status. Seed one admin user from an environment variable or a printed dev password.

## Data model
products(id, name, slug, description, price_cents, image_url, stock, category_id)
categories(id, name, slug)
orders(id, number, customer_name, email, address, total_cents, status, created_at)
order_items(id, order_id, product_id, name, price_cents, quantity)
users(id, username, password_hash, is_admin)
Money is stored in integer cents and shown with two decimals.

## Acceptance criteria to give the tasks
- The home page lists the seeded products; a category filter and search narrow the list.
- Adding two items to the cart shows the right line totals and grand total.
- Checking out creates an order, empties the cart, lowers stock, and shows the order number.
- Checkout refuses quantities above stock and an empty cart.
- Admin pages redirect to login when not logged in; a logged-in admin can create a product that then appears in the catalog.
- `python -m pytest -q` passes with tests for each item above.

## Suggested tasks (adapt to the request)
1. Infra: project setup (venv, requirements, app factory, db + schema + seed, base template, CSS, test fixture).
2. Backend: catalog + categories + search (with tests).
3. Backend: cart and checkout with stock rules (with tests).
4. Backend: admin login + product management + order status (with tests).
5. Frontend/design: templates and styling for all pages, consistent nav, empty and error states.
6. QA: extra edge-case tests and a full test run.
7. Docs: README (setup, run, admin login, tests).
