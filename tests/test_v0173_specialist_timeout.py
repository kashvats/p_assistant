import time

from living_assistant.agents import SpecialistRouter


class SlowProvider:
    def chat(self, *args, **kwargs):
        time.sleep(0.3)
        return {'message': {'content': 'late'}}


class FakeManager:
    max_concurrent_generations = 1
    def __init__(self):
        self.provider = SlowProvider()
    def activate(self, model, **kwargs):
        return None


def test_specialist_delegate_returns_on_timeout_instead_of_hanging():
    router = SpecialistRouter(
        FakeManager(), {'general': 'g'}, timeout_seconds=1.0,
    )
    # Constructor enforces a production minimum of 1 second; lower it directly for
    # this deterministic regression test without weakening the runtime default.
    router.timeout_seconds = 0.05
    started = time.monotonic()
    result = router.delegate('general', 'slow task')
    elapsed = time.monotonic() - started
    assert result['ok'] is False and result['timeout'] is True
    assert elapsed < 0.2
