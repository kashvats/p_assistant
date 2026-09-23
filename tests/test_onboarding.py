from pathlib import Path
import yaml
from typer.testing import CliRunner

from living_assistant.system.onboarding import OnboardingManager
from living_assistant.connectors import ConnectorRegistry
from living_assistant.cli import app


def seed_config(tmp_path):
    source=Path(__file__).resolve().parents[1]/'src'/'living_assistant'/'default_config.yaml'
    target=tmp_path/'assistant.yaml'
    target.write_text(source.read_text())
    return target


def test_onboarding_updates_workspace_model_voice_and_connector_without_secret(tmp_path):
    config_path=seed_config(tmp_path)
    registry=ConnectorRegistry(tmp_path/'connectors.json')
    manager=OnboardingManager(registry, config_path=config_path)
    ws=tmp_path/'workspace'
    result=manager.complete(
        workspace_root=str(ws), profile='lite', model='qwen3.5:1.5b', voice_enabled=False,
        connector={
            'name':'phone','provider':'telegram','kind':'messaging',
            'capabilities':['messages.read','messages.send'],'env_prefix':'PHONE','settings':{},
        },
    )
    assert result['ok'] is True and ws.is_dir()
    cfg=yaml.safe_load(config_path.read_text())
    assert cfg['onboarding']['completed'] is True
    assert cfg['workspace_roots']==[str(ws.resolve())]
    assert cfg['voice']['enabled'] is False
    assert set(cfg['profiles']['lite']['models'].values())=={'qwen3.5:1.5b'}
    raw=(tmp_path/'connectors.json').read_text()
    assert 'BOT_TOKEN' not in raw and 'secret' not in raw.lower()
    assert registry.get('phone')['capabilities']==['messages.read','messages.send']


def test_onboarding_rejects_invalid_model_and_overbroad_connector_capability(tmp_path):
    config_path=seed_config(tmp_path)
    manager=OnboardingManager(ConnectorRegistry(tmp_path/'connectors.json'), config_path=config_path)
    try:
        manager.complete(workspace_root=str(tmp_path/'ws'),profile='lite',model='bad model',voice_enabled=True)
        assert False, 'invalid model accepted'
    except ValueError:
        pass
    try:
        manager.complete(
            workspace_root=str(tmp_path/'ws'),profile='lite',model='qwen3.5:0.8b',voice_enabled=True,
            connector={'name':'phone','provider':'telegram','kind':'messaging','capabilities':['mail.send']},
        )
        assert False, 'invalid capability accepted'
    except ValueError:
        pass


def test_cli_exposes_onboard_command():
    result=CliRunner().invoke(app,['--help'])
    assert result.exit_code==0
    assert 'onboard' in result.stdout

def test_load_config_prefers_completed_user_config_when_no_explicit_path(tmp_path, monkeypatch):
    import living_assistant.core.config as c
    user_cfg=seed_config(tmp_path)
    raw=yaml.safe_load(user_cfg.read_text())
    raw['workspace_roots']=['/custom/onboarded']
    user_cfg.write_text(yaml.safe_dump(raw,sort_keys=False))
    monkeypatch.setattr(c,'user_config_path',lambda:user_cfg)
    monkeypatch.delenv('ASSISTANT_CONFIG',raising=False)
    assert c.load_config()['workspace_roots']==['/custom/onboarded']
