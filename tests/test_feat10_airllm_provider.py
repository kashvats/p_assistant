from __future__ import annotations

from types import SimpleNamespace
import importlib as std_importlib
import tomllib

import pytest

import living_assistant.core.model_provider as model_provider
from living_assistant.model_provider import AirLLMProvider, CompositeModelProvider, ModelError


class _FakeInputIds:
    shape = (1, 3)

    def __init__(self):
        self.cuda_called = False

    def cuda(self):
        self.cuda_called = True
        return self


class _FakeTokenizer:
    def __init__(self):
        self.input_ids = _FakeInputIds()
        self.last_prompt = None
        self.last_tokenize_kwargs = None
        self.decoded = None

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        assert tokenize is False
        assert add_generation_prompt is True
        return "<chat>" + "|".join(f"{m['role']}:{m['content']}" for m in messages)

    def __call__(self, texts, **kwargs):
        self.last_prompt = texts[0]
        self.last_tokenize_kwargs = kwargs
        return {"input_ids": self.input_ids}

    def decode(self, tokens, skip_special_tokens=True):
        self.decoded = list(tokens)
        return "large-model answer"


class _FakeAirModel:
    def __init__(self):
        self.tokenizer = _FakeTokenizer()
        self.generate_calls = []

    def generate(self, input_ids, **kwargs):
        assert input_ids is self.tokenizer.input_ids
        self.generate_calls.append(kwargs)
        return SimpleNamespace(sequences=[[101, 102, 103, 201, 202]])


class _FakeAutoModel:
    calls = []
    model = _FakeAirModel()

    @classmethod
    def from_pretrained(cls, model_id, **kwargs):
        cls.calls.append((model_id, kwargs))
        return cls.model


@pytest.fixture(autouse=True)
def _reset_fake_model():
    _FakeAutoModel.calls = []
    _FakeAutoModel.model = _FakeAirModel()


def _install_fake_airllm(monkeypatch):
    real_import = std_importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "airllm":
            return SimpleNamespace(AutoModel=_FakeAutoModel)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(model_provider.importlib, "import_module", fake_import)


def test_airllm_is_lazy_optional_dependency(monkeypatch):
    real_import = std_importlib.import_module

    def missing(name, *args, **kwargs):
        if name == "airllm":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(model_provider.importlib, "import_module", missing)
    provider = AirLLMProvider(configured_models=["airllm:Qwen/Qwen3-32B"])

    # Inventory/status must not import or instantiate the optional package.
    assert provider.available_models() == ["airllm:Qwen/Qwen3-32B"]
    assert provider.model_size_bytes("airllm:Qwen/Qwen3-32B") is None

    with pytest.raises(ModelError, match=r'pip install -e ".\[airllm\]"'):
        provider.preload("airllm:Qwen/Qwen3-32B")


def test_airllm_uses_official_load_options_and_only_decodes_new_tokens(monkeypatch):
    _install_fake_airllm(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "hf_test_secret_value")
    provider = AirLLMProvider(
        configured_models=["airllm:Qwen/Qwen3-32B"],
        compression="4bit",
        layer_shards_saving_path="/tmp/airllm-shards",
        prefetching=True,
        delete_original=False,
        max_input_tokens=4096,
        max_new_tokens=64,
    )

    result = provider.chat(
        "airllm:Qwen/Qwen3-32B",
        [{"role": "user", "content": "hello"}],
        options={"num_ctx": 2048, "num_predict": 20},
    )

    assert _FakeAutoModel.calls == [(
        "Qwen/Qwen3-32B",
        {
            "prefetching": True,
            "delete_original": False,
            "compression": "4bit",
            "layer_shards_saving_path": "/tmp/airllm-shards",
            "hf_token": "hf_test_secret_value",
        },
    )]
    tokenizer = _FakeAutoModel.model.tokenizer
    assert tokenizer.input_ids.cuda_called is True
    assert tokenizer.last_prompt == "<chat>user:hello"
    assert tokenizer.last_tokenize_kwargs["max_length"] == 2048
    assert _FakeAutoModel.model.generate_calls == [{
        "max_new_tokens": 20,
        "use_cache": True,
        "return_dict_in_generate": True,
    }]
    assert tokenizer.decoded == [201, 202]
    assert result["message"]["content"] == "large-model answer"
    assert result["prompt_eval_count"] == 3
    assert result["eval_count"] == 2
    assert result["model"] == "airllm:Qwen/Qwen3-32B"


def test_airllm_rejects_unverified_tool_calling_before_loading(monkeypatch):
    _install_fake_airllm(monkeypatch)
    provider = AirLLMProvider()
    with pytest.raises(ModelError, match="structured tool calling"):
        provider.chat(
            "airllm:Qwen/Qwen3-32B",
            [{"role": "user", "content": "use a tool"}],
            tools=[{"type": "function", "function": {"name": "x"}}],
        )
    assert _FakeAutoModel.calls == []


