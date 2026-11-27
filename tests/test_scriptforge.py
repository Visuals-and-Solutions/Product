import sqlite3

import pytest

from scriptforge.generator import extract_code
from scriptforge.providers import MockProvider, build_provider
from scriptforge.storage import Catalog, slugify


@pytest.fixture()
def catalog(tmp_path):
    return Catalog(tmp_path / "ws")


def test_slugify_polish():
    assert slugify("Backup katalogu żółć ĘÓŁ") == "backup-katalogu-zolc-eol"


def test_add_and_get_roundtrip(catalog):
    s = catalog.add(name_hint="Test Script", code="print('x')\n", language="python", tags=["dev"])
    assert s.id is not None
    got = catalog.get(s.id)
    assert got.slug == s.slug
    assert got.tags == ["dev"]
    assert catalog.read_code(got) == "print('x')\n"


def test_slug_uniqueness(catalog):
    a = catalog.add(name_hint="Backup", code="a=1\n")
    b = catalog.add(name_hint="Backup", code="a=2\n")
    assert a.slug != b.slug


def test_list_filter_tag_and_search(catalog):
    catalog.add(name_hint="Backup tar", code="x=1\n", tags=["backup", "devops"])
    catalog.add(name_hint="Cleanup logs", code="x=2\n", tags=["cleanup"])
    assert len(catalog.list(tag="backup")) == 1
    assert len(catalog.list(search="logs")) == 1
    assert len(catalog.list()) == 2


def test_update_meta_and_delete(catalog):
    s = catalog.add(name_hint="Old", code="x=1\n")
    catalog.update_meta(s.id, name="New", tags=["a", "b"])
    got = catalog.get(s.id)
    assert got.name == "New" and got.tags == ["a", "b"]
    path = got.path
    assert catalog.delete(s.id)
    assert catalog.get(s.id) is None
    import pathlib

    assert not pathlib.Path(path).exists()


def test_export_index_and_json(catalog):
    catalog.add(name_hint="Demo", code="x=1\n", tags=["t1"])
    md = catalog.export_index()
    js = catalog.export_json()
    text = md.read_text(encoding="utf-8")
    assert "Demo" in text and "python" in text
    import json

    data = json.loads(js.read_text(encoding="utf-8"))
    assert data[0]["name"] == "Demo"


def test_extract_code_with_fence():
    response = "Oto skrypt:\n```python\nprint('ok')\n```\nMiłego dnia!"
    code, lang = extract_code(response)
    assert code == "print('ok')\n"
    assert lang == "python"


def test_extract_code_without_fence():
    code, lang = extract_code("print('bare')")
    assert code == "print('bare')\n"
    assert lang is None


def test_mock_provider_generate_and_save(catalog):
    provider = MockProvider()
    from scriptforge.generator import generate_and_save

    _, script = generate_and_save(catalog, provider, "hello world script", tags=["demo"])
    assert script.provider == "mock"
    assert "Hello from ScriptForge mock" in catalog.read_code(script)


def test_build_provider_missing_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from scriptforge.providers import ProviderError

    with pytest.raises(ProviderError):
        build_provider("google")


def test_mock_list_models():
    from scriptforge.modelinfo import fetch_models

    models = fetch_models("mock")
    assert "mock-1" in models


def test_get_models_cache_roundtrip(tmp_path, monkeypatch):
    from scriptforge import modelinfo

    info = modelinfo.get_models("mock", refresh=True, cache_dir=tmp_path)
    assert info["source"] == "api" and info["models"] == ["mock-1", "mock-2-mini"]

    from scriptforge.providers import MockProvider

    monkeypatch.setattr(MockProvider, "list_models", lambda self: ["changed-1"])
    cached = modelinfo.get_models("mock", cache_dir=tmp_path)
    assert cached["source"] == "cache" and cached["models"] == ["mock-1", "mock-2-mini"]

    refreshed = modelinfo.get_models("mock", refresh=True, cache_dir=tmp_path)
    assert refreshed["source"] == "api" and refreshed["models"] == ["changed-1"]


def test_get_models_missing_key(tmp_path, monkeypatch):
    from scriptforge.modelinfo import get_models

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    info = get_models("google", cache_dir=tmp_path)
    assert info["models"] == [] and info["error"] and "Brak klucza" in info["error"]


