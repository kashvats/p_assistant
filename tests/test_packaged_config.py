from importlib import resources
from pathlib import Path
import living_assistant.config as cfgmod


def test_packaged_default_config_resource_exists():
    resource = resources.files("living_assistant").joinpath("default_config.yaml")
    assert resource.is_file()
    assert "profiles:" in resource.read_text(encoding="utf-8")


def test_installed_mode_uses_packaged_config_and_user_data(monkeypatch, tmp_path):
    monkeypatch.setattr(cfgmod, "source_root", lambda: None)
    monkeypatch.setattr(cfgmod, "data_dir", lambda: tmp_path)
    cfg = cfgmod.load_config()
    assert "profiles" in cfg
    assert cfgmod.project_root() == tmp_path


def test_assistant_config_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("profile: lite\nprofiles: {}\nworkspace_roots: []\n", encoding="utf-8")
    monkeypatch.setenv("ASSISTANT_CONFIG", str(custom))
    cfg = cfgmod.load_config()
    assert cfg["profile"] == "lite"
    assert cfg["workspace_roots"] == []