def test_airllm_stream_is_honest_single_final_chunk(monkeypatch):
    _install_fake_airllm(monkeypatch)
    provider = AirLLMProvider(max_new_tokens=16)
    chunks = list(provider.chat_stream(
        "airllm:Qwen/Qwen3-32B",
        [{"role": "user", "content": "hello"}],
    ))
    assert len(chunks) == 1
    assert chunks[0]["done"] is True
    assert chunks[0]["message"]["content"] == "large-model answer"


def test_composite_routes_prefixed_models_without_changing_ollama_names():
    class Ollama:
        base_url = "http://127.0.0.1:11434"

        def __init__(self):
            self.calls = []

        def chat(self, model, messages, **kwargs):
            self.calls.append(("chat", model))
            return {"message": {"content": "ollama"}}

        def available_models(self):
            return ["qwen:local"]

        def model_inventory(self):
            return {"qwen:local": {"name": "qwen:local"}}

        def running_models(self):
            return []

        def model_size_bytes(self, model):
            return 123

        def preload(self, model, keep_alive=300):
            self.calls.append(("preload", model))
            return {"done": True}

        def unload(self, model):
            self.calls.append(("unload", model))

        def chat_stream(self, model, messages, **kwargs):
            yield self.chat(model, messages, **kwargs)

    class Air:
        is_airllm_model = staticmethod(AirLLMProvider.is_airllm_model)
        normalize_model = staticmethod(AirLLMProvider.normalize_model)

        def __init__(self):
            self.calls = []

        def available_models(self):
            return ["airllm:Qwen/Qwen3-32B"]

        def model_inventory(self):
            return {"airllm:Qwen/Qwen3-32B": {"provider": "airllm"}}

        def running_models(self):
            return []

        def model_size_bytes(self, model):
            self.calls.append(("size", model))
            return None

        def preload(self, model, keep_alive=300):
            self.calls.append(("preload", model))
            return {"done": True}

        def unload(self, model):
            self.calls.append(("unload", model))

        def chat(self, model, messages, **kwargs):
            self.calls.append(("chat", model))
            return {"message": {"content": "air"}}

        def chat_stream(self, model, messages, **kwargs):
            yield self.chat(model, messages, **kwargs)

    ollama = Ollama()
    air = Air()
    provider = CompositeModelProvider(ollama, air)

    assert provider.chat("qwen:local", [{"role": "user", "content": "x"}])["message"]["content"] == "ollama"
    assert provider.chat("airllm:Qwen/Qwen3-32B", [{"role": "user", "content": "x"}])["message"]["content"] == "air"
    assert ollama.calls == [("chat", "qwen:local")]
    assert air.calls == [("chat", "Qwen/Qwen3-32B")]
    assert provider.available_models() == ["qwen:local", "airllm:Qwen/Qwen3-32B"]
    assert provider.base_url == ollama.base_url


def test_airllm_extra_and_packaged_default_config_are_present():
    with open("pyproject.toml", "rb") as f:
        project = tomllib.load(f)
    assert project["project"]["optional-dependencies"]["airllm"] == ["airllm>=4,<5"]

    import yaml
    from importlib import resources
    config = yaml.safe_load(resources.files("living_assistant").joinpath("default_config.yaml").read_text())
    assert config["airllm"]["enabled"] is False
    assert config["airllm"]["compression"] is None
    assert config["airllm"]["hf_token_env"] == "HF_TOKEN"


def test_runtime_enables_composite_provider_without_importing_airllm(tmp_path, monkeypatch):
    import yaml
    from pathlib import Path
    import living_assistant.runtime as runtime

    base = yaml.safe_load(Path("config/assistant.yaml").read_text())
    base["workspace_roots"] = [str(tmp_path / "workspace")]
    base["airllm"]["enabled"] = True
    base["browser"]["enabled"] = False
    base["desktop"]["enabled"] = False
    config_path = tmp_path / "assistant.yaml"
    config_path.write_text(yaml.safe_dump(base, sort_keys=False))
    monkeypatch.setenv("ASSISTANT_CONFIG", str(config_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    rt = runtime.build_runtime(interactive=False)
    assert isinstance(rt.model_manager.provider, CompositeModelProvider)
    assert isinstance(rt.model_manager.provider.airllm, AirLLMProvider)
    # Building the runtime must remain lazy: no model is loaded and the optional
    # dependency is not needed until an airllm: model is actually requested.
    assert rt.model_manager.provider.airllm.running_models() == []
