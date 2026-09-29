from __future__ import annotations

import struct

from living_assistant.system import llama_server as ls
from living_assistant.system.llama_server import (
    GpuDevice,
    LlamaServerManager,
    choose_device,
    gguf_expert_count,
    parse_devices,
)

LIST_DEVICES = """load_backend: loaded Vulkan backend
Available devices:
  Vulkan0: AMD Radeon(TM) Graphics (16304 MiB, 15488 MiB free)
  Vulkan1: NVIDIA GeForce GTX 1650 (4149 MiB, 3558 MiB free)
"""


def _gguf(path, keys):
    """Write a minimal GGUF header with the given (key, uint32 value) pairs."""
    with open(path, "wb") as fh:
        fh.write(b"GGUF" + struct.pack("<IQQ", 3, 0, len(keys)))
        for key, value in keys:
            raw = key.encode()
            fh.write(struct.pack("<Q", len(raw)) + raw)
            if isinstance(value, str):
                v = value.encode()
                fh.write(struct.pack("<IQ", 8, len(v)) + v)
            else:
                fh.write(struct.pack("<II", 4, value))
    return path


def _manager(tmp_path, monkeypatch, devices_text=LIST_DEVICES, **cfg):
    model = tmp_path / "model.gguf"
    if not model.exists():
        _gguf(model, [("general.architecture", "qwen3moe"), ("qwen3moe.expert_count", 128)])
    exe = tmp_path / "llama-server.exe"
    exe.write_text("")
    m = LlamaServerManager({"model_path": str(model), "binary": str(exe), "threads": 6, **cfg}, tmp_path)
    monkeypatch.setattr(m, "devices", lambda: parse_devices(devices_text))
    return m


def test_parse_devices_and_prefer_discrete_gpu_over_integrated():
    devices = parse_devices(LIST_DEVICES)
    assert [d.id for d in devices] == ["Vulkan0", "Vulkan1"]
    assert devices[0].integrated and not devices[1].integrated
    chosen, _ = choose_device(devices)
    assert chosen.id == "Vulkan1"


def test_no_gpu_or_only_integrated_gpu_falls_back_to_cpu():
    assert choose_device([])[0] is None
    only_igpu = [GpuDevice("Vulkan0", "Intel(R) UHD Graphics", 8000, 7000)]
    assert choose_device(only_igpu)[0] is None
    assert choose_device(parse_devices(LIST_DEVICES), "cpu")[0] is None
    tiny = [GpuDevice("CUDA0", "NVIDIA GeForce GT 710", 1024, 900)]
    assert choose_device(tiny)[0] is None  # not enough free VRAM to help


def test_gguf_expert_count_detects_moe_and_dense(tmp_path):
    moe = _gguf(tmp_path / "moe.gguf", [("general.architecture", "qwen3moe"), ("qwen3moe.expert_count", 128)])
    dense = _gguf(tmp_path / "dense.gguf", [("general.architecture", "llama"), ("tokenizer.ggml.model", "gpt2")])
    assert gguf_expert_count(moe) == 128
    assert gguf_expert_count(dense) == 0
    (tmp_path / "junk.gguf").write_bytes(b"not a gguf")
    assert gguf_expert_count(tmp_path / "junk.gguf") == 0


def test_gpu_plan_keeps_moe_experts_in_ram(tmp_path, monkeypatch):
    plan = _manager(tmp_path, monkeypatch).build_plan()
    assert plan.mode == "gpu"
    argv = " ".join(plan.argv)
    assert "-dev Vulkan1" in argv and "-ngl 99" in argv and "--cpu-moe" in argv
    assert "-np 1" in argv and "-ub 2048" in argv


def test_dense_model_on_gpu_uses_llama_cpp_fit(tmp_path, monkeypatch):
    _gguf(tmp_path / "model.gguf", [("general.architecture", "llama")])
    plan = _manager(tmp_path, monkeypatch).build_plan()
    assert plan.mode == "gpu" and "--fit on" in " ".join(plan.argv) and "--cpu-moe" not in plan.argv


def test_machine_without_gpu_gets_cpu_plan(tmp_path, monkeypatch):
    plan = _manager(tmp_path, monkeypatch, devices_text="Available devices:\n").build_plan()
    assert plan.mode == "cpu"
    assert plan.argv[plan.argv.index("-dev") + 1] == "none"
    assert plan.argv[plan.argv.index("-ngl") + 1] == "0"


def test_failed_gpu_launch_retries_on_cpu(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    launched = []

    class FakeProc:
        def __init__(self, ok):
            self.ok = ok

        def poll(self):
            return None if self.ok else 1

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    def fake_spawn(plan):
        launched.append(plan.mode)
        return FakeProc(ok=plan.mode == "cpu")

    health = {"up": False}
    monkeypatch.setattr(m, "_spawn", fake_spawn)
    monkeypatch.setattr(m, "healthy", lambda timeout=2.0: health["up"])

    def wait_ready(proc, timeout):
        health["up"] = proc.ok
        return proc.ok

    monkeypatch.setattr(m, "_wait_ready", wait_ready)
    status = m.ensure_running()
    assert launched == ["gpu", "cpu"]
    assert status["running"] is True and status["plan"]["mode"] == "cpu"


def test_existing_server_is_reused_and_never_launched_over(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "healthy", lambda timeout=2.0: True)
    monkeypatch.setattr(m, "_spawn", lambda plan: (_ for _ in ()).throw(AssertionError("must not launch")))
    status = m.ensure_running()
    assert status["external"] is True and status["managed"] is False


def test_missing_binary_or_model_reports_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "find_llama_server", lambda configured=None: None)
    m = LlamaServerManager({"model_path": str(tmp_path / "missing.gguf")}, tmp_path)
    monkeypatch.setattr(m, "healthy", lambda timeout=2.0: False)
    status = m.ensure_running()
    assert status["running"] is False and "llama-server was not found" in status["last_error"]
