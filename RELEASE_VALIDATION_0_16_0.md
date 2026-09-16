# Living Assistant v0.16.0 Release Validation

## Release gate

- Python compilation: PASS
- Full cumulative source suite: **211 passed**
- v0.16 focused platform-hardening suite: **17 passed**
- Linux/macOS shell installer syntax (`bash -n`): PASS
- Wheel build: PASS
- Installed-wheel import/version: PASS (`0.16.0`)
- Installed packaged default config: PASS
- Installed `organism platform status`: PASS
- Installed `/health`: PASS (`0.16.0`)
- Installed `/platform/status`: PASS
- Local API hostile Host rejection: PASS (HTTP 400)
- Wheel contents include `platform_hardening.py`, packaged config, dashboard and macOS Endpoint Security helper: PASS

## v0.16 regression coverage

The focused tests cover:

- native symlink preference;
- Windows-style symlink privilege denial and directory-junction fallback;
- correct CPython `_winapi.CreateJunction(target, link)` argument order;
- file hard-link fallback and shared-content semantics;
- explicit-only copy fallback;
- no traversal through simulated reparse/junction directory boundaries;
- integrity scanner refusing to traverse directory symlinks;
- workspace listing with broken links;
- capability probe cleanup;
- sleep/resume gap detection;
- daemon resume revalidation and model resynchronization;
- filesystem-watch rebaseline after resume;
- safer user-service installer patterns;
- Windows bootstrap independent of `Activate.ps1`;
- platform API/version surfaces.

## Artifact note

Cross-platform OS APIs are unit-tested/simulated from the build environment, but final v1.0 certification still requires physical/VM validation on ordinary Windows, Ubuntu/Linux and macOS user accounts. In particular, Windows standard-user junction/symlink behavior, macOS LaunchAgent/permission prompts and real suspend/resume cycles cannot be truthfully certified from this Linux build environment alone.
