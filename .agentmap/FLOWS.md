# Execution Flows

> Maintain durable request, service, event, queue, and data flows here.
> Do not regenerate this file automatically.

Example:

```text
POST /api/login
→ api/auth.py::login
→ services/auth.py::authenticate
→ repositories/users.py::find_by_email
→ database
```
