from __future__ import annotations
from importlib import resources
from pathlib import Path
import os, re, yaml
from platformdirs import user_data_dir

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


def _expand_env(value):
    if isinstance(value, str):
        def repl(match):
            key, default = match.group(1), match.group(2)
            return os.environ.get(key, default or "")
        return ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_expand_env(x) for x in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def source_root() -> Path | None:
    """Return the repository root when running from a source checkout/editable tree."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "config" / "assistant.yaml").exists():
            return parent
    return None


def data_dir() -> Path:
    p = Path(user_data_dir("LivingAssistant", "LivingAssistant"))
    p.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            p.chmod(0o700)
        except OSError:
            pass
    return p



def user_config_path() -> Path:
    return data_dir() / "assistant.yaml"


def active_config_path() -> Path | None:
    explicit = os.environ.get("ASSISTANT_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()
    user_path = user_config_path()
    if user_path.exists():
        return user_path.resolve()
    root = source_root()
    if root is not None:
        return (root / "config" / "assistant.yaml").resolve()
    return None

def project_root() -> Path:
    """Writable base for relative runtime paths.

    In a source checkout this is the repository root. In an installed wheel it is
    the per-user application data directory, never site-packages or an arbitrary cwd.
    """
    return source_root() or data_dir()


def _default_config_text() -> str:
    root = source_root()
    if root is not None:
        return (root / "config" / "assistant.yaml").read_text(encoding="utf-8")
    return resources.files("living_assistant").joinpath("default_config.yaml").read_text(encoding="utf-8")


def load_config(path: str | Path | None = None) -> dict:
    explicit = path or os.environ.get("ASSISTANT_CONFIG")
    if explicit:
        raw_text = Path(explicit).expanduser().read_text(encoding="utf-8")
    elif user_config_path().exists():
        raw_text = user_config_path().read_text(encoding="utf-8")
    else:
        raw_text = _default_config_text()
    raw = yaml.safe_load(raw_text)
    if not isinstance(raw, dict):
        raise ValueError("Assistant configuration must be a YAML mapping.")
    return _expand_env(raw)
