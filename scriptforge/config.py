"""Konfiguracja providerów i obsługa pliku .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROVIDERS = {
    "google": {
        "label": "Google Gemini",
        "env_keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "default_model": "gemini-2.5-flash",
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "env_keys": ["NVIDIA_API_KEY"],
        "default_model": "meta/llama-3.3-70b-instruct",
    },
    "zai": {
        "label": "Z.ai (GLM)",
        "env_keys": ["ZAI_API_KEY", "ZHIPU_API_KEY"],
        "default_model": "glm-4.6",
    },
    "mock": {
        "label": "Mock (testy, bez klucza)",
        "env_keys": [],
        "default_model": "mock-1",
    },
}


def load_dotenv(path: Path | None = None) -> None:
    """Wczytuje proste pary KEY=VALUE z pliku .env (bez nadpisywania istniejących)."""
    candidates = [path] if path else [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    for candidate in candidates:
        if not candidate or not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def api_key_for(provider: str) -> str | None:
    for env_key in PROVIDERS.get(provider, {}).get("env_keys", []):
        value = os.environ.get(env_key)
        if value:
            return value
    return None


@dataclass
class Settings:
    workspace: Path
    provider: str
    model: str | None
    db_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        workspace = Path(os.environ.get("SCRIPTFORGE_HOME", Path.home() / "scriptforge")).expanduser()
        provider = os.environ.get("SCRIPTFORGE_PROVIDER", "google")
        if provider not in PROVIDERS:
            provider = "google"
        model = os.environ.get("SCRIPTFORGE_MODEL") or PROVIDERS[provider]["default_model"]
        return cls(
            workspace=workspace,
            provider=provider,
            model=model,
            db_path=workspace / "catalog.sqlite3",
        )
