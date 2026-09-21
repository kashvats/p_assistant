from __future__ import annotations
from dataclasses import dataclass
from types import SimpleNamespace
import threading
import time

from living_assistant.hardware import HardwareInfo
from living_assistant.resource_manager import ResourceManager, ModelRuntimePolicy
from living_assistant.model_provider import ModelManager


def hw(ram=32, *, vram=None, free=None, apple=False, os_name='Linux'):
    return HardwareInfo(
        os_name, 'arm64' if apple else 'x86_64', 8, 16, float(ram), float(ram)-2,
        'Apple Silicon (unified memory)' if apple else ('Test GPU' if vram is not None else None),
        vram, free if free is not None else vram, 1 if (apple or vram is not None) else 0,
        apple, apple,
    )


def cfg(**runtime):
    base = {
        'profile': 'auto',
        'model_runtime': {
            'mode': 'auto',
            'reserve_ram_gb_by_profile': {'lite': 1, 'balanced': 3, 'power': 6},
            'reserve_vram_gb': 1,
            'dedicated_vram_gb_for_two': 16,
            'dedicated_vram_gb_for_three': 24,
            'apple_unified_memory_gb_for_two': 32,
            'apple_unified_memory_gb_for_three': 64,
            'cpu_ram_gb_for_two': 48,
            'cpu_ram_gb_for_three': 96,
            'resident_keep_alive_seconds': 300,
            'admission_timeout_seconds': 2,
            'max_parallel_per_model': 1,
        }
    }
    base['model_runtime'].update(runtime)
    return base


def test_4gb_gpu_stays_single_model():
    rm = ResourceManager('balanced', cfg(), hardware=hw(32, vram=4, free=4))
    assert rm.model_policy.max_resident_models == 1
    assert rm.model_policy.max_concurrent_generations == 1
    assert rm.model_policy.mode == 'single'


def test_16gb_gpu_enables_two_models():
    rm = ResourceManager('balanced', cfg(), hardware=hw(32, vram=16, free=16))
    assert rm.model_policy.max_resident_models == 2
    assert rm.model_policy.max_concurrent_generations == 2
    assert rm.model_policy.mode == 'multi'


def test_24gb_gpu_enables_three_models():
    rm = ResourceManager('balanced', cfg(), hardware=hw(32, vram=24, free=24))
    assert rm.model_policy.max_resident_models == 3
    assert rm.model_policy.max_concurrent_generations == 3


def test_apple_unified_memory_thresholds():
    assert ResourceManager('balanced', cfg(), hardware=hw(32, apple=True, os_name='Darwin')).model_policy.max_resident_models == 2
    assert ResourceManager('power', cfg(), hardware=hw(64, apple=True, os_name='Darwin')).model_policy.max_resident_models == 3


def test_lite_profile_always_single_in_auto_mode():
    rm = ResourceManager('lite', cfg(), hardware=hw(64, vram=24, free=24))
    assert rm.model_policy.max_resident_models == 1


def test_explicit_single_overrides_high_end_hardware():
    rm = ResourceManager('power', cfg(mode='single'), hardware=hw(64, vram=24, free=24))
    assert rm.model_policy.max_resident_models == 1
    assert rm.model_policy.max_concurrent_generations == 1


@dataclass
class FakeResources:
    model_policy: ModelRuntimePolicy
    reject_additional: bool = False
    hot: bool = False

    def can_admit_model(self, size_bytes=None, resident_count=0, resident_size_bytes=0):
        if self.reject_additional and resident_count > 0:
            return False, 'simulated pressure'
        return True, 'ok'

    def can_start_model(self):
        return True, 'ok'

    def thermal_pressure(self):
        return (self.hot, 'simulated heat' if self.hot else 'ok')


class FakeProvider:
    def __init__(self):
        self.unloaded = []
        self.preloaded = []
        self.running = []

    def model_size_bytes(self, model):
        return 2 * 1024**3

    def unload(self, model):
        self.unloaded.append(model)

    def preload(self, model, keep_alive=300):
        self.preloaded.append((model, keep_alive))
        return {'done': True}

    def running_models(self):
        return list(self.running)


