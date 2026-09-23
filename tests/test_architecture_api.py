from __future__ import annotations

from pathlib import Path

from living_assistant import api
from living_assistant.api_routes import (
    assistant,
    desktop,
    improvements,
    integrations,
    models,
    personal,
    peers,
    security,
    ui,
    workspace,
)


def test_api_is_split_into_domain_routers_without_duplicate_routes():
    routers = [
        assistant.router,
        desktop.router,
        improvements.router,
        integrations.router,
        models.router,
        personal.router,
        peers.router,
        security.router,
        ui.router,
        workspace.router,
    ]
    assert all(router.routes for router in routers)

    def leaf_routes(routes):
        for route in routes:
            nested_router = getattr(route, "original_router", None)
            if nested_router is not None:
                yield from leaf_routes(nested_router.routes)
            else:
                yield route

    route_keys = []
    for route in leaf_routes(api.app.routes):
        path = getattr(route, "path", "")
        if path.startswith(("/docs", "/redoc", "/openapi.json")):
            continue
        methods = tuple(sorted(getattr(route, "methods", ()) or ()))
        route_keys.append((path, methods))

    assert len(route_keys) == 123
    assert len(route_keys) == len(set(route_keys))


def test_api_bootstrap_is_no_longer_the_monolithic_route_file():
    source = Path(api.__file__).read_text(encoding="utf-8")
    assert len(source.splitlines()) < 250
    assert "app.include_router(security_router)" in source
    assert "app.include_router(improvements_router)" in source
