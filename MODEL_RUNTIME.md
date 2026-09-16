# Adaptive Multi-Model Runtime — v0.13

## Goal

Keep Living Assistant lightweight on small machines while eliminating unnecessary model swaps on systems that can safely retain multiple local models.

The assistant controls **two separate budgets**:

1. **Resident models** — how many distinct models may remain warm in Ollama memory.
2. **Concurrent generations** — how many inference requests may execute at the same time.

They are intentionally not treated as the same thing. A machine may keep two models warm but still serialize generation if configuration or thermal pressure requires it.

## Automatic policy

Default thresholds are conservative:

| Hardware | Default residency |
|---|---:|
| Lite profile / low-memory machine | 1 |
| Dedicated GPU below 16 GB VRAM | 1 |
| Dedicated GPU 16–23.9 GB VRAM | 2 |
| Dedicated GPU 24+ GB VRAM | 3 |
| Apple Silicon 32–63.9 GB unified memory | 2 |
| Apple Silicon 64+ GB unified memory | 3 |
| CPU-only/system RAM 48–95.9 GB | 2 |
| CPU-only/system RAM 96+ GB | 3 |

A 32-GB laptop with a GTX 1650 4 GB therefore remains **1 resident / 1 generation** by default.

The policy is in `model_runtime` inside `assistant.yaml`. `mode: single` always forces one model. `max_resident_models` and `max_concurrent_generations` can reduce automatic limits. Increasing beyond the hardware-derived residency ceiling requires the explicit `force_max_resident: true` escape hatch and is not recommended without measurement.

## Memory admission

Before adding another resident model, Living Assistant checks available system RAM and, for dedicated NVIDIA GPUs, current free VRAM. Model file size from Ollama's local inventory is used only as a conservative estimate; Ollama remains the final memory allocator.

When an additional model cannot fit safely, the manager evicts the least-recently-used idle model. If every candidate is currently in use, the request waits for a bounded admission timeout instead of force-unloading an active generation.

The first/only model may still use Ollama's normal CPU/GPU partial-offload behavior.

## Concurrency

By default `max_parallel_per_model: 1`. This matters because parallel requests to the same model can multiply context/KV-cache memory. Capable systems can still execute **different resident models** concurrently up to `max_concurrent_generations`.

The manager uses leases so an in-use model is not selected for LRU eviction.

## Thermal guard

Where temperature telemetry is available, v0.13 reads NVIDIA GPU temperature through `nvidia-smi` and CPU/system sensors through `psutil`. If a configured threshold is exceeded, additional concurrency is throttled so one active generation can finish while new work waits.

Defaults:

```yaml
model_runtime:
  thermal_guard_enabled: true
  max_gpu_temperature_c: 83
  max_cpu_temperature_c: 90
```

Sensor support varies by operating system. If no trustworthy temperature sensor is exposed, the runtime falls back to RAM/VRAM pressure safeguards rather than inventing a value.

## Ollama interaction

Living Assistant uses:

- `GET /api/ps` to inspect loaded models.
- an empty `/api/chat` request to preload a model.
- `keep_alive: 0` to unload a model.
- a longer keep-alive while adaptive multi-model residency is active.

Living Assistant **does not** modify the Ollama service environment automatically. `organism doctor` reports suggested values for `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL`; the user controls the Ollama service configuration.

## Commands

```bash
organism doctor
organism model status
organism model status --refresh
organism model preload qwen3.5:2b
organism model unload qwen3.5:2b
organism model sleep
```

Local API:

```text
GET  /models/status
POST /models/preload
POST /models/unload
```

## Safety behavior

- Lite stays single-model in automatic mode.
- Low dedicated VRAM wins over abundant system RAM for automatic GPU residency.
- In-use models are not LRU-evicted.
- Same-model requests are serialized by default.
- Additional model admission is denied/evicted under memory pressure.
- High detected temperature reduces effective concurrency.
- All waits are bounded by `admission_timeout_seconds`.
- `organism model sleep` unloads only idle models; it does not kill a live generation.