def policy(resident=2, concurrent=2, per_model=1, keep_alive=300):
    return ModelRuntimePolicy(
        mode='multi' if resident > 1 else 'single',
        max_resident_models=resident,
        max_concurrent_generations=concurrent,
        max_parallel_per_model=per_model,
        resident_keep_alive_seconds=keep_alive,
        admission_timeout_seconds=2,
        reserve_ram_gb=1,
        reserve_vram_gb=1,
        reason='test',
    )


def test_single_mode_evicts_previous_model():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(1, 1)))
    mm.activate('a')
    mm.activate('b')
    assert provider.unloaded == ['a']
    assert [x['model'] for x in mm.status()['resident_models']] == ['b']


def test_multi_mode_keeps_two_and_lru_evicts():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(2, 2)))
    mm.activate('a')
    mm.activate('b')
    mm.activate('a')  # touch A, making B the LRU
    mm.activate('c')
    assert provider.unloaded == ['b']
    assert [x['model'] for x in mm.status()['resident_models']] == ['a', 'c']


def test_pressure_evicts_idle_model_even_before_count_limit():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(3, 2), reject_additional=True))
    mm.activate('a')
    mm.activate('b')
    assert provider.unloaded == ['a']
    assert [x['model'] for x in mm.status()['resident_models']] == ['b']


def test_preload_uses_long_resident_keep_alive():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(2, 2, keep_alive=321)))
    result = mm.preload('coder')
    assert result['ok'] is True
    assert provider.preloaded == [('coder', 321)]


def test_distinct_models_can_hold_generation_leases_concurrently():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(2, 2, per_model=1)))
    both_inside = threading.Event()
    release = threading.Event()
    lock = threading.Lock()
    inside = set()

    def worker(model):
        with mm.lease(model):
            with lock:
                inside.add(model)
                if len(inside) == 2:
                    both_inside.set()
            release.wait(1)

    t1 = threading.Thread(target=worker, args=('a',))
    t2 = threading.Thread(target=worker, args=('b',))
    t1.start(); t2.start()
    assert both_inside.wait(1), mm.status()
    release.set(); t1.join(2); t2.join(2)
    assert not t1.is_alive() and not t2.is_alive()


def test_same_model_is_serialized_when_parallel_per_model_is_one():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(2, 2, per_model=1)))
    first_inside = threading.Event()
    release_first = threading.Event()
    second_inside = threading.Event()

    def first():
        with mm.lease('same'):
            first_inside.set()
            release_first.wait(1)

    def second():
        first_inside.wait(1)
        with mm.lease('same'):
            second_inside.set()

    t1 = threading.Thread(target=first); t2 = threading.Thread(target=second)
    t1.start(); t2.start()
    assert first_inside.wait(1)
    time.sleep(0.08)
    assert not second_inside.is_set()
    release_first.set()
    assert second_inside.wait(1)
    t1.join(2); t2.join(2)


def test_status_can_sync_provider_running_models():
    provider = FakeProvider()
    provider.running = [{'name': 'a', 'size': 100, 'size_vram': 80, 'expires_at': 'later'}]
    mm = ModelManager(provider, FakeResources(policy(2, 2)))
    status = mm.status(refresh=True)
    assert status['provider_running'][0]['name'] == 'a'
    assert status['resident_models'][0]['model'] == 'a'
    assert status['resident_models'][0]['size_vram_bytes'] == 80


def test_thermal_pressure_serializes_otherwise_parallel_models():
    provider = FakeProvider()
    resources = FakeResources(policy(2, 2, per_model=1), hot=True)
    mm = ModelManager(provider, resources)
    first_inside = threading.Event()
    release_first = threading.Event()
    second_inside = threading.Event()

    def first():
        with mm.lease('a'):
            first_inside.set()
            release_first.wait(1)

    def second():
        first_inside.wait(1)
        with mm.lease('b'):
            second_inside.set()

    t1 = threading.Thread(target=first); t2 = threading.Thread(target=second)
    t1.start(); t2.start()
    assert first_inside.wait(1)
    time.sleep(0.08)
    assert not second_inside.is_set()
    release_first.set()
    assert second_inside.wait(1)
    t1.join(2); t2.join(2)


