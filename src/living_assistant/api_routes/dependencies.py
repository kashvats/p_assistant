from __future__ import annotations

from living_assistant.core.runtime import Runtime


def runtime() -> Runtime:
    # Resolve through living_assistant.api at call time to preserve the public
    # compatibility surface for integrations/tests that monkeypatch get_runtime.
    from living_assistant import api as api_module

    return api_module._rt()


def authorize(authorization: str | None = None, token: str | None = None) -> None:
    # Same compatibility rationale as runtime().
    from living_assistant import api as api_module

    auth_fn = getattr(api_module, "_auth")
    if token:
        try:
            auth_fn(authorization, token_param=token)
            return
        except TypeError:
            pass
    auth_fn(authorization)
