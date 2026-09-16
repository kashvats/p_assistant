# Release Validation — Living Assistant v0.14.0

## Scope

Cumulative validation of v0.14 Desktop Intelligence on top of v0.13 Adaptive Multi-Model Runtime and all earlier releases.

## Automated checks

- Full cumulative pytest suite: **170/170 passed**.
- Python source compilation: passed.
- Bundled dashboard JavaScript `node --check`: passed.
- Wheel build: passed.
- Wheel installed into an isolated target directory: passed.
- Installed package reports version `0.14.0`: passed.
- Packaged desktop configuration: passed.
- Installed `/health`: passed.
- Installed `/desktop/status`: passed.
- Local API Host-header rejection retained: passed.
- Vision remains disabled by default: passed.
- Remote vision is blocked unless explicitly permitted: covered by regression tests.
- Desktop input and semantic/screenshot reads remain approval-gated: covered by regression tests.

## Platform validation boundary

The semantic and control adapters are implemented for Windows, macOS and Linux, but this build environment can only exercise the Linux capability-detection path. Real accessibility permissions, Wayland/X11 behavior, elevated-window boundaries, multi-monitor geometry, and native mouse/keyboard injection must be validated on actual Windows/Ubuntu/macOS machines before v1.0.

The local vision fallback is API-tested but not benchmarked against a real multimodal Ollama model in this sandbox.