def test_import_env_file_preserves_existing(tmp_path, monkeypatch):
    from scriptforge import config

    monkeypatch.setenv("SCRIPTFORGE_CONFIG", str(tmp_path / "cfg" / ".env"))
    old = tmp_path / "old.env"
    old.write_text("GOOGLE_API_KEY=old-google-key\nNVIDIA_API_KEY=old-nv-key\nOTHER=1\n")
    imported, skipped = config.import_env_file(old)
    assert imported == ["GOOGLE_API_KEY", "NVIDIA_API_KEY"]
    saved = (tmp_path / "cfg" / ".env").read_text()
    assert "old-google-key" in saved and "OTHER" not in saved

    newer = tmp_path / "newer.env"
    newer.write_text("GOOGLE_API_KEY=newer-key\nZAI_API_KEY=zai-key\n")
    imported2, skipped2 = config.import_env_file(newer)
    assert imported2 == ["ZAI_API_KEY"] and skipped2 == 1
    assert "newer-key" not in (tmp_path / "cfg" / ".env").read_text()


def test_key_status_masks_values(tmp_path, monkeypatch):
    from scriptforge import config

    monkeypatch.setenv("SCRIPTFORGE_CONFIG", str(tmp_path / "cfg" / ".env"))
    monkeypatch.setenv("GOOGLE_API_KEY", "secret-value-123456")
    rows = {r["name"]: r for r in config.key_status()}
    assert rows["GOOGLE_API_KEY"]["set"] is True
    assert "secret-value-123456" not in rows["GOOGLE_API_KEY"]["masked"]


def test_load_dotenv_does_not_override_environment(tmp_path, monkeypatch):
    from scriptforge.config import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_API_KEY=from-file\n")
    monkeypatch.setenv("GOOGLE_API_KEY", "from-env")
    monkeypatch.chdir(tmp_path)
    load_dotenv()
    import os

    assert os.environ["GOOGLE_API_KEY"] == "from-env"


def test_normalize_key_strips_pollution():
    from scriptforge.config import normalize_key

    assert normalize_key('  "abc-123"  ') == "abc-123"
    assert normalize_key("Bearer abc-123") == "abc-123"
    assert normalize_key(" abc-123 ") == "abc-123"


def test_explain_error_maps_invalid_key():
    from scriptforge.providers import explain_error

    msg = explain_error('{"error":{"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT"}}', 400, "google")
    assert "Klucz API jest nieprawidłowy" in msg and "AQ.Ab" in msg
    msg404 = explain_error("model not found", 404, "google")
    assert "scriptforge models" in msg404


def test_google_provider_invalid_key_message(monkeypatch):
    import httpx

    from scriptforge.providers import GoogleGeminiProvider, ProviderError

    monkeypatch.setenv("GOOGLE_API_KEY", "zly-klucz")
    provider = GoogleGeminiProvider("gemini-2.5-flash", "zly-klucz")

    def fake_post(*a, **kw):
        return httpx.Response(400, request=httpx.Request("POST", "http://x"), json={
            "error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    try:
        provider.generate("test")
        assert False, "powinien rzucić ProviderError"
    except ProviderError as exc:
        assert "Klucz API jest nieprawidłowy" in str(exc)


def test_set_api_key_writes_and_env(tmp_path, monkeypatch):
    from scriptforge import config

    monkeypatch.setenv("SCRIPTFORGE_CONFIG", str(tmp_path / "cfg" / ".env"))
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    config.set_api_key("NVIDIA_API_KEY", "  nv-key-999  ")
    import os

    assert os.environ["NVIDIA_API_KEY"] == "nv-key-999"
    assert (tmp_path / "cfg" / ".env").read_text() == "NVIDIA_API_KEY=nv-key-999\n"

    config.set_api_key("ZAI_API_KEY", "zai-1")
    content = (tmp_path / "cfg" / ".env").read_text()
    assert "nv-key-999" in content and "zai-1" in content


def test_set_api_key_rejects_unknown(tmp_path, monkeypatch):
    from scriptforge import config

    monkeypatch.setenv("SCRIPTFORGE_CONFIG", str(tmp_path / "cfg" / ".env"))
    try:
        config.set_api_key("HACKED_KEY", "x")
        assert False
    except ValueError:
        pass


def test_key_kind_detection():
    from scriptforge.config import key_kind

    assert key_kind("AQ.Ab1234567890abcdefghijklmnopqrstuvw") == "Auth (AQ)"
    assert "wygasły" in key_kind("AIzaSyABCDEF1234567890")
    assert "nieznany" in key_kind("xyz")


def test_google_uses_header_auth(monkeypatch):
    import httpx

    from scriptforge.providers import GoogleGeminiProvider

    provider = GoogleGeminiProvider("gemini-4-hydrogen", "AQ.AbTestKey123")
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        return httpx.Response(200, request=httpx.Request("GET", url), json={
            "models": [{"name": "models/gemini-4-hydrogen", "supportedGenerationMethods": ["generateContent"]}]
        })

    monkeypatch.setattr(httpx, "get", fake_get)
    models = provider.list_models()
    assert models == ["gemini-4-hydrogen"]
    assert captured["headers"].get("x-goog-api-key") == "AQ.AbTestKey123"
    assert "key=" not in captured["url"]
