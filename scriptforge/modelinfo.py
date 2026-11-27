"""Lista dostępnych modeli dla klucza API, z lokalnym cache i odświeżaniem."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .config import PROVIDERS, Settings, api_key_for, load_dotenv
from .providers import ProviderError, build_provider

CACHE_FILENAME = "model_cache.json"
DEFAULT_TTL_SECONDS = 24 * 3600


def _cache_path(cache_dir: Path) -> Path:
    return cache_dir / CACHE_FILENAME


def _read_cache(cache_dir: Path) -> dict:
    path = _cache_path(cache_dir)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cache(cache_dir: Path, data: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(cache_dir).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def fetch_models(provider: str, model: str | None = None) -> list[str]:
    """Pobiera listę modeli prosto z API providera (wymaga klucza)."""
    return build_provider(provider, model).list_models()


def get_models(
    provider: str,
    *,
    refresh: bool = False,
    cache_dir: Path | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict:
    """Zwraca {'models': [...], 'source': 'api'|'cache', 'fetched_at': str|None, 'error': str|None}.

    Cache leży w katalogu roboczym systemu, więc lista odświeża się w tle pracy
    aplikacji i jest dostępna offline do wygaśnięcia TTL (domyślnie 24 h).
    """
    if cache_dir is None:
        cache_dir = Settings.from_env().workspace
    cache = _read_cache(cache_dir)
    entry = cache.get(provider, {})
    age = time.time() - float(entry.get("fetched_at_ts", 0))
    if not refresh and entry.get("models") and age < ttl_seconds:
        return {
            "provider": provider,
            "models": entry["models"],
            "source": "cache",
            "fetched_at": entry.get("fetched_at"),
            "error": None,
        }
    error = None
    models = []
    if not api_key_for(provider) and provider != "mock":
        error = f"Brak klucza API dla {provider}"
    else:
        try:
            models = fetch_models(provider)
        except (ProviderError, OSError) as exc:
            error = str(exc)
    if models:
        cache[provider] = {
            "models": models,
            "fetched_at_ts": time.time(),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        _write_cache(cache_dir, cache)
        return {
            "provider": provider,
            "models": models,
            "source": "api",
            "fetched_at": cache[provider]["fetched_at"],
            "error": None,
        }
    if entry.get("models"):
        return {
            "provider": provider,
            "models": entry["models"],
            "source": "cache",
            "fetched_at": entry.get("fetched_at"),
            "error": error,
        }
    return {"provider": provider, "models": [], "source": "none", "fetched_at": None, "error": error}


def all_models(refresh: bool = False, cache_dir: Path | None = None) -> dict[str, dict]:
    load_dotenv()
    return {p: get_models(p, refresh=refresh, cache_dir=cache_dir) for p in PROVIDERS}


__all__ = ["fetch_models", "get_models", "all_models", "DEFAULT_TTL_SECONDS"]
