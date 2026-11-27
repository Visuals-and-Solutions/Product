"""Konfiguracja providerów i obsługa plików .env."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

KNOWN_KEY_NAMES = ["GOOGLE_API_KEY", "GEMINI_API_KEY", "NVIDIA_API_KEY", "ZAI_API_KEY", "ZHIPU_API_KEY"]


def user_config_path() -> Path:
    """Stała lokalizacja kluczy w katalogu domowym — przetrwa reinstalacje i nowe paczki."""
    override = os.environ.get("SCRIPTFORGE_CONFIG")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    return (Path(base).expanduser() / "scriptforge" / ".env")


PROVIDERS = {
    "google": {
        "label": "Google Gemini",
        "env_keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "default_model": "gemini-flash-latest",
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
    """Wczytuje pary KEY=VALUE bez nadpisywania zmiennych już obecnych w środowisku.

    Bez argumentu: najpierw lokalny .env (bieżący katalog, potem katalog projektu),
    na końcu stała konfiguracja użytkownika (~/.config/scriptforge/.env).
    """
    if path is not None:
        candidates = [path]
    else:
        candidates = [
            Path.cwd() / ".env",
            Path(__file__).resolve().parent.parent / ".env",
            user_config_path(),
        ]
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


_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def import_env_file(source: Path) -> tuple[list[str], int]:
    """Kopiuje znane klucze API z podanego pliku do stałej konfiguracji użytkownika.

    Nie nadpisuje kluczy już zapisanych w konfiguracji. Zwraca (zaimportowane nazwy, pominięte).
    """
    source = Path(source).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Nie znaleziono pliku: {source}")
    config_path = user_config_path()
    existing: dict[str, str] = {}
    if config_path.is_file():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            m = _LINE_RE.match(line)
            if m and m.group(1) in KNOWN_KEY_NAMES and m.group(2).strip():
                existing[m.group(1)] = m.group(2).strip()
    imported, skipped = [], 0
    for line in source.read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if not m or m.group(1) not in KNOWN_KEY_NAMES:
            continue
        key, value = m.group(1), m.group(2).strip().strip('"').strip("'")
        if not value:
            continue
        if key in existing:
            skipped += 1
            continue
        existing[key] = value
        imported.append(key)
    if imported:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={existing[k]}" for k in KNOWN_KEY_NAMES if k in existing]
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return imported, skipped


def set_api_key(name: str, value: str) -> None:
    """Zapisuje klucz do stałej konfiguracji i od razu w środowisku procesu."""
    if name not in KNOWN_KEY_NAMES:
        raise ValueError(f"Nieznana nazwa klucza: {name}. Dozwolone: {', '.join(KNOWN_KEY_NAMES)}")
    value = normalize_key(value)
    if not value:
        raise ValueError("Pusta wartość klucza")
    config_path = user_config_path()
    lines: dict[str, str] = {}
    if config_path.is_file():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            m = _LINE_RE.match(line)
            if m and m.group(1) in KNOWN_KEY_NAMES:
                lines[m.group(1)] = m.group(2).strip()
    lines[name] = value
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(f"{k}={lines[k]}" for k in KNOWN_KEY_NAMES if k in lines) + "\n",
        encoding="utf-8",
    )
    os.environ[name] = value


def provider_for_key_name(name: str) -> str | None:
    for provider, meta in PROVIDERS.items():
        if name in meta["env_keys"]:
            return provider
    return None


def key_status() -> list[dict]:
    """Stan kluczy (maskowany — nigdy nie zwraca wartości)."""
    load_dotenv()
    rows = []
    for name in KNOWN_KEY_NAMES:
        value = os.environ.get(name, "")
        masked = f"{value[:4]}…***" if len(value) > 8 else ("(ustawiony)" if value else "")
        rows.append({"name": name, "set": bool(value), "masked": masked})
    return rows


def api_key_for(provider: str) -> str | None:
    for env_key in PROVIDERS.get(provider, {}).get("env_keys", []):
        value = os.environ.get(env_key)
        if value:
            return normalize_key(value)
    return None


def normalize_key(value: str) -> str:
    """Usuwa typowe zanieczyszczenia wklejonego klucza: spacje, cudzysłowy, prefiks Bearer."""
    value = value.strip().strip('"').strip("'").strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value


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
