# Living Assistant v0.13.0 Release Validation

## Scope

Cumulative release based on v0.12.0, adding the Adaptive Multi-Model Runtime while retaining the hardened security, interaction, voice and connector layers.

## Automated validation

- Full source regression suite: **159 passed**.
- Python source/tests compilation: PASS.
- Dashboard JavaScript syntax (`node --check`): PASS.
- Focused v0.13 model-runtime suite: PASS.
- Built wheel: `living_assistant-0.13.0-py3-none-any.whl`.
- Installed-wheel import/version from outside source checkout: PASS (`0.13.0`).
- Packaged default configuration: PASS.
- Packaged dashboard asset: PASS.
- `organism --help` through installed wheel: PASS.
- `organism model status --no-refresh` through installed wheel: PASS.
- Installed API `/health`, `/status`, `/models/status`: PASS.
- Existing Host-header and Origin protections from the installed wheel: PASS.

## Model-runtime coverage

Regression tests cover:

- 4-GB dedicated-GPU single-model fallback;
- 16-GB and 24-GB dedicated-VRAM residency thresholds;
- Apple Silicon 32-GB and 64-GB unified-memory thresholds;
- lite-profile forced single-model behavior;
- explicit single-model override;
- LRU eviction;
- resource-pressure eviction;
- combined resident-model VRAM budget checks;
- longer multi-model keep-alive/preload behavior;
- concurrency of distinct models;
- same-model serialization by default;
- thermal-pressure serialization;
- Ollama `/api/ps` synchronization;
- local model-runtime API controls;
- compatibility with older/custom managers exposing only `activate()`.

## Artifact-test environment note

The sandbox's newly created Python virtual environments do not inherit the harness's preinstalled FastAPI/Typer/PyYAML dependency set even when `--system-site-packages` is requested, and external package fetching is unavailable. Therefore the installed-artifact gate installs **only the Living Assistant wheel** into an isolated target directory and runs it with the harness's already-installed dependency set. This validates that Living Assistant code/config/assets come from the wheel without claiming a network dependency installation occurred.

## Remaining real-hardware validation

Automated tests simulate resource policies and thread concurrency. Before v1.0, validate actual Ollama multi-model residency, VRAM behavior and temperature telemetry on real NVIDIA high-VRAM hardware and Apple Silicon. The primary GTX 1650 4-GB target is intentionally configured to remain single-model by default.
