from __future__ import annotations
from dataclasses import dataclass
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

def project_root() -> Path:
    # Works in editable install and source tree.
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "assistant.yaml").exists():
            return parent
    return Path.cwd()

def data_dir() -> Path:
    p = Path(user_data_dir("LivingAssistant", "LivingAssistant"))
    p.mkdir(parents=True, exist_ok=True)
    return p

def load_config(path: str | Path | None = None) -> dict:
    cfg_path = Path(path) if path else project_root() / "config" / "assistant.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return _expand_env(raw)
