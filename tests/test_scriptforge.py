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
