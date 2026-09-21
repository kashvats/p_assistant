from __future__ import annotations
import time
from living_assistant.tools.shell import ProcessRegistry


def test_managed_process_receives_project_environment(tmp_path):
    registry=ProcessRegistry(tmp_path/'processes.json')
    output=tmp_path/'port.txt'
    result=registry.start(
        "python -c \"import os,pathlib; pathlib.Path('port.txt').write_text(os.environ.get('PORT',''))\"",
        str(tmp_path), project='app', env={'PORT':'4321'}
    )
    assert result['ok'] is True
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and not output.exists():
        time.sleep(0.05)
    assert output.read_text()=='4321'
    stored=registry.get(result['id'])
    assert stored['env']=={'PORT':'4321'}
