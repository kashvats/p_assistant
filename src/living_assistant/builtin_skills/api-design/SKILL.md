---
name: api-design
description: "Design HTTP/JSON APIs or module interfaces: routes, request and response shapes, errors and validation - use when parts of a system must agree on a contract."
---

# Api design

## When to use
A backend, service or module boundary needs a defined contract.

## Steps
1. List the resources and the operations the clients need (from the requirements, not more).
2. For each operation define: method and path (or function signature), input fields with types and limits, output shape, and error responses with status codes.
3. Validate all input at the boundary; reject unknown or oversized values.
4. Write the contract down (OpenAPI snippet, markdown table, or typed stubs) where the task says.

## Rules and checks
- Consistent naming and error format across all routes.
- Never return secrets, stack traces or internal paths in errors.
