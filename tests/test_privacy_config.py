import pytest

from todays_outfit.config import Endpoint, load_config
from todays_outfit.llm import LLMClient, PrivacyError, check_privacy, is_local


def test_is_local():
    assert is_local("http://localhost:11434/v1") and is_local("http://127.0.0.1:8080/v1")
    assert not is_local("https://api.siliconflow.cn/v1")
    assert not is_local("http://localhost.evil.com/v1")


def test_privacy_matrix():
    cloud = "https://api.example.com/v1"
    check_privacy("off", cloud, True)
    check_privacy("images-local", cloud, False)
    check_privacy("local-only", "http://localhost:11434/v1", True)
    with pytest.raises(PrivacyError):
        check_privacy("images-local", cloud, True)
    with pytest.raises(PrivacyError):
        check_privacy("local-only", cloud, False)


def test_client_refuses_images_before_any_network_call():
    c = LLMClient(Endpoint("https://api.example.com/v1", "m", "SOME_KEY"), privacy="local-only")
    msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}]}]
    with pytest.raises(PrivacyError):
        c.chat(msg)


def test_one_line_switch(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[llm]\npreset = "siliconflow"\n')
    a = load_config(cfg)
    assert a.vision.base_url == "https://api.siliconflow.cn/v1" and a.vision.api_key_env == "SILICONFLOW_API_KEY"
    cfg.write_text('[llm]\npreset = "local"\n')
    b = load_config(cfg)
    assert b.vision.base_url == "http://localhost:11434/v1" and b.vision.api_key_env == ""


def test_per_step_override_and_bad_values(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[llm]\npreset = "siliconflow"\nprivacy = "images-local"\n[vision]\npreset = "local"\nmodel = "x"\n')
    c = load_config(cfg)
    assert c.vision.model == "x" and c.vision.base_url.startswith("http://localhost") and c.text.base_url.startswith("https://")
    assert c.privacy == "images-local"
    cfg.write_text('[llm]\npreset = "nope"\n')
    with pytest.raises(ValueError):
        load_config(cfg)
    with pytest.raises(ValueError):
        load_config(None, privacy="whatever")


def test_missing_key_env_is_reported_without_leaking(monkeypatch):
    from todays_outfit.llm import LLMError
    monkeypatch.delenv("SOME_KEY", raising=False)
    c = LLMClient(Endpoint("https://api.example.com/v1", "m", "SOME_KEY"))
    with pytest.raises(LLMError, match="SOME_KEY"):
        c.chat([{"role": "user", "content": "hi"}])