def test_resource_thermal_guard_blocks_additional_residency(monkeypatch):
    rm = ResourceManager('balanced', cfg(), hardware=hw(32, vram=16, free=16))
    monkeypatch.setattr(rm, 'snapshot', lambda: {
        'cpu_percent': 10, 'ram_percent': 30, 'available_ram_gb': 20,
        'gpu_free_vram_gb': 12, 'gpu_temperature_c': 90,
    })
    ok, reason = rm.can_admit_model(2 * 1024**3, resident_count=1)
    assert not ok
    assert 'Thermal admission gate' in reason


def test_model_runtime_api_status_and_controls(monkeypatch):
    from fastapi.testclient import TestClient
    import living_assistant.api as api

    class H:
        def to_dict(self):
            return {'os': 'Linux', 'machine': 'x86_64', 'ram_gb': 32}

    class R:
        def snapshot(self):
            return {'cpu_percent': 1, 'ram_percent': 2, 'available_ram_gb': 20}

    class P:
        def status(self):
            return {'focus': False}

    class MM:
        active_model = 'a'
        def status(self, refresh=False):
            return {'active_model': self.active_model, 'resident_count': 2, 'policy': {'max_resident_models': 2}, 'refresh': refresh}
        def preload(self, model):
            return {'ok': True, 'model': model, 'action': 'preload'}
        def unload(self, model):
            return {'ok': True, 'model': model, 'action': 'unload'}

    fake = SimpleNamespace(profile='balanced', hardware=H(), resources=R(), personal=P(), model_manager=MM())
    monkeypatch.setattr(api, 'runtime', fake)
    monkeypatch.delenv('ASSISTANT_API_TOKEN', raising=False)
    monkeypatch.setenv('ASSISTANT_API_TOKEN', 'test-token')
    client = TestClient(api.app, headers={'Authorization':'Bearer test-token'})

    status = client.get('/status')
    assert status.status_code == 200
    assert status.json()['model_runtime']['resident_count'] == 2
    assert client.get('/models/status?refresh=true').json()['refresh'] is True
    assert client.post('/models/preload', json={'model': 'coder:4b'}).json()['action'] == 'preload'
    assert client.post('/models/unload', json={'model': 'coder:4b'}).json()['action'] == 'unload'


def test_combined_model_sizes_respect_total_vram_budget(monkeypatch):
    rm = ResourceManager('balanced', cfg(), hardware=hw(32, vram=16, free=16))
    monkeypatch.setattr(rm, 'snapshot', lambda: {
        'cpu_percent': 10, 'ram_percent': 30, 'available_ram_gb': 20,
        'gpu_free_vram_gb': 16,
    })
    # Two ~8 GiB model files plus runtime headroom should not be admitted merely
    # because the static hardware threshold allows two resident models.
    ok, reason = rm.can_admit_model(8 * 1024**3, resident_count=1, resident_size_bytes=8 * 1024**3)
    assert not ok
    assert 'VRAM residency budget' in reason


def test_lower_priority_background_model_cannot_evict_foreground_model():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(1, 1)))
    mm.admission_timeout_seconds = 0.08
    mm.activate('orchestrator', priority=100)

    import pytest
    from living_assistant.model_provider import ModelError
    with pytest.raises(ModelError):
        mm.activate('background-specialist', priority=30)

    assert provider.unloaded == []
    resident = mm.status()['resident_models']
    assert [item['model'] for item in resident] == ['orchestrator']
    assert resident[0]['priority'] == 100


def test_higher_priority_foreground_model_evicts_lower_priority_background_model():
    provider = FakeProvider()
    mm = ModelManager(provider, FakeResources(policy(1, 1)))
    mm.activate('background-specialist', priority=30)
    mm.activate('orchestrator', priority=100)
    assert provider.unloaded == ['background-specialist']
    assert [item['model'] for item in mm.status()['resident_models']] == ['orchestrator']
